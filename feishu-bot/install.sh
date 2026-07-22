#!/bin/bash
# Install the write-only journal capture bot as a macOS launchd service.
set -euo pipefail

LABEL="com.journal-organizer.capture"
REVIEW_LABEL="com.journal-organizer.weekly-review"
BOT_DIR="${JOURNAL_BOT_DIR:-$HOME/.journal-bot}"
CONFIG_DIR="${JOURNAL_CONFIG_DIR:-$HOME/.config/journal-organizer}"
CONFIG_FILE="$CONFIG_DIR/config.json"
PROFILE="${LARK_PROFILE:-}"
SOURCE_DIR="$(cd "$(dirname "$0")/templates" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REVIEW_PLIST="$HOME/Library/LaunchAgents/$REVIEW_LABEL.plist"

if [[ -z "$PROFILE" ]]; then
  echo "LARK_PROFILE is required. Example:"
  echo "  LARK_PROFILE=cli_xxx bash feishu-bot/install.sh"
  exit 1
fi

for command in python3 node lark-cli; do
  command -v "$command" >/dev/null || { echo "Missing dependency: $command"; exit 1; }
done

CODEX_BIN="${CODEX_BIN:-$(command -v codex 2>/dev/null || true)}"
if [[ -z "$CODEX_BIN" && -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
fi
[[ -x "$CODEX_BIN" ]] || { echo "Codex CLI not found. Set CODEX_BIN."; exit 1; }

PYTHON_BIN="$(command -v python3)"
PATH_VALUE="$(dirname "$(command -v lark-cli)"):$(dirname "$CODEX_BIN"):$(dirname "$(command -v node)"):/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$BOT_DIR" "$CONFIG_DIR" "$HOME/Library/LaunchAgents"
cp "$SOURCE_DIR/handler.py" "$BOT_DIR/handler.py"
cp "$SOURCE_DIR/weekly_review.py" "$BOT_DIR/weekly_review.py"
cp "$SOURCE_DIR/organize_schema.json" "$BOT_DIR/organize_schema.json"
cp "$SOURCE_DIR/ctl.sh" "$BOT_DIR/ctl.sh"
chmod +x "$BOT_DIR/ctl.sh"

if [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$(dirname "$0")/../config.example.json" "$CONFIG_FILE"
  echo "Created $CONFIG_FILE. Set its vault path before sending messages."
fi

cat > "$BOT_DIR/run.sh" <<EOF
#!/bin/bash
set -euo pipefail
export HOME="$HOME"
export PATH="$PATH_VALUE"
export CODEX_BIN="$CODEX_BIN"
export LARK_PROFILE="$PROFILE"
export LARK_CLI_NO_PROXY=1
cd "$BOT_DIR"
exec lark-cli --profile "$PROFILE" event consume im.message.receive_v1 --as bot --quiet \\
  < <(tail -f /dev/null) \\
  | "$PYTHON_BIN" -u handler.py
EOF

cat > "$BOT_DIR/run-weekly.sh" <<EOF
#!/bin/bash
set -euo pipefail
export HOME="$HOME"
export PATH="$PATH_VALUE"
export CODEX_BIN="$CODEX_BIN"
export LARK_PROFILE="$PROFILE"
export LARK_CLI_NO_PROXY=1
cd "$BOT_DIR"
exec "$PYTHON_BIN" weekly_review.py
EOF
chmod +x "$BOT_DIR/run.sh" "$BOT_DIR/run-weekly.sh"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$BOT_DIR/run.sh</string></array>
  <key>WorkingDirectory</key><string>$BOT_DIR</string>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$BOT_DIR/runtime.log</string>
  <key>StandardErrorPath</key><string>$BOT_DIR/runtime.log</string>
</dict></plist>
EOF

cat > "$REVIEW_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$REVIEW_LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$BOT_DIR/run-weekly.sh</string></array>
  <key>WorkingDirectory</key><string>$BOT_DIR</string>
  <key>StartCalendarInterval</key><dict>
    <key>Weekday</key><integer>0</integer><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>$BOT_DIR/weekly.log</string>
  <key>StandardErrorPath</key><string>$BOT_DIR/weekly.log</string>
</dict></plist>
EOF

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootout "$DOMAIN/$REVIEW_LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl bootstrap "$DOMAIN" "$REVIEW_PLIST"

echo "Capture bot installed in $BOT_DIR"
echo "Profile: $PROFILE"
echo "Config: $CONFIG_FILE"
echo "Next: configure the Feishu long-connection event and publish the app."

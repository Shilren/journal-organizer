#!/bin/bash
# Install the read-only personal knowledge bot as a macOS launchd service.
set -euo pipefail

LABEL="com.journal-organizer.knowledge"
BOT_DIR="${KNOWLEDGE_BOT_DIR:-$HOME/.knowledge-bot}"
CONFIG_FILE="${JOURNAL_CONFIG:-$HOME/.config/journal-organizer/config.json}"
PROFILE="${LARK_PROFILE:-}"
SOURCE_DIR="$(cd "$(dirname "$0")/templates" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ -z "$PROFILE" ]]; then
  echo "LARK_PROFILE is required. Use a different Feishu app from the capture bot."
  echo "  LARK_PROFILE=cli_xxx bash knowledge-bot/install.sh"
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
[[ -f "$CONFIG_FILE" ]] || { echo "Missing $CONFIG_FILE. Install the capture bot or copy config.example.json first."; exit 1; }

VAULT="$(python3 -c 'import json,os,sys; print(os.path.expanduser(json.load(open(sys.argv[1], encoding="utf-8")).get("vault", "")))' "$CONFIG_FILE")"
[[ -n "$VAULT" ]] || { echo "vault is empty in $CONFIG_FILE"; exit 1; }

PYTHON_BIN="$(command -v python3)"
PATH_VALUE="$(dirname "$(command -v lark-cli)"):$(dirname "$CODEX_BIN"):$(dirname "$(command -v node)"):/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$BOT_DIR" "$HOME/Library/LaunchAgents"
cp "$SOURCE_DIR/handler.py" "$BOT_DIR/handler.py"
cp "$SOURCE_DIR/ctl.sh" "$BOT_DIR/ctl.sh"
chmod +x "$BOT_DIR/ctl.sh"
if [[ ! -f "$BOT_DIR/self_model.md" ]]; then
  cp "$SOURCE_DIR/self_model.example.md" "$BOT_DIR/self_model.md"
fi

cat > "$BOT_DIR/run.sh" <<EOF
#!/bin/bash
set -euo pipefail
export HOME="$HOME"
export PATH="$PATH_VALUE"
export CODEX_BIN="$CODEX_BIN"
export LARK_PROFILE="$PROFILE"
export KNOWLEDGE_VAULT="$VAULT"
export LARK_CLI_NO_PROXY=1
cd "$BOT_DIR"
exec lark-cli --profile "$PROFILE" event consume im.message.receive_v1 --as bot --quiet \\
  < <(tail -f /dev/null) \\
  | "$PYTHON_BIN" -u handler.py
EOF
chmod +x "$BOT_DIR/run.sh"

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

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"

echo "Knowledge bot installed in $BOT_DIR"
echo "Profile: $PROFILE"
echo "Vault: $VAULT"
echo "Edit $BOT_DIR/self_model.md to define voice, values and answer style."

#!/bin/bash
# ============================================================
#  journal-organizer · 飞书机器人 一键安装器（macOS）
#  把"从手机口述 → 自动整理归档进笔记仓库"的飞书 bot 装成
#  开机自启、睡眠不丢、崩溃自愈的后台服务。
# ============================================================
set -uo pipefail

LABEL="com.journal-bot"
RLABEL="com.journal-review"
BOTDIR="$HOME/.journal-bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RPLIST="$HOME/Library/LaunchAgents/$RLABEL.plist"
CONFIG_DIR="$HOME/.config/journal-organizer"
CONFIG_FILE="$CONFIG_DIR/config.json"
SRC="$(cd "$(dirname "$0")" && pwd)/templates"

say()  { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
err()  { printf "  \033[1;31m✗\033[0m %s\n" "$*"; }

say "==> 1/6 检查环境"
MISSING=0
for bin in python3 node lark-cli claude; do
  if p=$(command -v "$bin" 2>/dev/null); then
    ok "$bin -> $p"
  else
    err "缺少 $bin"
    MISSING=1
  fi
done
if [ "$MISSING" = 1 ]; then
  echo
  warn "缺少依赖，先装上再重跑本脚本："
  echo "    node:     https://nodejs.org  (或 brew install node)"
  echo "    lark-cli: npm install -g @larksuite/cli"
  echo "    claude:   https://claude.com/claude-code"
  exit 1
fi

# 组装一个干净 PATH（launchd 下 PATH 极简，必须写全）
NODE_DIR="$(dirname "$(command -v node)")"
CLI_DIR="$(dirname "$(command -v lark-cli)")"
CLAUDE_DIR="$(dirname "$(command -v claude)")"
PY="$(command -v python3)"
BOT_PATH="$CLI_DIR:$CLAUDE_DIR:$NODE_DIR:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

say "==> 2/6 检查 lark-cli 是否已登录机器人身份"
if lark-cli event list >/dev/null 2>&1; then
  ok "lark-cli 可用"
else
  warn "lark-cli 还没配置好。请先按 lark-cli 文档登录你的自建应用（机器人）："
  echo "    lark-cli auth login        # 按提示填 App ID / Secret"
  echo "  配置完再重跑本脚本。"
  exit 1
fi

say "==> 3/6 部署脚本到 $BOTDIR"
mkdir -p "$BOTDIR"
cp "$SRC/handler.py" "$BOTDIR/handler.py"
cp "$SRC/ctl.sh" "$BOTDIR/ctl.sh"
cp "$SRC/weekly_review.py" "$BOTDIR/weekly_review.py"
chmod +x "$BOTDIR/ctl.sh"

# 生成 run.sh（带正确 PATH）
cat > "$BOTDIR/run.sh" <<EOF
#!/bin/bash
set -uo pipefail
cd "$BOTDIR"
export PATH="$BOT_PATH"
export LARK_CLI_NO_PROXY=1
exec lark-cli event consume im.message.receive_v1 --as bot --quiet \\
  < <(tail -f /dev/null) \\
  | "$PY" -u handler.py
EOF
chmod +x "$BOTDIR/run.sh"
ok "handler.py / run.sh / ctl.sh 就位"

say "==> 4/6 检查配置（仓库 + 分类，与 journal-organizer skill 共用）"
if [ -f "$CONFIG_FILE" ]; then
  ok "已存在 $CONFIG_FILE"
else
  mkdir -p "$CONFIG_DIR"
  cat > "$CONFIG_FILE" <<'EOF'
{
  "vault": "/绝对路径/改成你的/笔记仓库文件夹",
  "categories": [
    {"name": "生活记录", "desc": "这一天发生了什么、做了什么"},
    {"name": "情绪感受", "desc": "当下心情、情绪波动、内心状态"},
    {"name": "学习复盘", "desc": "学到的知识、读到听到的内容、对某主题的总结"},
    {"name": "创作灵感", "desc": "内容选题、写作/视频的点子"},
    {"name": "商业想法", "desc": "生意、产品、商业模式、变现、市场机会"}
  ]
}
EOF
  warn "已生成配置模板：$CONFIG_FILE"
  warn "请编辑它：把 vault 改成你的仓库绝对路径，按需增删分类（每个分类配一句 desc）。"
fi

say "==> 5/6 安装开机自启服务（launchd）"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>$BOTDIR/run.sh</string></array>
    <key>WorkingDirectory</key><string>$BOTDIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>$HOME</string>
        <key>PATH</key><string>$BOT_PATH</string>
        <key>LARK_CLI_NO_PROXY</key><string>1</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>15</integer>
    <key>StandardOutPath</key><string>$BOTDIR/runtime.log</string>
    <key>StandardErrorPath</key><string>$BOTDIR/runtime.log</string>
</dict>
</plist>
EOF
DOM="gui/$(id -u)"
launchctl bootout "$DOM/$LABEL" 2>/dev/null
if launchctl bootstrap "$DOM" "$PLIST" 2>/dev/null; then
  ok "服务已加载并启动"
else
  err "launchctl bootstrap 失败，可手动：launchctl bootstrap $DOM \"$PLIST\""
fi

# 每周复盘定时任务（周日 21:00）
cat > "$RPLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$RLABEL</string>
    <key>ProgramArguments</key>
    <array><string>$PY</string><string>$BOTDIR/weekly_review.py</string></array>
    <key>WorkingDirectory</key><string>$BOTDIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>$HOME</string>
        <key>PATH</key><string>$BOT_PATH</string>
        <key>LARK_CLI_NO_PROXY</key><string>1</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>$BOTDIR/weekly.log</string>
    <key>StandardErrorPath</key><string>$BOTDIR/weekly.log</string>
</dict>
</plist>
EOF
launchctl bootout "$DOM/$RLABEL" 2>/dev/null
if launchctl bootstrap "$DOM" "$RPLIST" 2>/dev/null; then
  ok "每周复盘定时任务已装（周日 21:00）"
else
  warn "周复盘定时任务加载失败，可手动：launchctl bootstrap $DOM \"$RPLIST\""
fi

say "==> 6/6 完成 ✅"
cat <<EOF

下一步（必须在飞书开放平台 open.feishu.cn 给你的自建应用配置好，否则收不到消息）：
  1) 事件与回调 → 订阅方式：选「使用长连接接收事件」
  2) 添加事件：im.message.receive_v1（接收消息）
  3) 权限管理：加 im:message.p2p_msg:readonly 和发消息权限，然后「创建版本并发布」

日常管理：
  $BOTDIR/ctl.sh status     # 看状态
  $BOTDIR/ctl.sh log        # 看日志
  $BOTDIR/ctl.sh restart    # 重启
  $BOTDIR/ctl.sh stop       # 停（想停务必用这个，别用 kill）

用法：在飞书私聊你的 bot，直接发想法文字即可。设备睡眠也不丢，醒来自动补归档。
若刚才生成了配置模板，记得先把 $CONFIG_FILE 里的 vault 改成你的仓库路径，再 ctl.sh restart。
EOF

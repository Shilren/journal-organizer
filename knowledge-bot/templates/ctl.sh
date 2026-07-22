#!/bin/bash
LABEL="com.journal-organizer.knowledge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
BOT_DIR="${KNOWLEDGE_BOT_DIR:-$HOME/.knowledge-bot}"
LOG="$BOT_DIR/bot.log"

case "${1:-status}" in
  status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E '^\s*(state|pid|last exit) ' || echo "未加载（已停止）"
    ;;
  start)
    launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null && echo "已启动" || echo "可能已在运行"
    ;;
  stop)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && echo "已停止" || echo "本来就没运行"
    ;;
  restart)
    launchctl kickstart -k "$DOMAIN/$LABEL" 2>/dev/null && echo "已重启" || { launchctl bootstrap "$DOMAIN" "$PLIST" && echo "已启动"; }
    ;;
  log)
    tail -f "$LOG"
    ;;
  *)
    echo "用法: ctl.sh [status|start|stop|restart|log]"
    ;;
esac

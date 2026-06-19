#!/bin/bash
# 想法机器人 一键管理
# 用法: ~/.journal-bot/ctl.sh [status|start|stop|restart|log]
LABEL="com.journal-bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOM="gui/$(id -u)"
LOG="$HOME/.journal-bot/bot.log"

case "${1:-status}" in
  status)
    launchctl print "$DOM/$LABEL" 2>/dev/null | grep -E '^\s*(state|pid|last exit) ' \
      || echo "未加载（已停止）"
    ;;
  start)
    launchctl bootstrap "$DOM" "$PLIST" 2>/dev/null && echo "已启动" || echo "可能已在运行"
    ;;
  stop)
    # 必须用 bootout，pkill 会被 KeepAlive 自动拉起
    launchctl bootout "$DOM/$LABEL" 2>/dev/null && echo "已停止" || echo "本来就没运行"
    ;;
  restart)
    launchctl kickstart -k "$DOM/$LABEL" 2>/dev/null && echo "已重启" \
      || { launchctl bootstrap "$DOM" "$PLIST" && echo "已启动"; }
    ;;
  log)
    tail -f "$LOG"
    ;;
  *)
    echo "用法: ctl.sh [status|start|stop|restart|log]"
    ;;
esac

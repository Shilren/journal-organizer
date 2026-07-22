#!/bin/bash
# Install both bots. They must use two different Feishu app profiles.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
JOURNAL_PROFILE="${JOURNAL_LARK_PROFILE:-}"
KNOWLEDGE_PROFILE="${KNOWLEDGE_LARK_PROFILE:-}"

if [[ -z "$JOURNAL_PROFILE" || -z "$KNOWLEDGE_PROFILE" ]]; then
  echo "Set two distinct lark-cli profiles:"
  echo "  JOURNAL_LARK_PROFILE=cli_writer KNOWLEDGE_LARK_PROFILE=cli_reader bash install-all.sh"
  exit 1
fi
if [[ "$JOURNAL_PROFILE" == "$KNOWLEDGE_PROFILE" ]]; then
  echo "The two bots cannot share one Feishu app profile; event consumers would compete."
  exit 1
fi

LARK_PROFILE="$JOURNAL_PROFILE" bash "$ROOT/feishu-bot/install.sh"
LARK_PROFILE="$KNOWLEDGE_PROFILE" bash "$ROOT/knowledge-bot/install.sh"

echo "Both bots are installed. Configure and publish both Feishu apps."

#!/usr/bin/env bash
set -euo pipefail

event_name="${CC_HOOK_EVENT:-}"
project="${CC_HOOK_PROJECT:-}"

if [[ "$event_name" != "message.received" ]]; then
  exit 0
fi

projects_csv="${FAMILY_MEMORY_PROJECTS:-family-codex-at,family-group,family-deep}"
case ",${projects_csv}," in
  *,"${project}",*) ;;
  *) exit 0 ;;
esac

workspace="${FAMILY_MEMORY_WORKSPACE:-$(pwd)}"
script="${FAMILY_MEMORY_SCRIPT:-$workspace/scripts/family-memory-capture.py}"
if [[ ! -f "$script" ]]; then
  exit 0
fi

text="${CC_HOOK_TEXT:-${CC_HOOK_CONTENT:-${CC_HOOK_MESSAGE_TEXT:-${CC_HOOK_MESSAGE:-}}}}"
sender_id="${CC_HOOK_USER_ID:-${CC_HOOK_SENDER_ID:-${CC_HOOK_OPEN_ID:-${CC_HOOK_USER_OPEN_ID:-unknown_open_id}}}}"
sender_name="${CC_HOOK_USER_NAME:-${CC_HOOK_SENDER_NAME:-${CC_HOOK_NAME:-未命名成员}}}"
message_id="${CC_HOOK_MESSAGE_ID:-${CC_HOOK_MSG_ID:-${CC_HOOK_EVENT_ID:-}}}"
chat_id="${CC_HOOK_CHAT_ID:-}"

if [[ -z "$text" ]]; then
  exit 0
fi

python3 "$script" \
  --workspace "$workspace" \
  --chat-id "$chat_id" \
  --message-id "$message_id" \
  --sender-open-id "$sender_id" \
  --sender-name "$sender_name" \
  --text "$text" >/dev/null 2>&1 || true

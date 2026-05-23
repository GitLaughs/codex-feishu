#!/usr/bin/env bash
set -euo pipefail

mini_project="feishu-mini"
deep_project="feishu-deep"
deep_mention_pattern='(@_user_|deep|codex)'
ack_mini_all_messages=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mini-project) mini_project="${2:-}"; shift 2 ;;
    --deep-project) deep_project="${2:-}"; shift 2 ;;
    --deep-mention-pattern) deep_mention_pattern="${2:-}"; shift 2 ;;
    --ack-mini-all-messages) ack_mini_all_messages=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

project="${CC_HOOK_PROJECT:-}"
session="${CC_HOOK_SESSION_KEY:-}"
event_name="${CC_HOOK_EVENT:-}"
message_text="${CC_HOOK_TEXT:-}
${CC_HOOK_CONTENT:-}
${CC_HOOK_MESSAGE:-}
${CC_HOOK_MESSAGE_TEXT:-}"
ack_text="收到正在输出，请等等我。"

if [[ "$event_name" != "message.received" ]]; then exit 0; fi
if [[ -z "$project" || -z "$session" ]]; then exit 0; fi

cc_connect="$(command -v cc-connect || true)"
if [[ -z "$cc_connect" ]]; then exit 0; fi

should_ack=0
if [[ "$project" == "$deep_project" ]]; then
  should_ack=1
elif [[ "$project" == "$mini_project" ]]; then
  if [[ "$ack_mini_all_messages" -ne 1 ]]; then
    exit 0
  fi
  if [[ -n "$message_text" && "$message_text" =~ $deep_mention_pattern ]]; then
    should_ack=0
  else
    should_ack=1
  fi
fi

if [[ "$should_ack" -ne 1 ]]; then exit 0; fi

# message.received hooks can fire before cc-connect has fully registered the
# target session for CLI sends. Retry briefly so the acknowledgement is still
# immediate from the user's perspective but not lost to that race.
for _ in 1 2 3 4 5 6 7 8; do
  if "$cc_connect" send --project "$project" --session "$session" --message "$ack_text" >/dev/null 2>&1; then
    exit 0
  fi
  sleep 0.25
done

exit 0

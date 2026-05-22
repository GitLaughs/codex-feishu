#!/usr/bin/env bash
set -euo pipefail

event_key="im.message.receive_v1"
as_identity="bot"
timeout_value="10m"
max_events=0
jq_filter=""
output_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-key) event_key="$2"; shift 2 ;;
    --as) as_identity="$2"; shift 2 ;;
    --timeout) timeout_value="$2"; shift 2 ;;
    --max-events) max_events="$2"; shift 2 ;;
    --jq) jq_filter="$2"; shift 2 ;;
    --output-file) output_file="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_dir="${workspace}/memory/lark-events"
audit_path="${workspace}/memory/lark-audit.jsonl"
stamp="$(date +%Y%m%d-%H%M%S)"
safe_event="$(printf '%s' "$event_key" | sed -E 's/[^A-Za-z0-9._-]/_/g')"

mkdir -p "$run_dir" "$(dirname "$audit_path")"

if [[ -z "$output_file" ]]; then
  output_file="${run_dir}/${stamp}-${safe_event}.ndjson"
fi
stderr_file="${run_dir}/${stamp}.stderr.log"

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "lark-cli not found. Install with: npx @larksuite/cli@latest install" >&2
  exit 127
fi
if ! command -v timeout >/dev/null 2>&1; then
  echo "timeout command not found" >&2
  exit 127
fi

args=(event consume "$event_key" --as "$as_identity" --timeout "$timeout_value")
if [[ "$max_events" -gt 0 ]]; then
  args+=(--max-events "$max_events")
fi
if [[ -n "$jq_filter" ]]; then
  args+=(--jq "$jq_filter")
fi

set +e
timeout "$timeout_value" lark-cli "${args[@]}" >"$output_file" 2>"$stderr_file"
exit_code=$?
set -e

if [[ "$exit_code" -eq 124 ]]; then
  ok=true
else
  [[ "$exit_code" -eq 0 ]] && ok=true || ok=false
fi

printf '{"time":"%s","action":"event_consume","ok":%s,"event_key":"%s","as":"%s","exit_code":%s,"output_file":"%s","stderr_file":"%s"}\n' \
  "$(date -Is)" "$ok" "$event_key" "$as_identity" "$exit_code" "$output_file" "$stderr_file" >>"$audit_path"

printf '{"ok":%s,"event_key":"%s","as":"%s","exit_code":%s,"output_file":"%s","stderr_file":"%s"}\n' \
  "$ok" "$event_key" "$as_identity" "$exit_code" "$output_file" "$stderr_file"

#!/usr/bin/env bash
set -euo pipefail

dream_model="gpt-5.5"
dream_effort="xhigh"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dream-model) dream_model="$2"; shift 2 ;;
    --dream-effort) dream_effort="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prompt_path="${workspace}/scripts/dream_prompt.md"
dream_dir="${workspace}/memory/dreams"
stamp="$(date +%Y%m%d-%H%M%S)"
last_message_path="${dream_dir}/${stamp}-last-message.md"
log_path="${dream_dir}/${stamp}-events.jsonl"

if [[ ! -f "$prompt_path" ]]; then
  echo "prompt missing: $prompt_path" >&2
  exit 1
fi
if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found" >&2
  exit 127
fi

mkdir -p "$dream_dir"

set +e
codex exec \
  --ephemeral \
  --disable memories \
  -C "$workspace" \
  --skip-git-repo-check \
  --dangerously-bypass-approvals-and-sandbox \
  -m "$dream_model" \
  -c "model_reasoning_effort=\"${dream_effort}\"" \
  -o "$last_message_path" \
  - <"$prompt_path" >"$log_path" 2>&1
exit_code=$?
set -e

if [[ "$exit_code" -ne 0 ]]; then
  echo "dream failed: codex exit ${exit_code}. log: memory/dreams/${stamp}-events.jsonl"
  exit "$exit_code"
fi

if [[ -f "$last_message_path" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$last_message_path" "$stamp" <<'PY'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
stamp = sys.argv[2]
text = path.read_text(encoding="utf-8").strip()
if len(text) > 1200:
    text = text[:1200] + f"\n...(truncated; see memory/dreams/{stamp}-last-message.md)"
print(text)
PY
  else
    head -c 1200 "$last_message_path"
  fi
else
  echo "dream complete. event log: memory/dreams/${stamp}-events.jsonl"
fi

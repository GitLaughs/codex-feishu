#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
guide_path="${workspace}/local_files/docs/help-guide.md"
audit_path="${workspace}/memory/lark-audit.jsonl"

if [[ ! -f "$guide_path" ]]; then
  echo "help guide missing: $guide_path" >&2
  exit 1
fi

mkdir -p "$(dirname "$audit_path")"
printf '{"time":"%s","action":"help_display","project":"%s","session":"%s"}\n' \
  "$(date -Is)" "${CC_HOOK_PROJECT:-}" "${CC_HOOK_SESSION_KEY:-}" >>"$audit_path"

cat "$guide_path"

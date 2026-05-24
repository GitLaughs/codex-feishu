#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/opt/codex-feishu}"
MIN_INTERVAL_SECONDS="${CODEX_FEISHU_REINDEX_MIN_INTERVAL_SECONDS:-300}"
FORCE="${CODEX_FEISHU_REINDEX_FORCE:-0}"

STAMP_DIR="$ROOT/memory/search"
STAMP_FILE="$STAMP_DIR/last-reindex.txt"
LOCK_FILE="$STAMP_DIR/reindex.lock"
LOG_FILE="$STAMP_DIR/reindex.log"
mkdir -p "$STAMP_DIR"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG_FILE"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Skip reindex: lock is held."
  log "skip locked root=$ROOT"
  exit 0
fi

now="$(date +%s)"
if [[ "$FORCE" != "1" && -f "$STAMP_FILE" ]]; then
  last="$(cat "$STAMP_FILE" || true)"
  if [[ "$last" =~ ^[0-9]+$ ]]; then
    age=$((now - last))
    if (( age < MIN_INTERVAL_SECONDS )); then
      echo "Skip reindex: last run ${age}s ago (< ${MIN_INTERVAL_SECONDS}s)."
      log "skip interval age=${age} min=${MIN_INTERVAL_SECONDS} root=$ROOT"
      exit 0
    fi
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
start="$now"
log "start root=$ROOT force=$FORCE"
set +e
python3 "$SCRIPT_DIR/codex-feishu-index.py" --root "$ROOT" reindex
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  log "failed exit=$rc root=$ROOT"
  exit "$rc"
fi
printf '%s\n' "$now" > "$STAMP_FILE"
elapsed=$(($(date +%s) - start))
log "ok elapsed=${elapsed}s root=$ROOT"

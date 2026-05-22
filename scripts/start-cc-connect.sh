#!/usr/bin/env bash
set -u

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_path="${HOME}/.cc-connect/config.toml"
log_path=""
restart_delay=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --config|--config-path) config_path="$2"; shift 2 ;;
    --log|--log-path) log_path="$2"; shift 2 ;;
    --restart-delay) restart_delay="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$log_path" ]]; then
  log_path="${root}/cc-connect-run.log"
fi

cc_connect="$(command -v cc-connect || true)"
if [[ -z "$cc_connect" ]]; then
  echo "cc-connect not found in PATH" >&2
  exit 127
fi

mkdir -p "$(dirname "$log_path")"
cd "$root" || exit 1

while true; do
  {
    echo ""
    echo "==== cc-connect start $(date -Is) ===="
  } >>"$log_path"

  "$cc_connect" --config "$config_path" --force 2>&1 | tee -a "$log_path"
  exit_code=${PIPESTATUS[0]}

  echo "==== cc-connect exited code=${exit_code} $(date -Is); restart in ${restart_delay}s ====" >>"$log_path"
  sleep "$restart_delay"
done

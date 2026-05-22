#!/usr/bin/env bash
set -euo pipefail

service_name="codex-feishu-cc-connect"
config_path="${HOME}/.cc-connect/config.toml"
log_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service-name) service_name="$2"; shift 2 ;;
    --config|--config-path) config_path="$2"; shift 2 ;;
    --log|--log-path) log_path="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$log_path" ]]; then
  log_path="${PWD}/cc-connect-watchdog.log"
fi

mkdir -p "$(dirname "$log_path")"
write_log() {
  echo "$(date -Is) $*" >>"$log_path"
}

if pgrep -af "cc-connect.*${config_path}" >/dev/null 2>&1; then
  write_log "ok process_found service=${service_name}"
  exit 0
fi

write_log "cc-connect missing; restarting user service ${service_name}"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user restart "${service_name}.service" || {
    write_log "systemctl restart failed"
    exit 1
  }
else
  write_log "systemctl not found"
  exit 1
fi

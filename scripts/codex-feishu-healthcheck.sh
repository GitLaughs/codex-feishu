#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${OPENCLAW_ROOT:-/opt/openclaw}"
LOG_FILE="${OPENCLAW_HEALTH_LOG:-/var/log/openclaw-health.log}"
CC_LOG="${OPENCLAW_CC_LOG:-/var/log/cc-connect.log}"
MIN_AVAILABLE_MB="${OPENCLAW_MIN_AVAILABLE_MB:-300}"
MAX_DISK_USE_PCT="${OPENCLAW_MAX_DISK_USE_PCT:-80}"
EXPECTED_PROJECTS="${OPENCLAW_EXPECTED_PROJECTS:-9}"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//'
}

failures=()
add_failure() {
  failures+=("$1")
}

service_state() {
  systemctl is-active "$1" 2>/dev/null || true
}

cc_state="$(service_state cc-connect.service)"
mimo_state="$(service_state mimo-responses-proxy.service)"
watchdog_timer="$(service_state codex-failure-watchdog.timer)"
rotate_timer="$(service_state codex-balance-rotate.timer)"

[[ "$cc_state" == "active" ]] || add_failure "cc-connect.service is $cc_state"
[[ "$mimo_state" == "active" ]] || add_failure "mimo-responses-proxy.service is $mimo_state"
[[ "$watchdog_timer" == "active" ]] || add_failure "codex-failure-watchdog.timer is $watchdog_timer"
[[ "$rotate_timer" == "active" ]] || add_failure "codex-balance-rotate.timer is $rotate_timer"
[[ -d "$PROJECT_ROOT" ]] || add_failure "missing project root: $PROJECT_ROOT"

project_count="unknown"
if [[ -f "$CC_LOG" ]]; then
  project_count="$(grep -ao 'cc-connect is running" projects=[0-9]\+' "$CC_LOG" | tail -1 | sed -E 's/.*projects=([0-9]+)/\1/' || true)"
  [[ -n "$project_count" ]] || project_count="unknown"
  if [[ "$project_count" != "$EXPECTED_PROJECTS" ]]; then
    add_failure "expected projects=$EXPECTED_PROJECTS got=$project_count"
  fi
  recent_errors="$(tail -n 500 "$CC_LOG" | grep -Eic 'error|failed|panic|timeout|quota|rate limit' || true)"
else
  recent_errors="unknown"
  add_failure "missing cc-connect log: $CC_LOG"
fi

disk_use="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
if [[ -n "$disk_use" && "$disk_use" -gt "$MAX_DISK_USE_PCT" ]]; then
  add_failure "disk usage ${disk_use}% > ${MAX_DISK_USE_PCT}%"
fi

available_mb="$(awk '/MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo)"
if [[ -n "$available_mb" && "$available_mb" -lt "$MIN_AVAILABLE_MB" ]]; then
  add_failure "available memory ${available_mb}MiB < ${MIN_AVAILABLE_MB}MiB"
fi

ok=false
if [[ "${#failures[@]}" -eq 0 ]]; then
  ok=true
fi

failure_json="$(printf '%s\n' "${failures[@]}" | sed '/^$/d' | awk 'BEGIN{printf "["} {gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); printf "%s\"%s\"", sep, $0; sep=","} END{printf "]"}')"

report="$(cat <<JSON
{
  "time": "$(date -Is)",
  "ok": $ok,
  "services": {
    "cc_connect": "$cc_state",
    "mimo_responses_proxy": "$mimo_state",
    "codex_failure_watchdog_timer": "$watchdog_timer",
    "codex_balance_rotate_timer": "$rotate_timer"
  },
  "cc_connect": {
    "expected_projects": $EXPECTED_PROJECTS,
    "observed_projects": "$(json_escape "$project_count")",
    "recent_error_lines": "$(json_escape "$recent_errors")"
  },
  "resources": {
    "disk_use_percent": "$(json_escape "$disk_use")",
    "mem_available_mb": "$(json_escape "$available_mb")"
  },
  "failures": $failure_json
}
JSON
)"

mkdir -p "$(dirname "$LOG_FILE")"
printf '%s\n' "$report" | tee -a "$LOG_FILE"

if [[ "$ok" != "true" ]]; then
  exit 1
fi


#!/usr/bin/env bash
set -euo pipefail

verify=0
if [[ "${1:-}" == "--verify" ]]; then
  verify=1
fi

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//'
}

command_json() {
  local name="$1"
  local source=""
  local version=""
  if source="$(command -v "$name" 2>/dev/null)"; then
    case "$name" in
      node) version="$(node --version 2>/dev/null || true)" ;;
      npm) version="$(npm --version 2>/dev/null || true)" ;;
      lark-cli) version="$(lark-cli --version 2>/dev/null || true)" ;;
    esac
    printf '{"name":"%s","ok":true,"source":"%s","version":"%s"}' "$name" "$(json_escape "$source")" "$(json_escape "$version")"
  else
    printf '{"name":"%s","ok":false,"source":null,"version":null}' "$name"
  fi
}

latest=""
if command -v npm >/dev/null 2>&1; then
  latest="$(npm view @larksuite/cli version 2>/dev/null || true)"
fi

auth_output=""
auth_exit=127
if command -v lark-cli >/dev/null 2>&1; then
  set +e
  if [[ "$verify" -eq 1 ]]; then
    auth_output="$(lark-cli auth status --verify 2>&1)"
  else
    auth_output="$(lark-cli auth status 2>&1)"
  fi
  auth_exit=$?
  set -e
fi

redacted="$(printf '%s' "$auth_output" | sed -E 's/("(appSecret|accessToken|refreshToken|token)"[[:space:]]*:[[:space:]]*")[^"]+/\1<redacted>/Ig')"

printf '{'
printf '"checked_at":"%s",' "$(date -Is)"
printf '"commands":[%s,%s,%s],' "$(command_json node)" "$(command_json npm)" "$(command_json lark-cli)"
printf '"lark_cli_latest_npm":"%s",' "$(json_escape "$latest")"
if [[ "$auth_exit" -eq 0 ]]; then
  printf '"auth_ok":true,'
else
  printf '"auth_ok":false,'
fi
printf '"auth_exit_code":%s,' "$auth_exit"
printf '"auth_status_raw":"%s"' "$(json_escape "$redacted")"
printf '}\n'

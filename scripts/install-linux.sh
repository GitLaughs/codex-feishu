#!/usr/bin/env bash
set -euo pipefail

install_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_path="${HOME}/.cc-connect/config.toml"
workspace_path=""
service_name="codex-feishu-cc-connect"
group_chat_id=""
mini_project=""
deep_project=""
admin_open_id=""
mini_model=""
mini_effort=""
mini_ignore_bot_mentions=""
mini_trigger_threshold=""
deep_model=""
deep_effort=""
deep_instant_ack_text=""
dream_model=""
dream_effort=""
codex_mode=""
mini_app_id=""
mini_app_secret=""
deep_app_id=""
deep_app_secret=""
no_systemd=0
enable_family_memory=0
enable_codex_balance_rotate=0
codex_rotate_service_name="codex-feishu-codex-balance-rotate"
codex_rotate_db_path="${HOME}/.cc-switch/cc-switch.db"
codex_rotate_env_path=""
codex_rotate_auth_path="${HOME}/.codex/auth.json"
codex_rotate_config_path="${HOME}/.codex/config.toml"
codex_rotate_fallback_file="${HOME}/.cc-switch/codex-fallback-providers.json"
codex_rotate_interval="*:0/30"
codex_rotate_min_balance="0"
codex_rotate_extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) install_root="$2"; shift 2 ;;
    --config-path) config_path="$2"; shift 2 ;;
    --workspace-path) workspace_path="$2"; shift 2 ;;
    --service-name) service_name="$2"; shift 2 ;;
    --group-chat-id) group_chat_id="$2"; shift 2 ;;
    --mini-project) mini_project="$2"; shift 2 ;;
    --deep-project) deep_project="$2"; shift 2 ;;
    --admin-open-id) admin_open_id="$2"; shift 2 ;;
    --mini-model) mini_model="$2"; shift 2 ;;
    --mini-effort) mini_effort="$2"; shift 2 ;;
    --mini-ignore-bot-mentions) mini_ignore_bot_mentions="$2"; shift 2 ;;
    --mini-trigger-threshold) mini_trigger_threshold="$2"; shift 2 ;;
    --deep-model) deep_model="$2"; shift 2 ;;
    --deep-effort) deep_effort="$2"; shift 2 ;;
    --deep-instant-ack-text) deep_instant_ack_text="$2"; shift 2 ;;
    --dream-model) dream_model="$2"; shift 2 ;;
    --dream-effort) dream_effort="$2"; shift 2 ;;
    --codex-mode) codex_mode="$2"; shift 2 ;;
    --mini-app-id) mini_app_id="$2"; shift 2 ;;
    --mini-app-secret) mini_app_secret="$2"; shift 2 ;;
    --deep-app-id) deep_app_id="$2"; shift 2 ;;
    --deep-app-secret) deep_app_secret="$2"; shift 2 ;;
    --no-systemd) no_systemd=1; shift ;;
    --enable-family-memory) enable_family_memory=1; shift ;;
    --enable-codex-balance-rotate) enable_codex_balance_rotate=1; shift ;;
    --codex-rotate-service-name) codex_rotate_service_name="$2"; shift 2 ;;
    --codex-rotate-db-path) codex_rotate_db_path="$2"; shift 2 ;;
    --codex-rotate-env-path) codex_rotate_env_path="$2"; shift 2 ;;
    --codex-rotate-auth-path) codex_rotate_auth_path="$2"; shift 2 ;;
    --codex-rotate-config-path) codex_rotate_config_path="$2"; shift 2 ;;
    --codex-rotate-fallback-file) codex_rotate_fallback_file="$2"; shift 2 ;;
    --codex-rotate-interval) codex_rotate_interval="$2"; shift 2 ;;
    --codex-rotate-min-balance) codex_rotate_min_balance="$2"; shift 2 ;;
    --codex-rotate-no-warmup) codex_rotate_extra_args+=("--no-warmup"); shift ;;
    --codex-rotate-exclude-current) codex_rotate_extra_args+=("--exclude-current"); shift ;;
    --codex-rotate-force-fallback) codex_rotate_extra_args+=("--force-fallback"); shift ;;
    -h|--help) sed -n '1,140p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

read_value() {
  local prompt="$1"
  local default="${2:-}"
  local required="${3:-0}"
  local value=""
  while true; do
    if [[ -n "$default" ]]; then
      read -r -p "${prompt} [${default}]: " value
    else
      read -r -p "${prompt}: " value
    fi
    if [[ -z "$value" ]]; then
      value="$default"
    fi
    if [[ "$required" != "1" || -n "$value" ]]; then
      printf '%s' "$value"
      return
    fi
    echo "Value is required." >&2
  done
}

read_secret() {
  local prompt="$1"
  local value=""
  read -r -s -p "${prompt}: " value
  echo >&2
  printf '%s' "$value"
}

toml_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

systemd_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

replace_token() {
  local content="$1"
  local token="$2"
  local value="$3"
  printf '%s' "${content//${token}/${value}}"
}

toml_array_line() {
  local key="$1"
  local csv="$2"
  local line=""
  local item=""
  IFS=',' read -r -a items <<<"$csv"
  for item in "${items[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [[ -n "$item" ]] || continue
    if [[ -n "$line" ]]; then
      line+=", "
    fi
    line+="\"$(toml_escape "$item")\""
  done
  if [[ -n "$line" ]]; then
    printf '%s = [%s]' "$key" "$line"
  fi
}

toml_string_line() {
  local key="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    printf '%s = "%s"' "$key" "$(toml_escape "$value")"
  fi
}

write_file() {
  local path="$1"
  local content="$2"
  mkdir -p "$(dirname "$path")"
  printf '%s' "$content" >"$path"
}

install_root="$(cd "$install_root" && pwd)"
if [[ -z "$workspace_path" ]]; then
  workspace_path="${install_root}/workspace"
fi
if [[ -z "$codex_rotate_env_path" ]]; then
  codex_rotate_env_path="${install_root}/codex.env"
fi

echo "codex-feishu Linux installer"
echo "Install root: ${install_root}"
echo "Config path:  ${config_path}"
echo ""
echo "Feishu permission templates:"
echo "  Mini app: ${install_root}/templates/feishu-mini-scopes.json"
echo "  Deep app: ${install_root}/templates/feishu-deep-scopes.json"
echo "Before testing, import these in Feishu Open Platform -> App -> Permissions, then create and publish a new version."
echo "Mini includes im:message.group_msg for all group messages; deep intentionally does not."
echo ""

[[ -n "$group_chat_id" ]] || group_chat_id="$(read_value "Feishu group chat_id (oc_xxx)" "" 1)"
[[ -n "$mini_project" ]] || mini_project="$(read_value "Mini project name" "feishu-mini" 1)"
[[ -n "$deep_project" ]] || deep_project="$(read_value "Deep project name" "feishu-deep" 1)"
[[ -n "$admin_open_id" ]] || admin_open_id="$(read_value "Admin open_id (optional; use * to skip group admin)" "*" 0)"
[[ -n "$mini_model" ]] || mini_model="$(read_value "Mini model" "gpt-5.4-mini" 1)"
[[ -n "$mini_effort" ]] || mini_effort="$(read_value "Mini reasoning effort" "medium" 1)"
[[ -n "$mini_trigger_threshold" ]] || mini_trigger_threshold="$(read_value "Mini reply trigger threshold (relaxed/medium/strict)" "strict" 1)"
[[ -n "$deep_model" ]] || deep_model="$(read_value "Deep model" "gpt-5.5" 1)"
[[ -n "$deep_effort" ]] || deep_effort="$(read_value "Deep reasoning effort" "high" 1)"
[[ -n "$dream_model" ]] || dream_model="$(read_value "Dream command model" "$deep_model" 1)"
[[ -n "$dream_effort" ]] || dream_effort="$(read_value "Dream command reasoning effort" "xhigh" 1)"
[[ -n "$codex_mode" ]] || codex_mode="$(read_value "Codex mode" "yolo" 1)"
workspace_path="$(readlink -m "$workspace_path")"

echo ""
echo "Mini Feishu app credentials"
[[ -n "$mini_app_id" ]] || mini_app_id="$(read_value "Mini app_id" "" 1)"
[[ -n "$mini_app_secret" ]] || mini_app_secret="$(read_secret "Mini app_secret")"

echo ""
echo "Deep Feishu app credentials"
[[ -n "$deep_app_id" ]] || deep_app_id="$(read_value "Deep app_id" "" 1)"
[[ -n "$deep_app_secret" ]] || deep_app_secret="$(read_secret "Deep app_secret")"

mkdir -p "$(dirname "$config_path")"
mkdir -p "$workspace_path/scripts"
for folder in daily facts inbox people projects reviews search tasks dreams lark-events; do
  mkdir -p "$workspace_path/memory/$folder"
done
for file_name in open.md done.md; do
  task_path="$workspace_path/memory/tasks/$file_name"
  if [[ ! -f "$task_path" ]]; then
    printf '# %s\n' "$file_name" >"$task_path"
  fi
done
for folder in incoming docs data media code assets; do
  mkdir -p "$workspace_path/local_files/$folder"
done

index_path="$workspace_path/local_files/INDEX.md"
if [[ ! -f "$index_path" ]]; then
  cat >"$index_path" <<'EOF'
# Local File Index

| Date | Name | Path | Type | Notes |
|---|---|---|---|---|
| generated | help-guide.md | `local_files/docs/help-guide.md` | docs | Static command guide |
EOF
fi

knowledge_path="$workspace_path/KNOWLEDGE.md"
if [[ ! -f "$knowledge_path" ]]; then
  printf '# Knowledge\n' >"$knowledge_path"
fi

for script_name in import-local-file.sh lark-download-resource.sh lark-health.sh lark-event-listener.sh help.sh dream.sh generate-image.js codex-feishu-index.py codex-feishu-command.py codex-feishu-health-command.py codex-feishu-file-health.py codex-feishu-memory-health.py codex-feishu-manifest-health.py codex-feishu-help-health.py codex-feishu-redact-runs.py codex-feishu-reindex.sh test-codex-feishu-command-isolation.py; do
  cp "$install_root/scripts/$script_name" "$workspace_path/scripts/$script_name"
  chmod +x "$workspace_path/scripts/$script_name" 2>/dev/null || true
done
if [[ "$enable_family_memory" -eq 1 ]]; then
  for script_name in family-memory-capture.py family-memory-capture.ps1 cc-connect-memory-hook.sh test-family-memory.ps1 test-family-memory-hook.ps1; do
    cp "$install_root/scripts/$script_name" "$workspace_path/scripts/$script_name"
  done
  chmod +x "$workspace_path/scripts/cc-connect-memory-hook.sh" "$workspace_path/scripts/family-memory-capture.py" 2>/dev/null || true
  mkdir -p "$workspace_path/memory/messages" "$workspace_path/memory/people" "$workspace_path/memory/family" "$workspace_path/memory/summaries"
fi
chmod +x "$install_root/scripts/codex-balance-rotate.py" 2>/dev/null || true

instructions="$(<"$install_root/templates/INSTRUCTIONS.md")"
instructions="$(replace_token "$instructions" "__MINI_PROJECT__" "$mini_project")"
instructions="$(replace_token "$instructions" "__DEEP_PROJECT__" "$deep_project")"
instructions="$(replace_token "$instructions" "__MINI_MODEL__" "$mini_model")"
instructions="$(replace_token "$instructions" "__MINI_TRIGGER_THRESHOLD__" "$mini_trigger_threshold")"
instructions="$(replace_token "$instructions" "__DEEP_MODEL__" "$deep_model")"
write_file "$workspace_path/INSTRUCTIONS.md" "$instructions"

agents="$(<"$install_root/templates/AGENTS.md")"
agents="$(replace_token "$agents" "__WORKSPACE__" "$workspace_path")"
agents="$(replace_token "$agents" "__MINI_PROJECT__" "$mini_project")"
agents="$(replace_token "$agents" "__DEEP_PROJECT__" "$deep_project")"
agents="$(replace_token "$agents" "__MINI_MODEL__" "$mini_model")"
agents="$(replace_token "$agents" "__DREAM_MODEL__" "$dream_model")"
agents="$(replace_token "$agents" "__DREAM_EFFORT__" "$dream_effort")"
write_file "$workspace_path/AGENTS.md" "$agents"

dream_prompt="$(<"$install_root/templates/dream_prompt.md")"
dream_prompt="$(replace_token "$dream_prompt" "__WORKSPACE__" "$workspace_path")"
write_file "$workspace_path/scripts/dream_prompt.md" "$dream_prompt"

cp "$install_root/templates/help-guide.md" "$workspace_path/local_files/docs/help-guide.md"

workspace_name="$(basename "$workspace_path")"
manifest="$(<"$install_root/templates/workspace_manifest.json")"
manifest="$(replace_token "$manifest" "__WORKSPACE_NAME__" "$workspace_name")"
manifest="$(replace_token "$manifest" "__WORKSPACE__" "$workspace_path")"
manifest="$(replace_token "$manifest" "__MINI_PROJECT__" "$mini_project")"
manifest="$(replace_token "$manifest" "__DEEP_PROJECT__" "$deep_project")"
manifest="$(replace_token "$manifest" "__MINI_MODEL__" "$mini_model")"
manifest="$(replace_token "$manifest" "__DEEP_MODEL__" "$deep_model")"
write_file "$workspace_path/workspace_manifest.json" "$manifest"

group_admin_line=""
if [[ -n "$admin_open_id" && "$admin_open_id" != "*" ]]; then
  group_admin_line="admin_from = \"$(toml_escape "$admin_open_id")\""
fi
mini_ignore_bot_mentions_line="$(toml_array_line "ignore_bot_mentions" "$mini_ignore_bot_mentions")"
deep_instant_ack_line="$(toml_string_line "instant_ack_text" "$deep_instant_ack_text")"
family_memory_hook_block=""
if [[ "$enable_family_memory" -eq 1 ]]; then
  family_memory_projects="$(toml_escape "${mini_project},${deep_project}")"
  family_memory_hook_block="$(cat <<EOF
[[hooks]]
event = "message.received"
type = "command"
command = "FAMILY_MEMORY_WORKSPACE=\"$(toml_escape "$workspace_path")\" FAMILY_MEMORY_PROJECTS=\"${family_memory_projects}\" bash \"$(toml_escape "$workspace_path")/scripts/cc-connect-memory-hook.sh\""
async = true
timeout = 8
EOF
)"
fi

config="$(<"$install_root/templates/config.double-bot.linux.toml")"
config="$(replace_token "$config" "__INSTALL_ROOT__" "$(toml_escape "$install_root")")"
config="$(replace_token "$config" "__WORKSPACE__" "$(toml_escape "$workspace_path")")"
config="$(replace_token "$config" "__GROUP_CHAT_ID__" "$(toml_escape "$group_chat_id")")"
config="$(replace_token "$config" "__MINI_PROJECT__" "$(toml_escape "$mini_project")")"
config="$(replace_token "$config" "__DEEP_PROJECT__" "$(toml_escape "$deep_project")")"
config="$(replace_token "$config" "__CODEX_MODE__" "$(toml_escape "$codex_mode")")"
config="$(replace_token "$config" "__MINI_MODEL__" "$(toml_escape "$mini_model")")"
config="$(replace_token "$config" "__MINI_EFFORT__" "$(toml_escape "$mini_effort")")"
config="$(replace_token "$config" "__DEEP_MODEL__" "$(toml_escape "$deep_model")")"
config="$(replace_token "$config" "__DEEP_EFFORT__" "$(toml_escape "$deep_effort")")"
config="$(replace_token "$config" "__GROUP_ADMIN_LINE__" "$group_admin_line")"
config="$(replace_token "$config" "__MINI_IGNORE_BOT_MENTIONS_LINE__" "$mini_ignore_bot_mentions_line")"
config="$(replace_token "$config" "__DEEP_INSTANT_ACK_LINE__" "$deep_instant_ack_line")"
config="$(replace_token "$config" "__FAMILY_MEMORY_HOOK_BLOCK__" "$family_memory_hook_block")"
config="$(replace_token "$config" "__MINI_APP_ID__" "$(toml_escape "$mini_app_id")")"
config="$(replace_token "$config" "__MINI_APP_SECRET__" "$(toml_escape "$mini_app_secret")")"
config="$(replace_token "$config" "__DEEP_APP_ID__" "$(toml_escape "$deep_app_id")")"
config="$(replace_token "$config" "__DEEP_APP_SECRET__" "$(toml_escape "$deep_app_secret")")"

if [[ -f "$config_path" ]]; then
  backup_path="${config_path}.bak-$(date +%Y%m%d-%H%M%S)"
  cp "$config_path" "$backup_path"
  echo "Backed up existing config to $backup_path"
fi
write_file "$config_path" "$config"
echo "Wrote cc-connect config: $config_path"

if [[ "$no_systemd" -ne 1 ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    service_dir="${HOME}/.config/systemd/user"
    mkdir -p "$service_dir"
    service_path="${service_dir}/${service_name}.service"
    cat >"$service_path" <<EOF
[Unit]
Description=codex-feishu cc-connect runner
After=network-online.target

[Service]
Type=simple
WorkingDirectory=${install_root}
ExecStart=/usr/bin/env bash ${install_root}/scripts/start-cc-connect.sh --root ${install_root} --config ${config_path} --log ${install_root}/cc-connect-run.log
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now "${service_name}.service"
    echo "Registered and started systemd user service: ${service_name}.service"

    if [[ "$enable_codex_balance_rotate" -eq 1 ]]; then
      rotate_service_path="${service_dir}/${codex_rotate_service_name}.service"
      rotate_timer_path="${service_dir}/${codex_rotate_service_name}.timer"
      mkdir -p "$(dirname "$codex_rotate_env_path")" "$(dirname "$codex_rotate_auth_path")" "$(dirname "$codex_rotate_config_path")" "$(dirname "$codex_rotate_fallback_file")"
      codex_rotate_extra=""
      if [[ "${#codex_rotate_extra_args[@]}" -gt 0 ]]; then
        for arg in "${codex_rotate_extra_args[@]}"; do
          codex_rotate_extra+=" ${arg}"
        done
      fi
      cat >"$rotate_service_path" <<EOF
[Unit]
Description=codex-feishu Codex API balance rotation
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 "$(systemd_escape "$install_root")/scripts/codex-balance-rotate.py" --db "$(systemd_escape "$codex_rotate_db_path")" --env "$(systemd_escape "$codex_rotate_env_path")" --auth "$(systemd_escape "$codex_rotate_auth_path")" --codex-config "$(systemd_escape "$codex_rotate_config_path")" --fallback-file "$(systemd_escape "$codex_rotate_fallback_file")" --min-balance ${codex_rotate_min_balance}${codex_rotate_extra}
EOF
      cat >"$rotate_timer_path" <<EOF
[Unit]
Description=Run codex-feishu Codex API balance rotation

[Timer]
OnBootSec=2min
OnCalendar=${codex_rotate_interval}
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
EOF
      systemctl --user daemon-reload
      systemctl --user enable --now "${codex_rotate_service_name}.timer"
      echo "Registered Codex balance rotation timer: ${codex_rotate_service_name}.timer"
    fi
  else
    echo "systemctl not found; run scripts/start-cc-connect.sh manually or use --no-systemd" >&2
  fi
fi

echo ""
echo "Next steps:"
echo "1. Feishu console: open https://open.feishu.cn/app/<app_id> for each app."
echo "2. Permissions: import templates/feishu-mini-scopes.json into mini and templates/feishu-deep-scopes.json into deep."
echo "3. Events: subscribe both apps to im.message.receive_v1; only mini should have all-message group receive."
echo "4. Version: create and publish a new app version after permission changes."
echo "5. Invite both bots to the group."
echo "6. Send a normal group message to test mini monitoring."
echo "7. @ the deep bot to test deep routing."

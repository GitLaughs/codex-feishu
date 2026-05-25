#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=()

add_failure() {
  failures+=("$1")
}

echo "== Bash parse check =="
while IFS= read -r -d '' file; do
  if bash -n "$file"; then
    echo "OK   ${file#$root/}"
  else
    echo "FAIL ${file#$root/}"
    add_failure "Bash parser errors in ${file#$root/}"
  fi
done < <(find "$root/scripts" -name '*.sh' -type f -print0)

echo "== Secret and local-data scan =="
patterns=(
  "aa854"
  "aa9afa"
  "9yOJ"
  "1QOdx"
  "ou_[a-z0-9]{10,}"
  "oc_c175"
  "OPEN""CLAW"
  "mini_secret_test"
  "deep_secret_test"
)

for pattern in "${patterns[@]}"; do
  if grep -RIE --exclude-dir=.git --exclude-dir=.tmp --exclude='*.png' --exclude='*.jpg' --exclude='test-linux.sh' "$pattern" "$root" >/tmp/codex-feishu-grep.$$ 2>/dev/null; then
    add_failure "Sensitive/local pattern found: $pattern"
    cat /tmp/codex-feishu-grep.$$
  fi
  rm -f /tmp/codex-feishu-grep.$$
done

echo "== Linux install smoke test =="
tmp="$root/.tmp/linux-test"
rm -rf "$tmp"
mkdir -p "$tmp"

python_bin=""
if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
  python_bin="python"
else
  add_failure "python not found; deterministic command scripts require Python."
fi

bash "$root/scripts/install-linux.sh" \
  --install-root "$root" \
  --config-path "$tmp/config.toml" \
  --workspace-path "$tmp/workspace" \
  --group-chat-id "oc_test" \
  --mini-project "feishu-mini" \
  --deep-project "feishu-deep" \
  --admin-open-id "*" \
  --mini-model "gpt-5.4-mini" \
  --mini-effort "medium" \
  --mini-ignore-bot-mentions "feishu-deep,ou_deep" \
  --mini-trigger-threshold "strict" \
  --deep-model "gpt-5.5" \
  --deep-effort "high" \
  --dream-model "gpt-5.5" \
  --dream-effort "xhigh" \
  --codex-mode "yolo" \
  --mini-app-id "cli_mini" \
  --mini-app-secret "fake-mini-secret" \
  --deep-app-id "cli_deep" \
  --deep-app-secret "fake-deep-secret" \
  --enable-family-memory \
  --no-systemd >/dev/null

[[ -f "$tmp/config.toml" ]] || add_failure "Linux install did not generate config."
grep -q 'name = "help"' "$tmp/config.toml" || add_failure "Linux install did not generate /help command."
grep -q 'name = "dream"' "$tmp/config.toml" || add_failure "Linux install did not generate /dream command."
for command_name in files memfind knowledge tasks task workspace-info status-index health-codex-feishu; do
  grep -q "name = \"${command_name}\"" "$tmp/config.toml" || add_failure "Linux install did not generate /${command_name} command."
done
grep -q 'disabled_commands = \["dir", "shell", "restart", "upgrade", "cron", "commands", "provider"\]' "$tmp/config.toml" || add_failure "Linux install did not disable privileged group commands."
if grep -q 'admin_from = "\*"' "$tmp/config.toml"; then
  add_failure "Linux install should not grant wildcard group admin privileges."
fi
grep -q 'ignore_bot_mentions = \["feishu-deep", "ou_deep"\]' "$tmp/config.toml" || add_failure "Linux install did not generate mini ignored bot mention routing guard."
if grep -q 'instant_ack_text = ' "$tmp/config.toml"; then
  add_failure "Linux install should not generate text instant ack by default."
fi
grep -q 'reaction_emoji = "OnIt"' "$tmp/config.toml" || add_failure "Linux install did not enable OnIt reaction emoji."
grep -q 'image_command_enabled = true' "$tmp/config.toml" || add_failure "Linux install did not enable platform image commands."
grep -q 'generate-image.js' "$tmp/config.toml" || add_failure "Linux install did not configure the image generation helper."
grep -q 'cc-connect-memory-hook.sh' "$tmp/config.toml" || add_failure "Linux install did not generate optional family memory hook."
grep -q 'cc-connect-lark-events-hook.py' "$tmp/config.toml" || add_failure "Linux install did not generate lark event capture hook."
[[ -f "$tmp/workspace/AGENTS.md" ]] || add_failure "Linux install did not generate AGENTS.md."
[[ -f "$tmp/workspace/INSTRUCTIONS.md" ]] || add_failure "Linux install did not generate INSTRUCTIONS.md."
[[ -f "$tmp/workspace/workspace_manifest.json" ]] || add_failure "Linux install did not generate workspace manifest."
[[ -f "$tmp/workspace/scripts/dream_prompt.md" ]] || add_failure "Linux install did not generate dream prompt."
[[ -f "$tmp/workspace/local_files/docs/help-guide.md" ]] || add_failure "Linux install did not generate help guide."
[[ -f "$tmp/workspace/scripts/import-local-file.sh" ]] || add_failure "Linux install did not copy import-local-file.sh."
[[ -f "$tmp/workspace/scripts/generate-image.js" ]] || add_failure "Linux install did not copy generate-image.js."
[[ -f "$tmp/workspace/scripts/family-memory-capture.py" ]] || add_failure "Linux install did not copy family-memory-capture.py."
[[ -f "$tmp/workspace/scripts/cc-connect-memory-hook.sh" ]] || add_failure "Linux install did not copy cc-connect-memory-hook.sh."
for script_name in codex-feishu-index.py codex-feishu-command.py codex-feishu-health-command.py codex-feishu-file-health.py codex-feishu-memory-health.py codex-feishu-manifest-health.py codex-feishu-help-health.py codex-feishu-redact-runs.py codex-feishu-reindex.sh memory-recall.ps1 task-agent.py create-feishu-reminder.py delete-feishu-reminder.py memory-curator.py capture-private-message.py cc-connect-lark-events-hook.py codex-feishu-group-sense.py codex-feishu-heartbeat-sense.py build-feishu-private-packet.py build-feishu-group-packet.py build-feishu-dream-packet.py build-feishu-recall-packet.py test-codex-feishu-command-isolation.py; do
  [[ -f "$tmp/workspace/scripts/$script_name" ]] || add_failure "Linux install did not copy deterministic command script $script_name."
done
for script_name in evidence_packet.py task_intent_router.py; do
  [[ -f "$tmp/workspace/scripts/lib/$script_name" ]] || add_failure "Linux install did not copy scripts/lib/$script_name."
done
[[ -d "$tmp/workspace/memory/family" ]] || add_failure "Linux install did not create family memory folder."

if [[ -n "$python_bin" ]]; then
  "$python_bin" "$tmp/workspace/scripts/codex-feishu-index.py" --root "$tmp/workspace" reindex >/dev/null || add_failure "Linux deterministic reindex failed."
  "$python_bin" "$tmp/workspace/scripts/test-codex-feishu-command-isolation.py" --root "$tmp/workspace" >/dev/null || add_failure "Linux command isolation failed."
  "$python_bin" "$tmp/workspace/scripts/codex-feishu-health-command.py" --root "$tmp/workspace" | grep -q 'codex-feishu 健康：OK' || add_failure "Linux codex-feishu health command failed."
  "$python_bin" "$tmp/workspace/scripts/codex-feishu-command.py" --root "$tmp/workspace" /task preview "每天晚上9点提醒我检查服务状态" | grep -q '任务代理预览' || add_failure "Linux /task preview failed."
fi

rm -rf "$tmp"

if [[ "${#failures[@]}" -gt 0 ]]; then
  echo "== Failures =="
  printf '%s\n' "${failures[@]}"
  exit 1
fi

echo "All Linux checks passed."

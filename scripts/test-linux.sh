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
  "OPENCLAW"
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
[[ -f "$tmp/workspace/AGENTS.md" ]] || add_failure "Linux install did not generate AGENTS.md."
[[ -f "$tmp/workspace/INSTRUCTIONS.md" ]] || add_failure "Linux install did not generate INSTRUCTIONS.md."
[[ -f "$tmp/workspace/scripts/dream_prompt.md" ]] || add_failure "Linux install did not generate dream prompt."
[[ -f "$tmp/workspace/local_files/docs/help-guide.md" ]] || add_failure "Linux install did not generate help guide."
[[ -f "$tmp/workspace/scripts/import-local-file.sh" ]] || add_failure "Linux install did not copy import-local-file.sh."
[[ -f "$tmp/workspace/scripts/generate-image.js" ]] || add_failure "Linux install did not copy generate-image.js."
[[ -f "$tmp/workspace/scripts/family-memory-capture.py" ]] || add_failure "Linux install did not copy family-memory-capture.py."
[[ -f "$tmp/workspace/scripts/cc-connect-memory-hook.sh" ]] || add_failure "Linux install did not copy cc-connect-memory-hook.sh."
[[ -d "$tmp/workspace/memory/family" ]] || add_failure "Linux install did not create family memory folder."

rm -rf "$tmp"

if [[ "${#failures[@]}" -gt 0 ]]; then
  echo "== Failures =="
  printf '%s\n' "${failures[@]}"
  exit 1
fi

echo "All Linux checks passed."

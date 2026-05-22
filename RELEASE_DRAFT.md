# codex-feishu v0.2.0

Adds a Linux deployment package while preserving the existing Windows workflow.

## Highlights

- Windows PowerShell installer and hidden runner remain supported.
- New Linux installer: `scripts/install-linux.sh`.
- New Linux TOML template: `templates/config.double-bot.linux.toml`.
- New Linux helper scripts for ack, runner, `/help`, `/dream`, file import, Feishu resource download, event listening, and health checks.
- Optional systemd user service for Linux background operation.
- GitHub Actions now validates both Windows and Linux paths.

## Install

Windows:

```powershell
npm install -g cc-connect
git clone https://github.com/GitLaughs/codex-feishu.git
cd codex-feishu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Linux:

```bash
git clone https://github.com/GitLaughs/codex-feishu.git
cd codex-feishu
bash ./scripts/install-linux.sh
```

Linux non-interactive example:

```bash
bash ./scripts/install-linux.sh \
  --group-chat-id "oc_xxx" \
  --mini-project "feishu-mini" \
  --deep-project "feishu-deep" \
  --mini-model "gpt-5.4-mini" \
  --mini-effort "medium" \
  --mini-trigger-threshold "strict" \
  --deep-model "gpt-5.5" \
  --deep-effort "high" \
  --dream-model "gpt-5.5" \
  --dream-effort "xhigh" \
  --workspace-path "$HOME/codex-feishu-workspace" \
  --mini-app-id "cli_xxx" \
  --mini-app-secret "..." \
  --deep-app-id "cli_yyy" \
  --deep-app-secret "..."
```

## Feishu Console Checklist

Mini app:

- bot capability enabled;
- `im.message.receive_v1` subscribed;
- group all-message permission approved and published.

Deep app:

- bot capability enabled;
- `im.message.receive_v1` subscribed;
- invited to the target group;
- all-message permission not required.

## Verify

```powershell
cc-connect sessions list
Get-Content .\cc-connect-run.log -Tail 80
```

Expected:

- normal group messages wake the mini project;
- mini replies only when the threshold policy says the message is worth a response;
- @ mention updates the deep project;
- Feishu reply continues the matching task session;
- `/help` returns the generated static guide;
- `/dream` runs workspace maintenance from the generated workspace;
- Linux service can be inspected with `systemctl --user status codex-feishu-cc-connect.service`.

## Notes

- This is a configuration and deployment layer around `cc-connect`.
- The threshold is enforced through generated project instructions, not a new
  `cc-connect` protocol field.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Full Changelog

See `CHANGELOG.md`.

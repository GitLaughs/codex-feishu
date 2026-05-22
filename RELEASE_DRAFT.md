# codex-feishu v0.1.2

Syncs the published installer with the current local dual-bot workflow.

## Highlights

- Generated `AGENTS.md` now enforces group privacy boundaries and `NO_REPLY` silence rules.
- Mini no longer auto-acknowledges every normal group message; it says `收到` only after deciding to handle the message.
- Deep @ tasks still get immediate standalone `收到` through the hidden hook.
- Added static `/help` and `/dream` commands.
- Added Feishu/Lark helper scripts for resource download, event listening, and redacted health checks.
- Group projects disable privileged cc-connect management commands by default.

## Install

```powershell
npm install -g cc-connect
git clone https://github.com/<owner>/codex-feishu.git
cd codex-feishu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Non-interactive example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -GroupChatId "oc_xxx" `
  -MiniProject "feishu-mini" `
  -DeepProject "feishu-deep" `
  -MiniModel "gpt-5.4-mini" `
  -MiniEffort "medium" `
  -MiniTriggerThreshold "strict" `
  -DeepModel "gpt-5.5" `
  -DeepEffort "high" `
  -DreamModel "gpt-5.5" `
  -DreamEffort "xhigh" `
  -WorkspacePath "E:\FeishuCodexWorkspace" `
  -MiniAppId "cli_xxx" `
  -MiniAppSecret "..." `
  -DeepAppId "cli_yyy" `
  -DeepAppSecret "..."
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
- `/dream` runs workspace maintenance from the generated workspace.

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

# codex-feishu v0.1.1

Adds configurable `gpt-5.4-mini` reply trigger thresholds for dual-bot Feishu
group routing.

## Highlights

- New `-MiniTriggerThreshold` installer option.
- Default mini threshold is `strict`.
- `gpt-5.4-mini` now has explicit rules for relaxed, medium, and strict reply decisions.
- Casual chat and standalone question marks stay silent by default.
- File handling, explicit bot-directed work, actionable tasks, and important project context still trigger replies.

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
- Feishu reply continues the matching task session.

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

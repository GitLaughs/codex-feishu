# codex-feishu v0.1.0

First public release candidate for dual-bot Codex routing in Feishu group chats.

## Highlights

- Dual Feishu app routing:
  - mini bot monitors normal group messages;
  - deep bot handles @ mentions directly.
- Reply-chain based parallel sessions with `thread_isolation` and `reply_to_trigger`.
- Hidden Windows scheduled-task runner and watchdog.
- Hidden immediate `收到` acknowledgement hook.
- Stream preview defaults for long-running Codex replies.
- Local group workspace bootstrap with file classification and indexing.

## Install

```powershell
npm install -g cc-connect
git clone https://github.com/<owner>/codex-feishu.git
cd codex-feishu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
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

- normal group message updates the mini project;
- @ mention updates the deep project;
- Feishu reply continues the matching task session;
- hook acknowledgements do not open terminal windows.

## Known Limitations

- Windows-first release.
- Requires manual Feishu app creation and permission approval.
- Uses local scheduled tasks instead of a packaged Windows service.
- Does not ship a GUI configuration wizard yet.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Full Changelog

Initial release.

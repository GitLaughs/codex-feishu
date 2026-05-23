# codex-feishu v0.4.0

Adds an optional Feishu mention/topic route guard so an all-message mini bot can
stay silent when the deep bot is @mentioned.

## Highlights

- Windows installer now accepts `-MiniIgnoreBotMentions`.
- Linux installer now accepts `--mini-ignore-bot-mentions`.
- The generated mini Feishu platform config can include `ignore_bot_mentions = [...]`.
- In patched `cc-connect` runtimes that support this field, mini drops the root deep @ message and later replies in the same Feishu topic before `gpt-5.4-mini` runs.

## Install

Windows example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -MiniIgnoreBotMentions "feishu-deep,ou_deep_bot_open_id"
```

Linux example:

```bash
bash ./scripts/install-linux.sh \
  --mini-ignore-bot-mentions "feishu-deep,ou_deep_bot_open_id"
```

Leave the option empty for stock runtimes that do not understand this patched
platform field.

## Verify

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

Expected:

- generated config contains `ignore_bot_mentions` when the installer option is provided;
- normal dual-bot installs still work when the option is omitted;
- PowerShell parser, secret scan, and install smoke checks pass.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Full Changelog

See `CHANGELOG.md`.

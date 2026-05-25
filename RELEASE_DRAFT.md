# codex-feishu v0.8.1｜Codex 余额轮询和失败切换

Adds generic Codex provider rotation hardening for Feishu/Lark group bots, without publishing local provider names, keys, or machine paths.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、Codex 余额轮询、失败切换、fallback provider、cc-connect 部署。

## Highlights

- `codex-balance-rotate.py` now supports separate primary and fallback balance thresholds.
- Fallback providers are generic OpenAI-compatible entries loaded from a local JSON file that is never committed.
- New `codex-failure-watchdog.py` watches cc-connect logs for quota, auth, rate-limit, and upstream errors, then rotates away from the current key.
- Linux installer registers the failure watchdog timer by default when balance rotation is enabled.
- Healthcheck fallback proxy service name is configurable and no longer bakes in a local provider name.
- Builds on the v0.8.0 beginner Ubuntu bootstrap path without changing its no-secrets boundary.

## Required Runtime

This release packages deployment templates and helper scripts. Codex provider rotation requires Python, a cc-switch SQLite database, and providers with compatible OpenAI-style generation plus `/v1/usage` endpoints. The failure watchdog expects systemd journal access for the cc-connect service. Bootstrap still does not write Feishu app secrets, OpenAI-compatible API keys, user IDs, group IDs, or generated cc-connect config.

## Verify

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git diff --check
```

Expected:

- PowerShell parser, Python parser, and secret/local-data scan pass.
- Windows install smoke generates workspace manifest, deterministic command config, reindex output, command isolation, and health checks.
- Linux install checks run when a usable bash exists; otherwise they are skipped by the Windows test wrapper.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

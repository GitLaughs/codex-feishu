# codex-feishu v0.7.0｜飞书工作区检索和健康检查

Adds deterministic read-only workspace commands, generated workspace manifests, and local health checks for Feishu/Lark group bots.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、群聊记忆、文件检索、工作区健康检查、Codex 群机器人、cc-connect 部署。

## Highlights

- Installers now generate `workspace_manifest.json` with active commands, planned commands, data sources, guardrails, and resource policy.
- New deterministic read-only commands: `/files`, `/memfind`, `/knowledge`, `/tasks`, `/workspace-info`, `/status-index`, and `/health-codex-feishu`.
- New SQLite/FTS5 index scripts search workspace files, memory, knowledge, tasks, and manifests without invoking the model.
- New health checks cover manifest consistency, static `/help` command discovery, file index coverage, memory file health, and run-log query redaction.
- New roadmap document separates current read-only lookup from planned write commands such as `/remember draft`, `/remember approve`, and `/forget archive`.

## Required Runtime

This release packages deployment templates and helper scripts. The deterministic commands are normal cc-connect `[[commands]]` entries and require Python on the host. Image commands still require a runtime that supports Feishu `image_command_enabled`, `image_script`, `image_workspace`, `image_timeout_secs`, and `image_triggers` platform options.

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

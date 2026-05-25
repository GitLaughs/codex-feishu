# codex-feishu v0.9.0｜自然语言任务和记忆管理

Adds the core task-agent, memory-management, event-capture, and evidence-packet workflows to the public Feishu/Lark group bot release, without publishing local provider names, keys, private IDs, or machine paths.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、自然语言任务代理、群聊记忆、evidence packet、cc-connect 部署。

## Highlights

- `/task preview`, `/task run`, and `/task list` are now active commands in generated Windows and Linux configs.
- `task-agent.py` parses reminders, weekly rotas, calendar deletion, file modification, script creation, and deploy/restart requests; only low-risk structured local state is executed automatically.
- Redacted Feishu event capture writes compact group events into `memory/lark-events/` for later recall and `/dream` workflows.
- New evidence packet builders cover private memory, group memory, dream maintenance, and recall results while avoiding raw JSON/NDJSON context dumps.
- `memory-curator.py`, `codex-feishu-group-sense.py`, and `codex-feishu-heartbeat-sense.py` are included in installer-managed workspaces.
- Public docs, templates, tests, and install scripts use generic examples only.

## Required Runtime

This release packages deployment templates and helper scripts. `/task run` may write local task state and can create Feishu calendar reminders only when the local operator configures the required `lark-cli` identity. Bootstrap and installers still do not commit Feishu app secrets, OpenAI-compatible API keys, user IDs, group IDs, or generated cc-connect config.

## Verify

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git diff --check
```

Expected:

- PowerShell parser, Python parser, and secret/local-data scan pass.
- Windows install smoke generates workspace manifest, deterministic command config, `/task` config, event hook config, reindex output, command isolation, and health checks.
- Focused task-agent, private capture, event hook, and evidence packet tests pass.
- Linux install checks run when a usable bash exists; otherwise they are skipped by the Windows test wrapper.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

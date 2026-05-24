# codex-feishu v0.8.0｜Linux 新手安装和云端发行说明

Adds a beginner-friendly Ubuntu bootstrap path and release documentation for the current cloud Linux deployment baseline.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、群聊记忆、文件检索、工作区健康检查、Codex 群机器人、cc-connect 部署。

## Highlights

- New `scripts/bootstrap-linux.sh` prepares a fresh Ubuntu host for codex-feishu.
- Bootstrap installs apt dependencies, optional swap, Node.js 22, pinned `@openai/codex@0.133.0`, and pinned `cc-connect@1.3.3-beta.2`.
- Bootstrap can clone or update `https://github.com/GitLaughs/codex-feishu.git`, then hands off to `scripts/install-linux.sh`.
- Linux install docs now separate host bootstrap from Feishu app credentials and runtime config generation.
- Changelog and docs record the current cloud Linux baseline while keeping private server config out of the public repo.

## Required Runtime

This release packages deployment templates and helper scripts. The beginner bootstrap targets Ubuntu hosts and installs Node.js 22 plus Python 3. Deterministic commands remain normal cc-connect `[[commands]]` entries and require Python on the host. Image commands still require a runtime that supports Feishu `image_command_enabled`, `image_script`, `image_workspace`, `image_timeout_secs`, and `image_triggers` platform options.

Bootstrap does not write Feishu app secrets, OpenAI-compatible API keys, user IDs, group IDs, or generated cc-connect config. Run `scripts/install-linux.sh` after bootstrap to configure a real Feishu deployment.

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

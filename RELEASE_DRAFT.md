# codex-feishu v0.6.0｜飞书群聊画图命令

Adds platform-layer image generation commands for Feishu/Lark group bots, matching the QQ bot `/画图` workflow without sending the request through the mini/deep agent.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、飞书画图、飞书生图、Codex 群机器人、cc-connect 部署。

## Highlights

- Feishu platform templates now enable `/画图`、`/生图`、`/img`、`画图`、`生图` when the runtime supports `image_command_enabled`.
- New `scripts/generate-image.js` helper calls an OpenAI-compatible image API, saves generated images under `local_files/generated/images/`, and writes metadata to `memory/image-events-YYYY-MM-DD.jsonl`.
- The helper supports `FEISHU_IMAGE_BASE_URL`, `FEISHU_IMAGE_API_KEY`, `FEISHU_IMAGE_API_MODE`, `FEISHU_IMAGE_IMAGES_MODEL`, and related overrides.
- Windows and Linux installers copy the image helper into the generated group workspace.
- Tests now verify the image command config and helper copy path.

## Required Runtime

This release packages deployment templates and helper scripts. The underlying `cc-connect` runtime must support Feishu `image_command_enabled`, `image_script`, `image_workspace`, `image_timeout_secs`, and `image_triggers` platform options.

## Verify

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git diff --check
```

Expected:

- PowerShell parser and secret/local-data scan pass.
- Windows install smoke generates image command options and copies `generate-image.js`.
- Linux install checks run when a usable bash exists; otherwise they are skipped by the Windows test wrapper.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

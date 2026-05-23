# codex-feishu v0.5.0｜飞书双机器人群聊工作流

Packages the current production-style Feishu Codex workflow with platform-layer acknowledgements and optional family memory capture.

中文关键词：飞书机器人、Lark 机器人、飞书群聊 Codex、Codex 群机器人、双机器人路由、话题隔离、即时收到回复、家庭记忆、群聊记忆、cc-connect 部署。

## Highlights

- Deep @ tasks now use generated `instant_ack_text = "收到正在输出，请等等我。"` instead of the legacy acknowledgement hook.
- Mini can still stay silent on deep mentions through `ignore_bot_mentions`.
- Optional family memory capture can be enabled with `-EnableFamilyMemory` or `--enable-family-memory`.
- Family memory scripts record explicit `记住`、`忘掉`、`待办`、`购物`、`你记得什么` messages into workspace-local files.
- README and install docs were refreshed to reproduce the dual-bot, topic-isolated, optional-memory workflow.
- Codex API balance rotation docs now describe generic cc-switch providers with an OpenAI-compatible usage endpoint.
- Codex API balance rotation now falls back to chat completions warmup when a provider does not support the Responses API.

## Install

Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -MiniIgnoreBotMentions "feishu-deep,ou_deep_bot_open_id" `
  -DeepInstantAckText "收到正在输出，请等等我。" `
  -EnableFamilyMemory
```

Linux:

```bash
bash ./scripts/install-linux.sh \
  --mini-ignore-bot-mentions "feishu-deep,ou_deep_bot_open_id" \
  --deep-instant-ack-text "收到正在输出，请等等我。" \
  --enable-family-memory
```

## Verify

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git diff --check
```

Expected:

- PowerShell parser and secret/local-data scan pass.
- Windows install smoke generates `instant_ack_text` and optional family memory hook files.
- Family memory direct capture and hook smoke tests pass.
- Linux install checks run when a usable bash exists; otherwise they are skipped by the Windows test wrapper.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Full Changelog

See `CHANGELOG.md`.

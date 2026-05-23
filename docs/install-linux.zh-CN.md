# Linux 安装教程

本文说明如何在 Linux 服务器或桌面环境中部署 `codex-feishu`。Windows 版本仍保留在 `scripts/install.ps1`，Linux 版本使用 `scripts/install-linux.sh`。

## 适用场景

- 你想把 `cc-connect` 长期跑在 Linux 主机上。
- 你希望用 systemd user service 后台运行。
- 你仍然需要和 Windows 版相同的双机器人流程：mini 全量监听、deep 只处理 @、回复链隔离、`/help`、`/dream`、文件归档和健康检查。
- 你可以选择接入 cc-switch 的 provider 余额轮询，让 Codex 新会话默认使用当前余额最高的可用 API。
- 你可以选择启用家庭记忆捕获，把明确的记忆、待办、购物消息写入本地工作区。

## 安装依赖

```bash
node --version
npm --version
bash --version
npm install -g cc-connect
cc-connect --version
```

可选安装 `lark-cli`，用于附件下载、事件监听和健康检查：

```bash
npx @larksuite/cli@latest install
lark-cli --version
```

## 克隆仓库

```bash
git clone https://github.com/GitLaughs/codex-feishu.git
cd codex-feishu
```

## 准备飞书应用

仍然需要两个飞书/Lark 自建应用：

- mini app：开启机器人能力、订阅 `im.message.receive_v1`、申请群聊全量消息权限。
- deep app：开启机器人能力、订阅 `im.message.receive_v1`，不建议开启群聊全量消息权限。

两个机器人都需要被拉进目标群。

## 交互安装

```bash
bash ./scripts/install-linux.sh
```

## 非交互安装

```bash
bash ./scripts/install-linux.sh \
  --group-chat-id "oc_xxx" \
  --mini-project "feishu-mini" \
  --deep-project "feishu-deep" \
  --admin-open-id "*" \
  --mini-model "gpt-5.4-mini" \
  --mini-effort "medium" \
  --mini-ignore-bot-mentions "feishu-deep,ou_deep_bot_open_id" \
  --mini-trigger-threshold "strict" \
  --deep-model "gpt-5.5" \
  --deep-effort "high" \
  --deep-instant-ack-text "收到正在输出，请等等我。" \
  --dream-model "gpt-5.5" \
  --dream-effort "xhigh" \
  --codex-mode "yolo" \
  --workspace-path "$HOME/codex-feishu-workspace" \
  --mini-app-id "cli_xxx" \
  --mini-app-secret "..." \
  --deep-app-id "cli_yyy" \
  --deep-app-secret "..." \
  --enable-family-memory
```

只生成配置，不注册 systemd：

```bash
bash ./scripts/install-linux.sh --no-systemd
```

## Codex API 余额轮询

如果服务器上安装了 cc-switch，并且多个兼容 OpenAI API 的 Codex provider 已在 cc-switch 中配置，可开启轮询：

```bash
bash ./scripts/install-linux.sh \
  --enable-codex-balance-rotate \
  --codex-rotate-db-path "$HOME/.cc-switch/cc-switch.db" \
  --codex-rotate-auth-path "$HOME/.codex/auth.json"
```

安装器会创建：

```text
~/.config/systemd/user/codex-feishu-codex-balance-rotate.service
~/.config/systemd/user/codex-feishu-codex-balance-rotate.timer
```

默认每 30 分钟运行一次，读取 cc-switch 数据库中的 Codex provider，调用 `/v1/usage` 查询余额，并把余额最高的有效 key 写入：

- `--codex-rotate-env-path`，默认是仓库目录下的 `codex.env`
- `--codex-rotate-auth-path`，默认是 `$HOME/.codex/auth.json`
- `--codex-rotate-config-path`，默认是 `$HOME/.codex/config.toml`
- `--codex-rotate-fallback-file`，默认是 `$HOME/.cc-switch/codex-fallback-providers.json`

warmup 默认先请求 Responses API；如果 provider 返回不支持 Responses，会自动改用 chat completions 做 warmup，再查询 `/v1/usage`。也可以在 fallback 文件里显式写：

```json
{
  "name": "backup-provider",
  "base_url": "https://example.invalid/v1",
  "key": "sk-...",
  "model": "gpt-5.5",
  "warmup_api": "chat"
}
```

可调整频率：

```bash
bash ./scripts/install-linux.sh \
  --enable-codex-balance-rotate \
  --codex-rotate-interval "*:0/15"
```

这套逻辑不做单条消息失败后的自动重试。如果某次回答因为余额或上游错误失败，让用户重新发送即可。

## 家庭记忆捕获

开启方式：

```bash
bash ./scripts/install-linux.sh --enable-family-memory
```

安装器会复制 `family-memory-capture.py`、`cc-connect-memory-hook.sh` 和测试脚本，并创建：

```text
memory/messages
memory/people
memory/family
memory/summaries
```

这个 hook 只记录显式记忆类消息，不负责即时“收到”回复。deep 的即时回复由 `instant_ack_text` 字段处理。

## systemd user service

默认情况下，如果系统有 `systemctl`，安装器会创建并启动：

```text
~/.config/systemd/user/codex-feishu-cc-connect.service
```

常用命令：

```bash
systemctl --user status codex-feishu-cc-connect.service
systemctl --user restart codex-feishu-cc-connect.service
journalctl --user -u codex-feishu-cc-connect.service -f
```

如果服务器登出后 user service 会停止，需要启用 linger：

```bash
loginctl enable-linger "$USER"
```

如果不使用 systemd，可以手动启动：

```bash
bash ./scripts/start-cc-connect.sh \
  --root "$(pwd)" \
  --config "$HOME/.cc-connect/config.toml" \
  --log "$(pwd)/cc-connect-run.log"
```

## 安装结果

Linux 安装器会生成：

- `$HOME/.cc-connect/config.toml`
- 群聊工作区
- `AGENTS.md`
- `INSTRUCTIONS.md`
- `local_files/`
- `memory/`
  - 如果启用家庭记忆，还会生成 `memory/messages`、`memory/people`、`memory/family`、`memory/summaries`
- `local_files/docs/help-guide.md`
- `scripts/dream_prompt.md`
- Linux 版 helper scripts：
  - `help.sh`
  - `dream.sh`
  - `import-local-file.sh`
  - `lark-download-resource.sh`
  - `lark-event-listener.sh`
  - `lark-health.sh`

## 验证

```bash
cc-connect sessions list
tail -n 120 ./cc-connect-run.log
```

在群里测试：

- 普通消息：进入 mini project，闲聊默认静默。
- @ deep bot：进入 deep project，立即收到 `收到正在输出，请等等我。`。
- 如果启用 `--mini-ignore-bot-mentions` 且运行时支持该字段，deep bot 的 @ 根消息和同话题回复不会再进入 mini。
- `/help`：返回静态使用指南。
- `/dream`：执行工作区整理。
- 飞书回复某条任务消息：继续对应会话。

## 常见问题

### systemd 启动后找不到 cc-connect

确认 `cc-connect` 在 user service 的 PATH 中可见：

```bash
command -v cc-connect
npm root -g
```

如果是 nvm 安装的 Node.js，systemd 可能没有加载 nvm 环境。可以改为手动启动，或把 Node.js 安装到系统 PATH。

### /dream 找不到 codex

`/dream` 需要 `codex` CLI 在服务环境中可见：

```bash
command -v codex
```

如果 shell 里有、systemd 里没有，通常也是 PATH 问题。

### lark-cli helper 不可用

运行：

```bash
bash ./scripts/lark-health.sh
```

如果输出显示 `lark-cli` 不存在，先安装：

```bash
npx @larksuite/cli@latest install
```

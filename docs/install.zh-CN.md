# 中文安装教程

本文从零开始说明如何把 `codex-feishu` 部署到 Windows，并接入一个飞书/Lark 群聊。Linux 部署见 [Linux 安装教程](install-linux.zh-CN.md)。

## 目标效果

部署完成后，一个群里会有两个机器人：

- mini bot：接收全部群消息，用 `gpt-5.4-mini` 判断是否需要回复。
- deep bot：只处理 @，用 `gpt-5.5` 处理复杂任务。
- `/help`：直接返回静态群聊使用指南，不进入模型推理。
- `/dream`：用 deep 模型整理本地工作区、知识库和文件索引。
- 可选家庭记忆：把明确的“记住 / 待办 / 购物 / 查记忆”消息写入本地工作区。

普通群消息、文件和项目上下文不会丢；真正复杂的任务可以直接 @ deep bot。

## 1. 本地环境

确认系统和工具：

```powershell
node --version
npm --version
powershell.exe -NoProfile -Command "$PSVersionTable.PSVersion"
```

安装 `cc-connect`：

```powershell
npm install -g cc-connect
cc-connect --version
```

克隆仓库：

```powershell
git clone https://github.com/GitLaughs/codex-feishu.git
cd codex-feishu
```

如果不能访问 GitHub，可以先下载 zip，再在解压目录运行后续命令。

## 2. 创建两个飞书应用

进入飞书开放平台，创建两个自建应用。

建议命名：

- `codex-mini`
- `codex-deep`

两个应用都需要开启机器人能力，并把机器人添加到目标群聊。

## 3. 配置 mini app

mini app 的职责是“全量监听，但不一定回复”。

在飞书开放平台里配置：

- 开启机器人能力。
- 开启事件订阅。
- 订阅 `im.message.receive_v1`。
- 在“权限管理”里导入：

  ```text
  templates/feishu-mini-scopes.json
  ```

- 申请群聊全量消息权限，控制台里通常显示为 `im:message.group_msg` 或“接收群聊中所有消息”。
- 按控制台要求配置数据权限范围。
- 修改权限后发布新版本，并等待审核/生效。

mini app 必须有群聊全量消息权限，否则普通群消息不会触发本地 `cc-connect`。

## 4. 配置 deep app

deep app 的职责是“只处理 @ 触发的复杂任务”。

在飞书开放平台里配置：

- 开启机器人能力。
- 开启事件订阅。
- 订阅 `im.message.receive_v1`。
- 在“权限管理”里导入：

  ```text
  templates/feishu-deep-scopes.json
  ```

- 把机器人添加到同一个群。
- 不要给它开启群聊全量消息权限，除非你明确想让它也监听所有消息。

这样可以避免 @ 消息被 mini 的全量监听项目抢走。

权限导入后必须到“版本管理”创建并发布新版本。只保存权限但不发布，线上机器人仍会按旧权限运行。

可以用 App ID 直接打开控制台：

```text
https://open.feishu.cn/app/<app_id>
```

## 5. 准备安装参数

安装前准备这些值：

| 参数 | 含义 | 示例 |
|---|---|---|
| `GroupChatId` | 飞书群 chat_id | `oc_xxx` |
| `MiniAppId` | mini app 的 app id | `cli_xxx` |
| `MiniAppSecret` | mini app secret | 不要提交到 Git |
| `DeepAppId` | deep app 的 app id | `cli_yyy` |
| `DeepAppSecret` | deep app secret | 不要提交到 Git |
| `WorkspacePath` | 本地群聊工作区 | `E:\FeishuCodexWorkspace` |

如果暂时不知道群 `chat_id`，可以先参考 `cc-connect` 或飞书 API 获取方式；本仓库不会内置你的真实群 ID。

## 6. 运行安装器

交互式安装：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

推荐的非交互安装模板：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -GroupChatId "oc_xxx" `
  -MiniProject "feishu-mini" `
  -DeepProject "feishu-deep" `
  -AdminOpenId "*" `
  -MiniModel "gpt-5.4-mini" `
  -MiniEffort "medium" `
  -MiniIgnoreBotMentions "codex-deep,ou_deep_bot_open_id" `
  -MiniTriggerThreshold "strict" `
  -DeepModel "gpt-5.5" `
  -DeepEffort "high" `
  -DeepInstantAckText "收到正在输出，请等等我。" `
  -DreamModel "gpt-5.5" `
  -DreamEffort "xhigh" `
  -CodexMode "yolo" `
  -WorkspacePath "E:\FeishuCodexWorkspace" `
  -MiniAppId "cli_xxx" `
  -MiniAppSecret "填你的 mini secret" `
  -DeepAppId "cli_yyy" `
  -DeepAppSecret "填你的 deep secret" `
  -EnableFamilyMemory
```

安装脚本会：

- 备份已有 `~\.cc-connect\config.toml`。
- 写入新的双机器人配置。
- 创建群聊工作区。
- 生成 `AGENTS.md`、`INSTRUCTIONS.md`、`KNOWLEDGE.md`、`memory` 和 `local_files` 目录。
- 生成 `/help` 指南和 `/dream` 维护提示词。
- 复制文件归档、飞书资源下载、事件监听、健康检查和画图脚本。
- 如果启用 `-EnableFamilyMemory`，复制家庭记忆脚本并创建 `memory/messages`、`memory/people`、`memory/family`、`memory/summaries`。
- 注册 Windows 计划任务启动 `cc-connect`。
- 注册 watchdog，定期检查并拉起 `cc-connect`。

## 7. mini 回复阈值怎么选

`-MiniTriggerThreshold` 有三个值：

- `strict`：推荐默认值。群聊安静、节省 token，只有明确有用时回复。
- `medium`：适合项目群，普通问题和文件事件会更积极处理。
- `relaxed`：适合测试或机器人主导的群，mini 会更愿意参与。

如果不确定，先用：

```powershell
-MiniTriggerThreshold "strict"
```

后续如果发现 mini 太安静，再改成 `medium`。

## 8. 验证本地状态

查看版本：

```powershell
cc-connect --version
```

查看会话：

```powershell
cc-connect sessions list
```

查看日志：

```powershell
Get-Content .\cc-connect-run.log -Tail 120
```

查看进程：

```powershell
Get-Process cc-connect -ErrorAction SilentlyContinue
```

查看计划任务：

```powershell
Get-ScheduledTask -TaskName codex-feishu-cc-connect,codex-feishu-watchdog
```

## 9. 验证群聊行为

在目标群里测试：

1. 发送一条普通消息，例如“记录一下今天的测试结论”。
2. 发送一个文件，确认 mini 能处理或记录文件。
3. @ deep bot 提一个复杂问题。
4. 对 deep bot 的某条回复使用飞书“回复”，继续补充要求。

预期行为：

- 普通消息进入 mini project。
- 闲聊默认不回复，也不会收到 `收到`。
- 文件会被保存和索引到本地工作区。
- @ 消息进入 deep project。
- @ 消息由 deep 平台路由立即回复 `收到正在输出，请等等我。`。
- 不同 root @ 消息会形成不同任务会话。
- 飞书回复链会继续对应任务。

再测试静态命令：

```text
/help
/dream
```

预期：

- `/help` 返回 `local_files/docs/help-guide.md` 的内容。
- `/dream` 在工作区内整理 `KNOWLEDGE.md`、`memory/YYYY-MM-DD.md` 和 `memory/dreams/`。
- `/画图`、`/生图`、`/img`、`画图`、`生图` 在支持 `image_command_enabled` 的运行时中直接生成图片。需要在运行服务的环境里配置 `FEISHU_IMAGE_API_KEY`，可选配置 `FEISHU_IMAGE_BASE_URL`、`FEISHU_IMAGE_API_MODE`、`FEISHU_IMAGE_IMAGES_MODEL`。

## 10. 常见问题

### 普通群消息没有触发 mini

优先检查飞书控制台：

- mini app 是否订阅了 `im.message.receive_v1`。
- mini app 是否申请并发布了群聊全量消息权限。
- 权限变更后是否发布了新版本。
- mini bot 是否已经在群里。

再检查本地日志：

```powershell
Get-Content .\cc-connect-run.log -Tail 120
```

### @ 消息进了 mini 而不是 deep

通常是两个项目共用了同一个飞书 app，或者 deep app 没有独立配置。

推荐配置：

```toml
# mini project
group_reply_all = true

# deep project
group_reply_all = false
```

并且 mini 和 deep 使用两个不同的飞书 app。

如果你的 `cc-connect` 支持 `ignore_bot_mentions`，同时给 mini 增加 deep bot 的显示名或 open_id：

```powershell
-MiniIgnoreBotMentions "codex-deep,ou_deep_bot_open_id"
```

生成配置示例：

```toml
ignore_bot_mentions = ["codex-deep", "ou_deep_bot_open_id"]
```

这样 deep bot 被 @ 后，mini 会跳过根消息和同话题后续回复，不再重复处理。

### deep 没有立即回复“收到”

即时“收到”现在走 Feishu platform 的 `instant_ack_text` 字段，不再依赖 `message.received` 命令 hook。

配置里应类似：

```toml
instant_ack_text = "收到正在输出，请等等我。"
```

如果配置正确但仍无立即回复，确认当前 `cc-connect` 运行时支持 `instant_ack_text`，并重启服务或计划任务。

### 家庭记忆没有写入

确认安装时启用了：

```powershell
-EnableFamilyMemory
```

配置里应有 `cc-connect-memory-hook.ps1`，工作区应有：

```powershell
Test-Path .\scripts\family-memory-capture.ps1
Test-Path .\memory\family
```

家庭记忆 hook 只处理显式记忆类消息，例如 `记住：...`、`待办：...`、`购物：...`。它不负责即时“收到”回复。

### 流式预览没有出现

检查配置：

```toml
[stream_preview]
enabled = true
interval_ms = 1000
min_delta_chars = 5
max_chars = 2000
```

很短的回复可能在预览刷新前就已经完成，这是正常情况。

### /help 或 /dream 没反应

检查配置里是否生成了命令：

```toml
[[commands]]
name = "help"

[[commands]]
name = "dream"
```

再检查工作区脚本：

```powershell
Test-Path .\scripts\help.ps1
Test-Path .\scripts\dream.ps1
Test-Path .\local_files\docs\help-guide.md
```

### 需要检查 lark-cli 状态

安装器会把健康检查脚本复制到群聊工作区：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\lark-health.ps1
```

输出会尽量脱敏，不会打印完整 token。

## 11. 更新配置

重新运行安装器即可覆盖生成配置。脚本会先备份已有 `config.toml`：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

如果只想生成文件，不想注册或启动计划任务：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -NoScheduledTasks
```

## 12. 安全注意

- 不要把 `~\.cc-connect\config.toml` 提交到 Git。
- 不要把 app secret、open_id、chat_id 写进公开 Issue。
- 公开复现问题时，用 `cli_xxx`、`oc_xxx` 这类占位符替代真实值。
- 如果 secret 泄露，先去飞书开放平台重置，再更新本地配置。

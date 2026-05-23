# codex-feishu 优化简报 2026-05-23

## 已确认现状

- 云端 `cc-connect.service` 正常运行。
- Feishu 项目数为 9，覆盖私聊、项目群、汇报群、家庭群。
- `mimo-responses-proxy.service`、Codex 余额轮询 timer、失败 watchdog timer 正常。
- 服务器资源偏紧：1.6GiB 内存，根分区 40G，当前用量约 51%。

## 本轮已落地

- 新增 `docs/product-iteration-plan.md`：codex-feishu 产品化路线，按 P0/P1/P2/P3 拆分。
- 新增 `scripts/audit-secrets.ps1`：本地发布前密钥扫描门禁。
- 新增 `scripts/codex-feishu-healthcheck.sh`：云端 systemd/项目数/资源/近期错误健康检查。

## 下一步执行顺序

1. 轮换已暴露过的 API key 和 Feishu app secret。
2. 部署 `codex-feishu-healthcheck.sh` 到服务器，并接 systemd timer。
3. 将部署流程加入 `audit-secrets.ps1` 门禁。
4. 为每个 Feishu 群生成 workspace manifest。
5. 将 `/help`、`/status`、失败卡片改为结构化输出。

## 上线判断

当前系统可用，但还不应对外作为正式产品承诺。先完成密钥治理、健康检查、自动回滚、统一命令，再进入 beta。

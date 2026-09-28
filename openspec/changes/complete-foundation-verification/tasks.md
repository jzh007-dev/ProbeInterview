# Tasks

依赖：`deliver-foundation-probe-workflow` 已完成并归档。原 `setup-foundation` 任务 4.1–4.2 映射到本 change。

## 1. 完成统一验证与 E2E 验收

- [ ] 1.1 建立根级 `scripts/verify`，依次运行 backend 格式/lint/类型/单测、小程序 Jest/类型检查、迁移测试、owner/pgvector 集成测试和 Celery 测试，并文档化本地与 CI 的唯一调用方式；以故意破坏一个阶段的回归测试验证失败会返回非零状态并标识阶段
- [ ] 1.2 使用隔离 Compose 环境运行“小程序请求等价客户端 → Caddy → API → PostgreSQL → Redis → Worker → pgvector → 状态查询”端到端测试，提供 CI 平台无关的调用契约而不绑定托管平台，并以一次全新环境成功运行及自动清理测试数据作为验收证据

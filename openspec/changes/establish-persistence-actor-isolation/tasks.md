# Tasks

依赖：`establish-runtime-api-foundation` 已完成并归档。原 `setup-foundation` 任务 2.3–2.4 映射到本 change。

## 1. 交付持久化与 Actor 隔离

- [ ] 1.1 创建 pgvector 扩展、`foundation_probe_job` 与 `foundation_probe_vector` 的 SQLAlchemy 模型和 Alembic 初始迁移，并以空库升级、允许的降级、约束和固定向量写入/距离查询测试验证 schema
- [ ] 1.2 实现 `ActorContext`、非生产 local actor provider 和显式 `ActorScope` repository 契约，并以两个 actor 的 probe/向量集成测试验证 owner 条件在 SQL 查询前置生效且越权响应不泄露存在性

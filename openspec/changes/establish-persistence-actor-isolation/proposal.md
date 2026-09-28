# Proposal

## Why

运行拓扑与 API 协议建立后，foundation 仍需要可迁移的 PostgreSQL/pgvector schema 和可证明的 owner 前置隔离，probe 工作流才能安全持久化、恢复和查询状态。本 change 将数据真相与 actor scope 作为独立验收边界。

## What Changes

- 启用 pgvector 扩展并创建业务无关的 `foundation_probe_job` 与 `foundation_probe_vector` SQLAlchemy 模型和 Alembic 初始迁移。
- 验证空库升级、允许的降级、schema 约束、固定测试向量写入和距离查询。
- 建立 `ActorContext(actor_id, capabilities)`、仅非生产可用的 local actor provider 和显式 `ActorScope` repository 契约。
- 要求 probe、状态和向量查询在数据库/向量读取前应用公共范围或当前 actor 的 owner 条件。
- 以两个 actor 的集成测试证明跨 owner 记录和向量不可见，且外部响应不泄露目标是否存在。
- 保持测试向量表与未来知识向量模型隔离，不决定业务 Embedding 维度、距离函数或索引类型。

## Capabilities

### New Capabilities

- `persistence-actor-isolation`: 定义 foundation schema 迁移、固定向量 smoke query、ActorContext 和 owner 前置隔离行为。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 依赖 `establish-runtime-api-foundation` 完成并归档。
- 影响 PostgreSQL + pgvector、SQLAlchemy 2、Alembic、identity/access 基础契约、repository 查询和数据库集成测试。
- 为 `deliver-foundation-probe-workflow` 提供持久化 job/vector 记录和 actor-scoped 查询边界。
- 不实现 probe HTTP 命令、Celery 执行、外部服务 fake adapter、小程序诊断页或完整 E2E。

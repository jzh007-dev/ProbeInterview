# Design

## Context

本 change 的动机见 `proposal.md`，行为契约见 `specs/persistence-actor-isolation/spec.md`。它依赖已归档的 `establish-runtime-api-foundation`，承接原任务 2.3–2.4，并为后续 probe API 与 Worker 提供唯一持久化和隔离边界。

设计遵循 `docs/architecture.md`、ADR 0002 和 ADR 0004。PostgreSQL 是任务状态真相，pgvector 数据是可重建派生数据；owner/public scope 必须在数据库或向量读取前应用。真实知识 schema、Embedding 维度、距离策略和索引类型仍由消费它们的后续知识 change 决定。

## Goals / Non-Goals

**Goals:**

- 通过 Alembic 从空库显式建立 pgvector 与两个业务无关 probe 表。
- 在 probe 工作流实现前独立验证 schema 约束、允许的 downgrade 和固定测试向量距离查询。
- 固定 `ActorContext`、local actor provider 与显式 `ActorScope` repository 契约。
- 以两个 actor 的集成测试证明 owner 条件在记录和向量读取前生效。

**Non-Goals:**

- 不实现正式微信身份交换、账户生命周期或白名单 capability 映射。
- 不实现 probe HTTP 命令、幂等请求处理、Celery 消息、重试或恢复命令。
- 不创建知识来源、chunk、概念、业务 embedding、检索索引或公共知识发布模型。
- 不把 Redis、Celery result backend 或 pgvector 记录作为任务状态真相。

## Decisions

### 1. PostgreSQL 是 probe 状态真相，pgvector 只承载隔离 smoke data

本 change 只创建：

- `foundation_probe_job`：稳定 ID、owner、幂等键、input hash、状态、尝试次数、request ID、安全结果/错误、时间戳和乐观锁版本。
- `foundation_probe_vector`：稳定 ID、probe ID、owner、probe 专用固定维度测试向量、版本和有效状态。

字段为后续 probe change 提供完整持久化契约，但本 change 不实现状态转换和异步执行。测试向量表只验证扩展、SQLAlchemy 映射、事务、距离查询和 owner 前置过滤，禁止被后续知识检索复用。该边界遵循 ADR 0002。

直接创建最终知识向量表会提前决定业务 chunk、Embedding 维度、距离函数和索引，因此被排除。

### 2. Schema 只由显式 Alembic migration 修改

Alembic 初始 migration 启用 pgvector 并创建两个 probe 表、外键、唯一约束和必要检查约束。应用启动不自动创建或修改 schema。

自动化测试从空库升级到 head，验证声明支持的 downgrade、约束和固定向量查询。显式 migration 让本地、Compose 和未来部署使用同一 schema 演进路径；运行时 `create_all` 会掩盖迁移缺失并导致环境漂移，因此禁止。

### 3. 应用层只接收 ActorContext

应用服务依赖 `ActorContext(actor_id, capabilities)`，不读取微信登录细节或任意调试 header。Development/test 可通过 local actor provider 建立上下文；production 配置与 provider 工厂必须拒绝该实现。

正式微信身份 provider 将来只替换上下文来源，不改变应用服务和 repository 方法签名。使用全局固定用户虽然更短，但无法证明跨 owner 隔离并容易成为生产捷径，因此禁止。该边界遵循 ADR 0004。

### 4. Repository 显式要求 ActorScope 并在 SQL/向量查询中前置过滤

所有 owner-scoped repository 方法显式接收 actor scope。SQL 条件先限制当前 actor 或允许的公共范围，再读取记录或执行向量距离排序；禁止先召回再在内存过滤。

对其他 owner 的 probe 返回与不存在一致的外部结果。集成测试使用至少两个 actor，分别覆盖自己的 job、其他 owner job 和向量查询，证明记录存在性与向量候选均不泄露。

业务模块不得直接导入其他模块的 ORM model 或 repository；probe application 通过本模块契约访问持久化。

## Risks / Trade-offs

- [Probe 表被后续业务复用] → 名称、migration 和文档明确其验证专用性质，知识 change 必须建立独立 schema。
- [向量过滤写在查询结果之后] → repository contract 强制 ActorScope，集成测试检查 SQL 级 owner 条件和跨 owner 候选。
- [Local actor 成为认证捷径] → production 配置与 provider factory 双重拒绝。
- [初始 migration 承载后续任务字段但尚无 workflow] → 字段仅定义持久化契约，状态转换仍由下一 change 的应用服务和测试交付。

## Migration Plan

1. 增加 SQLAlchemy 映射与 Alembic 初始 migration，显式启用 pgvector。
2. 在隔离空库执行 upgrade、允许的 downgrade 和 schema 约束测试。
3. 实现 ActorContext、local actor provider、ActorScope repository 契约与两个 actor 集成测试。
4. 验证固定 probe 向量写入、距离查询和 owner 前置过滤，不启动 probe API 或 Worker 闭环。

这是 greenfield schema。回滚只在隔离或无业务数据环境执行本 change 声明支持的 downgrade；一旦后续 change 写入 probe 状态，生产回滚必须按迁移策略保留可审计数据。

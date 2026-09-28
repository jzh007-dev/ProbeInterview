# Proposal

## Why

已验证的运行拓扑、API 协议、持久化和 actor 隔离还不能证明异步任务可端到端安全执行。本 change 用非业务 foundation probe 串通 API、数据库、Redis/Celery、Worker、pgvector、fake adapter 和开发诊断客户端，同时保持真实供应商与产品功能在范围外。

## What Changes

- 定义 `ObjectStorage`、`EmbeddingProvider` 和 `StructuredLlmClient` 应用端口及 deterministic fake adapter，并验证契约、显式失败和日志脱敏。
- 实现 `POST /api/v1/foundation/probes` 与 `GET /api/v1/foundation/probes/{id}`，返回 HTTP 202、`Location`、类型化任务资源和安全状态摘要。
- 以 actor、命令类型、`Idempotency-Key` 和规范化 input hash 实现幂等创建及 409 冲突。
- 实现只携带 probe ID 的 Celery 消息、状态锁定、fake 存储往返、fake embedding、owner-scoped pgvector 查询、有限重试、终态幂等和超时 QUEUED 恢复命令。
- 创建仅 development 构建可见的小程序诊断页，覆盖发起、轮询、QUEUED/RUNNING/SUCCEEDED/FAILED、加载、错误、成功摘要和重复点击。
- 保证本地与测试运行不需要真实 OSS、LLM 或 Embedding 凭证，production 不暴露 probe 创建入口或诊断页。

## Capabilities

### New Capabilities

- `foundation-probe-workflow`: 定义异步 probe API、幂等与恢复语义、fake adapter 边界及开发诊断客户端行为。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 依赖 `establish-persistence-actor-isolation` 完成并归档。
- 影响 platform/foundation 端口与 adapter、probe application/API、Celery Worker、恢复命令、PostgreSQL probe 记录、pgvector smoke query、小程序开发诊断页及其自动化测试。
- UI 只用于开发诊断，参考 `docs/design/visuals/ui-direction.html` 的已选视觉方向，但不新增产品页面或导航能力。
- 为 `complete-foundation-verification` 提供可运行的完整 probe 链路。
- 不实现正式微信登录、真实 OSS/百炼 adapter、知识导入、业务 Embedding、知识检索、卡片或面试功能。

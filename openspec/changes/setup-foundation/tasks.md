# Tasks

## 1. 建立可复现工程骨架

- [x] 1.1 创建 `apps/backend`、`apps/miniprogram`、`infra/compose` 和 `scripts` 目录，按业务模块内部再分层建立 modular-monolith 骨架，配置 Python 3.12 + uv、TypeScript + TDesign 和依赖锁定；以全新环境安装、backend import 和小程序类型检查验证骨架可复现
- [x] 1.2 使用 Pydantic Settings 建立 development、test、production 配置 schema、无密钥示例配置和启动校验，记录本地启动命令；以配置单元测试验证缺少必填项时明确失败、production 禁止 local actor、fake production fallback 和 foundation probe

## 2. 交付 API、持久化与隔离基线

- [ ] 2.1 配置 Caddy、FastAPI、Celery Worker、PostgreSQL + pgvector 和 Redis 的 Docker Compose 服务、健康检查及隔离测试 profile，提供 Caddy 反向代理、production 自动 TLS/HTTPS 跳转配置和本地测试配置；以 Compose 校验、代理请求及所有基础服务健康验证运行拓扑
- [ ] 2.2 实现 `/health/live`、`/health/ready`、直接类型化成功响应、RFC 9457 `application/problem+json` 错误、`X-Request-ID` 中间件和带 request/trace/job ID 的结构化安全日志；以 API 测试验证依赖故障、字段错误、未处理异常、敏感信息脱敏和 request ID 传播
- [ ] 2.3 创建 pgvector 扩展、`foundation_probe_job` 与 `foundation_probe_vector` 的 SQLAlchemy 模型和 Alembic 初始迁移，并以空库升级、允许的降级、约束和固定向量写入/距离查询测试验证 schema
- [ ] 2.4 实现 `ActorContext`、非生产 local actor provider 和显式 `ActorScope` repository 契约，并以两个 actor 的 probe/向量集成测试验证 owner 条件在 SQL 查询前置生效且越权响应不泄露存在性

## 3. 交付异步 foundation probe 闭环

- [ ] 3.1 定义 `ObjectStorage`、`EmbeddingProvider`、`StructuredLlmClient` 端口及确定性 fake adapter，增加 adapter 契约测试和日志脱敏测试，验证本地与测试运行不需要真实 OSS 或百炼凭证
- [ ] 3.2 实现 `POST /api/v1/foundation/probes` 与 `GET /api/v1/foundation/probes/{id}`，包括 HTTP 202、`Location` 状态地址、类型化任务资源、幂等键和 input hash 冲突处理；以 API/数据库测试验证重复相同命令复用原任务、不同输入返回 RFC 9457 格式的 409
- [ ] 3.3 实现只接收 probe ID 的 Celery 任务、状态锁定、fake 存储往返、fake embedding、owner-scoped pgvector 查询、有限重试和超时 QUEUED 恢复命令，并以重复投递、中断恢复、最终失败和单一结果测试验证幂等性
- [ ] 3.4 创建仅开发构建可见的小程序诊断页，支持发起 probe、轮询 QUEUED/RUNNING/SUCCEEDED/FAILED 和展示安全摘要，并以 Jest + `miniprogram-simulate` 组件测试验证加载/状态变化/错误态、重复点击幂等及 production 构建不暴露入口

## 4. 自动验证与闭环验收

- [ ] 4.1 建立根级 `scripts/verify`，依次运行 backend 格式/lint/类型/单测、小程序 Jest/类型检查、迁移测试、owner/pgvector 集成测试和 Celery 测试，并文档化本地与 CI 的唯一调用方式；以故意破坏一个阶段的回归测试验证失败会返回非零状态并标识阶段
- [ ] 4.2 使用隔离 Compose 环境运行“小程序请求等价客户端 → Caddy → API → PostgreSQL → Redis → Worker → pgvector → 状态查询”端到端测试，提供 CI 平台无关的调用契约而不绑定托管平台，并以一次全新环境成功运行及自动清理测试数据作为验收证据

# Proposal

## Why

ProbeInterview 当前没有可运行、可测试的工程骨架，后续知识导入、卡片生成和模拟面试都缺少共同依赖的 API、持久化、后台任务与客户端基础。先交付一条最薄的 walking skeleton，可以在进入业务 change 前验证技术栈、运行单元和自动化测试链路真实可用。

## What Changes

- 建立微信小程序、反向代理、FastAPI API、Celery Worker、PostgreSQL + pgvector 和 Redis 的最小工程与 Docker Compose 运行骨架。
- 提供非业务的 foundation probe：客户端发起任务，API 持久化并投递，Worker 异步执行，客户端轮询最终状态。
- 建立 `/api/v1`、统一成功/错误结构、request ID、命令幂等键和异步任务状态的基础契约。
- 建立 Alembic 迁移、最小 owner scope、任务记录和固定测试向量表，验证事务、跨 owner 隔离及 pgvector 写入/查询。
- 建立对象存储、LLM 和 Embedding 的供应商端口与 fake adapter；本 change 不调用真实 OSS、百炼模型或业务 Embedding。
- 建立 Python 与小程序的统一格式检查、静态检查、单元测试、数据库/Worker 集成测试、端到端 probe 测试和 CI 入口。
- 明确排除微信正式登录、知识文件上传解析、知识点/卡片模型、真实向量化、检索、LLM 业务调用及产品页面。

## Capabilities

### New Capabilities

- `platform-foundation`: 定义系统健康、请求追踪、异步任务、owner 隔离、pgvector smoke test 和 walking skeleton 的可观察基础行为。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 新增微信小程序 TypeScript + TDesign、Python 3.12 + FastAPI/Pydantic 2、SQLAlchemy 2/Alembic、Celery/Redis 和 Docker Compose 工程骨架。
- 新增 PostgreSQL + pgvector 基础迁移、foundation probe API、后台任务和最小持久化模型。
- 新增 `/api/v1` 基础协议、统一错误、request ID、幂等与任务状态约定，后续 changes 必须复用。
- 新增 pytest、Ruff、mypy、小程序检查及 CI 命令；后续功能 change 以这些命令作为准入条件。
- 不新增任何知识库、卡片、面试或用户产品能力，不连接真实 OSS 或百炼业务接口。

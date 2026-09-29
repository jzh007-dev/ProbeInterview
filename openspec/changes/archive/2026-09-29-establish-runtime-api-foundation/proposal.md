# Proposal

## Why

可复现工程骨架仍缺少后续 foundation changes 共同依赖的可运行拓扑和 HTTP 基础契约。本 change 在引入业务无关持久化 schema 与 probe 工作流前，先独立交付并验证 Caddy、API、Worker、PostgreSQL 和 Redis 的运行边界。

## What Changes

- 使用同一个 backend 镜像和不同启动命令，将 Caddy、FastAPI API、Celery Worker、PostgreSQL + pgvector 和 Redis 配置为 Docker Compose 服务。
- 提供 development、test、production 编排变体，包含健康检查、依赖重试、隔离测试卷、本地反向代理及 production TLS/HTTPS 跳转配置。
- 提供独立存活与就绪检查；就绪状态反映数据库和任务投递依赖是否可用。
- 建立类型化成功资源、RFC 9457 Problem Details、`X-Request-ID` 及带 request/trace/job ID 的结构化安全日志。
- 在不引入应用持久化或 actor-owned 记录的前提下，验证运行拓扑、反向代理、依赖故障、错误映射、request ID 传播和日志脱敏。
- 原样保留现有未提交的 Docker/Compose/Caddy 实现工作并将其归属本 change；本次规划拆分不修改或提交这些代码。

## Capabilities

### New Capabilities

- `runtime-api-foundation`: 定义后续 changes 复用的运行拓扑、服务健康、API 错误协议、请求追踪和结构化安全日志。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 依赖 `setup-foundation` 完成并归档。
- 影响 `apps/backend` 运行入口、`infra/compose`、Caddy 配置、健康接口、API 中间件、错误映射、日志、拓扑测试和运行文档。
- 为 `establish-persistence-actor-isolation` 提供已验证的运行服务与 HTTP 契约。
- 不创建 Alembic 迁移、foundation probe 表、actor-scoped repository、probe API、客户端诊断页或根级完整验证入口。

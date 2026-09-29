# Design

## Context

本 change 的动机见 `proposal.md`，行为契约见 `specs/runtime-api-foundation/spec.md`。它直接依赖已归档的 `setup-foundation`，并只承接原任务 2.1–2.2。

工作树当前已有未提交的 Docker/Compose/Caddy 实现：backend Dockerfile、development/test/production Compose 文件、Caddy 配置、拓扑测试脚本以及被删除的占位 README。这些文件原样归属本 change；本次 OpenSpec 拆分不修改、覆盖或提交它们。

设计遵循 `docs/architecture.md`、ADR 0001、0003、0004、0005。持久化 schema、ActorContext、probe API 和完整 E2E 由后续 changes 交付。

## Goals / Non-Goals

**Goals:**

- 交付可独立启动和验证的 Caddy、API、Worker、PostgreSQL + pgvector、Redis 拓扑。
- 建立所有后续 API 复用的存活/就绪、类型化成功资源、Problem Details、request ID 与安全日志契约。
- 区分 development、test、production 编排行为，并保证测试状态隔离可清理。
- 在不依赖 probe 表或业务 API 的情况下验收反向代理和运行依赖。

**Non-Goals:**

- 不创建 Alembic migration、foundation probe job/vector schema 或 actor-scoped repository。
- 不实现 `POST/GET foundation probes`、幂等命令、Celery probe 执行或恢复命令。
- 不实现小程序诊断页、真实外部服务 adapter 或根级完整验证入口。
- 不提供高可用、自动扩缩容、托管数据库/队列、备份、监控或告警平台。

## Decisions

### 1. Compose 使用五个运行单元并共享 backend 镜像

Compose 包含 Caddy、FastAPI API、Celery Worker、PostgreSQL + pgvector 和 Redis。API 与 Worker 使用同一 backend 镜像和应用包，通过不同命令启动；这保持模块化单体的代码边界，同时验证独立进程入口。

PostgreSQL 和 Redis 使用明确命名的持久卷；test profile 使用独立 project name、端口和可清理卷。服务依赖以 health check 和应用级重试判断可用，不能仅依赖容器启动顺序。该拓扑遵循 ADR 0001、0003 和 0005。

替代方案在请求内执行后台工作或省略 Worker/Redis，会使后续 probe change 无法在相同运行边界内实现；提前使用 Kubernetes 或托管服务则超出单 ECS MVP。

### 2. Caddy 是唯一外部 HTTP 入口

Development/test 使用明确的本地 Caddy 配置验证反向代理；production 使用域名配置启用自动 TLS 和 HTTP 到 HTTPS 跳转。API、Worker、PostgreSQL 和 Redis 不直接暴露公网。

拓扑验收使用不依赖业务 schema 的公开健康或基础 API 请求，避免本 change 被后续数据库工作阻塞。选择 Caddy 而非在 FastAPI 内终止公网 TLS，保持网关可替换且不改变内部 API 契约。该边界遵循 ADR 0005。

### 3. 存活与就绪分离

- `GET /health/live` 只证明 API 进程可处理请求，不依赖真实云供应商。
- `GET /health/ready` 检查当前处理请求所需的 PostgreSQL 与 Redis/任务投递依赖，并以稳定依赖类别报告不可用。

Worker 与基础服务通过 Compose health check 参与拓扑状态。存活接口不等于完整业务就绪，避免非关键供应商或后续尚未实现的 adapter 让进程被错误重启。

### 4. API 使用类型化成功资源和 RFC 9457 Problem Details

所有版本化业务 API 位于 `/api/v1`。成功响应直接返回具体 schema，不增加通用 `data/meta` envelope。错误使用 `application/problem+json`，包含 RFC 9457 标准字段以及稳定 `code`、可选字段错误和 request ID 扩展，不暴露堆栈、SQL、密钥、连接串或供应商原始错误。

中间件接受合法客户端 request ID，否则生成新值，并在 `X-Request-ID` 响应头、错误映射和结构化日志中复用。异步命令的 `202 + Location` 与 `Idempotency-Key` 细节由 `deliver-foundation-probe-workflow` 实现，但必须复用本 change 的协议。该决策遵循 ADR 0004。

### 5. 日志以安全摘要关联 request、trace 和 job

API 和 Worker 输出结构化 JSON。HTTP 事件优先携带 request ID，跨进程事件使用 trace ID，后台执行使用 job ID；尚无 job 的运行事件不伪造标识。

日志排除请求正文、私人来源文本、完整 Prompt/模型响应、密钥、令牌、连接串和内部异常堆栈。异常通过稳定错误类别和安全摘要排障。选择结构化字段而非文本拼接，便于后续 probe 在不记录私密输入的前提下关联链路。该决策遵循 ADR 0005。

## Risks / Trade-offs

- [现有 2.1 未提交代码与新边界不完全一致] → 实施恢复时先按本 change specs/design 对照，但不得在本次拆分中改动这些文件。
- [API health 在尚无 migration 时错误依赖 schema] → readiness 只检查基础连接与任务投递，不查询后续 probe 表。
- [Caddy 自动 TLS 在本地依赖公网域名] → development/test 使用本地 HTTP 配置；production 才启用域名与自动证书。
- [日志脱敏降低直接排障信息] → 保留 request/trace/job、稳定错误类别和安全摘要，私密原文只能走受控数据访问。

## Migration Plan

1. 从现有未提交 2.1 文件继续实现并验证 development/test/production Compose 与 Caddy 配置。
2. 验证 backend 镜像能以 API 和 Worker 两个命令启动，五个运行单元通过 health check。
3. 实现并测试 live/ready、Problem Details、request ID 和安全结构化日志。
4. 更新本 change 内所需运行文档与 focused checks，不创建迁移或 probe 业务闭环。

这是 greenfield 运行拓扑。回滚通过停止并清理本 change 的 Compose project 与测试卷完成，不删除后续 change 或用户业务数据。

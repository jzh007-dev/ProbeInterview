# Design

## Context

行为范围见 `proposal.md` 与 `specs/trace-context-propagation/spec.md`。现有 API 已提供 request ID、Problem Details 和结构化日志，但没有标准 span context 或 Celery 传播。

设计遵循 `docs/architecture.md`、ADR 0003、0005 和 0008。实现使用成熟 SDK 默认能力，只保留公网信任边界这一项项目策略。

## Goals / Non-Goals

**Goals:**

- 创建服务端 HTTP trace，并把活动 span 字段加入安全结构化日志。
- 通过 Celery header 延续 API 创建的 W3C context。
- 使用 in-memory exporter 自动验证 span、父子关系和 service resource。

**Non-Goals:**

- 不实现小程序 tracing、client action ID 或前端请求封装。
- 不实现生产 OTLP exporter、Collector、生产采样、exporter 脱敏或监控平台。
- 不规定业务任务的重试 span 拓扑、Agent 语义、metrics 或告警。

## Decisions

### 1. 使用官方 OpenTelemetry Python 组件

Backend 锁定 `opentelemetry-api`、`opentelemetry-sdk`、
`opentelemetry-instrumentation-fastapi` 和
`opentelemetry-instrumentation-celery`。初始化与 instrumentation 只位于
`platform/foundation` infrastructure。

Development/test 使用 `ParentBased(ALWAYS_ON)` 并可注入 in-memory exporter。
Production 没有 span processor，使用 `ParentBased(ALWAYS_OFF)`；context 和日志
关联继续工作，但不导出 span。

### 2. 公网边界不接受客户端父上下文

FastAPI 外层 infrastructure middleware 在官方 instrumentation 提取前移除
`traceparent`、`tracestate` 和 `baggage`。Instrumentation 随后创建新的 SERVER
span。`X-Request-ID` 与 trace ID 保持独立，响应返回诊断用 `X-Trace-ID`。

### 3. Celery 使用标准内部传播

API producer 与 Worker 使用仅包含 W3C Trace Context 的 propagator。消息业务参数
仍只包含稳定 job ID；Baggage 和私人内容不进入 header。Worker 缺少合法 context
时创建新 trace，而不是让业务失败。

### 4. 日志与 resource 保持最小稳定字段

API 与 Worker resource 使用 `service.namespace`、`service.name`、
`service.version` 和 `deployment.environment.name`。日志从活动 span 读取 trace
ID、span ID 与 trace flags，并附带适用的 request ID 或 job ID。项目日志不记录
请求正文、私人文本、Prompt、模型响应、凭证、令牌或连接串。

FastAPI URL 属性移除 query 值。生产 trace export 的异常事件与脱敏策略由未来
observability change 决定。

## Risks / Trade-offs

- [客户端与 API 不在同一 trace] → 当前没有客户端 tracing runtime；诊断使用响应 request/trace ID。
- [middleware 顺序导致客户端 context 被提取] → 用 in-memory exporter 覆盖合法、无效和伪造 sampled header。
- [Celery instrumentation 升级改变 header/span] → 锁定依赖并验证真实注入、提取和父子关系。

## Migration Plan

1. 用 ADR 0008 取代 ADR 0007 的超范围决策。
2. 完成 FastAPI 服务端 trace、resource 与日志关联。
3. 完成 Celery producer/Worker 内部传播。
4. 运行 backend 单元、格式、lint 和类型检查。

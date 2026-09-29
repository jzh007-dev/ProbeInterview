# Proposal

## Why

现有 request ID 只能关联单次 HTTP 日志，不能为后续 API 投递的 Celery 工作提供标准父子上下文。本 change 只建立最小服务端 trace 传播，不提前建设生产遥测平台。

## What Changes

- 公网 HTTP 忽略客户端 trace header，由 FastAPI 创建服务端 trace，并返回独立 `X-Request-ID` 与诊断用 `X-Trace-ID`。
- API 与 Celery Worker 使用 W3C Trace Context 传播服务端上下文，消息仍只携带稳定任务 ID 和安全 header。
- 使用官方 OpenTelemetry Python API/SDK 与 FastAPI/Celery instrumentation，统一 API/Worker resource 与日志关联字段。
- Development/test 使用 in-memory exporter 验证行为。
- 新增 ADR 0008，取代 ADR 0007 中超出当前 MVP 的客户端 tracing、生产采样、OTLP 和 exporter 脱敏决策。

## Capabilities

### New Capabilities

- `trace-context-propagation`: 定义服务端 HTTP trace 与 API/Celery/Worker 内部 W3C 上下文传播。

### Modified Capabilities

无。

## Impact

- 仅影响 backend telemetry 初始化、FastAPI middleware/instrumentation、结构化日志和 Celery instrumentation。
- 锁定 OpenTelemetry API/SDK、FastAPI instrumentation 与 Celery instrumentation。
- 不修改小程序，不启用生产 OTLP/Collector，不定义客户端 trace、生产采样、监控厂商或 Agent 语义。

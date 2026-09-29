# Spec Delta

## Purpose

定义 ProbeInterview 服务端 HTTP 请求与 Celery Worker 之间的最小标准追踪上下文，使后台执行能够关联原始服务端请求，而不提前引入客户端 tracing 或生产遥测平台。

## ADDED Requirements

### Requirement: 公网请求使用服务端 trace
系统 SHALL 为每个公网 HTTP 请求创建服务端 trace，SHALL 忽略客户端提供的 trace propagation header，并 SHALL 保留独立 request ID。

#### Scenario: 公网请求进入 API
- **WHEN** 请求缺少或携带任意 `traceparent`、`tracestate` 或 Baggage
- **THEN** API 创建新的 SERVER trace/span，并在响应中返回独立 `X-Request-ID` 与 `X-Trace-ID`

#### Scenario: API 记录请求日志
- **WHEN** API 在请求处理期间记录结构化日志
- **THEN** 日志包含同一 request ID、trace ID、span ID、trace flags 和 API service resource

#### Scenario: 请求 URL 包含 query
- **WHEN** 公网请求 URL 包含 query 参数
- **THEN** span attribute 和 event 不包含原始 query 值

### Requirement: Celery 延续服务端 trace
系统 SHALL 在 Celery message header 中传播 API 创建的 W3C Trace Context，并 SHALL 使 Worker 执行关联原始服务端请求和稳定 job ID。

#### Scenario: API 发布后台消息
- **WHEN** API 在活动服务端 span 内发布只携带稳定 job ID 的 Celery 消息
- **THEN** producer 注入 W3C Trace Context，且 header 不包含 Baggage、请求正文或私人业务内容

#### Scenario: Worker 消费消息
- **WHEN** Worker 收到合法 trace context
- **THEN** Worker 创建相关联的 CONSUMER span，并在日志中记录同一 trace ID、独立 span ID、job ID 和 Worker service resource

#### Scenario: Worker 收到缺失或无效上下文
- **WHEN** Celery 消息没有合法 trace context
- **THEN** Worker 创建新的 trace 并继续执行，且 trace 缺失不导致业务失败

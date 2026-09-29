# ADR 0007: W3C Trace Context and OpenTelemetry

## Status

Superseded by [ADR 0008](0008-server-owned-public-traces-and-deferred-export.md)

## Date

2026-09-29

## Context

ProbeInterview 需要把微信小程序的一次用户动作、FastAPI 请求、Celery 消息和 Worker 执行关联为可移植的因果链。现有运行基础只把单次 HTTP 的 request ID 复用为 trace ID，不能表达标准父子关系，也不能直接接入兼容 OpenTelemetry 的监控平台。

追踪属于跨运行单元的基础设施能力，不是业务状态真相。遥测后端不可用时，HTTP 请求、数据库事务和后台任务仍必须正确执行；同时日志和 span 不得泄露请求正文、私人知识、完整 Prompt 或模型响应、密钥、令牌和连接信息。

本决策需要引入 OpenTelemetry Python API、SDK、FastAPI/Celery instrumentation 和 OTLP exporter 作为后端主要依赖，因此必须在添加依赖前明确协议、采样、隐私和供应商隔离边界。

## Decision

HTTP 和 Celery message header 使用 W3C Trace Context：

- `traceparent` 是跨边界传播 trace ID、parent span ID 和 trace flags 的唯一协议；
- `tracestate` 仅在符合 W3C 限制时传播，无效值被丢弃且不影响业务请求；
- `X-Request-ID` 独立标识一次 HTTP 请求；
- `X-Client-Action-ID` 关联小程序的一次用户意图；
- 稳定业务 `job_id` 关联后台任务及其重试；
- 响应中的 `X-Trace-ID` 只用于诊断展示，不能作为后续请求的父上下文。

合法的外部 `traceparent` 由 OpenTelemetry 自动提取并继续同一 trace，同时为 SERVER span 生成新的 span ID；缺失或无效上下文由 OpenTelemetry 自动创建新的 trace。应用不手写或重新生成合法的 trace ID。公开 HTTP 边界不信任远程 `sampled` 位：production 使用本地配置的采样比例决定 SERVER span 是否记录和导出，随后由服务内部的子 span、Celery producer 和 Worker 继承该本地决定。

后端使用官方 OpenTelemetry Python API/SDK、FastAPI instrumentation、Celery instrumentation 和 OTLP trace exporter。初始化、semantic convention 映射、自定义属性、sampler 和 exporter 只位于 `platform/foundation` infrastructure 边界；domain 和 application 代码不得导入 OpenTelemetry、OTLP 或监控厂商 SDK。

全局 propagator 只启用 W3C Trace Context，不启用 W3C Baggage。入站 `baggage` header 被忽略，不得进入 Celery header、span 或日志。

API 和 Worker resource 至少包含：

- `service.namespace=probeinterview`；
- `service.name=probeinterview-api` 或 `probeinterview-worker`；
- `service.version`；
- `deployment.environment.name`。

标准属性优先使用锁定依赖版本对应的 OpenTelemetry semantic conventions。缺少标准字段时使用版本化的 `probeinterview.*` 命名空间。Span 名称使用路由模板、任务类型或稳定操作名，不包含 actor ID、job ID、URL 实参或用户文本。

采样与导出遵循以下规则：

- development 和 test 默认全采样，可使用 in-memory exporter 做确定性断言；
- production 启用 OTLP 时必须显式配置合法采样比例；公开入口的远程父上下文按本地 trace-id-ratio 策略采样而不继承远程 `sampled` 位，服务内部的本地父子关系使用 parent-based 策略继承本地决定；
- 未配置 OTLP endpoint 时不导出 trace，但传播、span/log 关联和业务执行继续工作；
- OTLP 使用有界批量队列和短超时；队列满、超时或后端拒绝只产生限流后的安全诊断，不得向请求或 Worker 抛出遥测异常；
- exporter 只接受标准 OTLP 配置，应用代码不感知 ARMS、SLS 或其他具体平台。

结构化日志从当前 span context 读取小写十六进制 `trace_id`、`span_id` 和 `trace_flags`，并在适用时附带 request ID、client action ID、job ID 和上述 service resource。普通日志、span attribute 和 exception event 不记录请求正文、私人来源文本、完整 Prompt 或模型响应、密钥、令牌、连接串、原始异常 message、局部变量或 W3C Baggage 中的身份与业务 payload。

异常诊断保留异常类型、稳定错误码、由模块名/函数名/行号组成的有界安全堆栈帧和稳定 fingerprint。原始 traceback 只用于不进入日志或 exporter 的受控本地调试与测试失败输出。

本决策只建立通用 trace context 与 trace exporter 边界，不定义 Agent run、step、tool、model、Token、成本、评估或回放语义。未来 Agent runtime change 可以复用该上下文，但必须独立定义 Agent 语义。

## Alternatives

### 使用自定义 Trace ID header

实现简单，但不能表达标准 span 父子关系，会失去与兼容云平台、Collector 和自托管后端的互操作性。

### 直接使用云厂商监控 SDK

可以更快接入单一平台，但会把供应商配置和数据模型扩散到应用代码，增加迁移成本并违反既有 adapter 边界。

### 手写 tracing SDK

可以减少依赖数量，但 W3C 解析、上下文传播、采样、批处理和 OTLP 导出容易产生规范错误，维护成本高于使用标准实现。

### 立即在小程序引入浏览器 OpenTelemetry SDK

可以创建完整客户端 span，但当前没有其适配微信小程序运行时的兼容性证据。小程序先使用统一请求封装、client action ID 和可替换 trace-context provider。

## Consequences

- 后端锁文件将增加 OpenTelemetry API/SDK、FastAPI/Celery instrumentation 和 OTLP exporter。
- API、Worker 和小程序必须通过 W3C context、request ID、client action ID 和 job ID 的明确职责关联，不能继续复用同一个标识。
- 监控平台可通过 infrastructure 配置替换，业务模块和传播协议不需要修改。
- 默认关闭导出降低本地和测试环境门槛，但 production 启用 OTLP 时必须显式配置采样。
- 遥测故障不会改变业务结果；排障依赖安全的结构化标识和摘要，而不是记录私人正文。
- Agent 语义、日志采集、metrics、Collector、Dashboard 和告警仍由后续独立 change 决定。

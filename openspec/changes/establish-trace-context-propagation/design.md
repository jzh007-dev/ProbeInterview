# Design

## Context

本 change 的动机见 `proposal.md`，行为契约见 `specs/trace-context-propagation/spec.md` 与 `specs/runtime-api-foundation/spec.md`。当前 FastAPI middleware 接受或生成 `X-Request-ID`，并把同一值直接绑定为 trace ID；JSON 日志只有 request、trace 和 job 三类关联字段。Celery 尚未传播上下文，小程序也没有统一请求封装。

设计遵循 `docs/architecture.md`、ADR 0003、0004、0005 和 0006。Trace 是跨运行单元的基础设施能力，不是业务状态真相；遥测失败不得改变 HTTP、数据库或后台任务结果，普通日志和 span 属性不得包含私人正文、完整 Prompt/模型响应、密钥或令牌。

OpenTelemetry Python API/SDK、instrumentation 和 OTLP exporter 是新的主要依赖。实施必须先新增并接受 ADR 0007，确认 W3C Trace Context、OpenTelemetry 数据模型、OTLP 出口和供应商隔离边界，再同步 `docs/architecture.md`、ADR 索引和 `openspec/config.yaml`；该步骤完成前不得添加依赖或实现埋点。

## Goals / Non-Goals

**Goals:**

- 固定 W3C `traceparent`/`tracestate`、独立 `X-Request-ID`、`X-Client-Action-ID` 和诊断用 `X-Trace-ID` 的职责。
- 使用 OpenTelemetry Python API/SDK 让 FastAPI 与 Celery 产生具有正确父子或链接关系的 span。
- 让结构化 JSON 日志从活动 span 读取标准 trace ID、span ID 和 trace flags，并附带稳定服务资源字段。
- 通过可选 OTLP exporter 保持对兼容云平台或自托管平台的可移植性。
- 为小程序提供统一请求封装和安全关联信息，而不引入尚未验证适配微信运行时的浏览器遥测 SDK。

**Non-Goals:**

- 不部署 OpenTelemetry Collector，不接入 ARMS、SLS 或其他具体平台，不建设 Dashboard、告警、日志索引或指标系统。
- 不实现 Trace 数据库、Probe 表、业务 API、业务后台任务或完整产品 E2E。
- 不定义 Agent run、step、tool、model、Prompt、Token、成本、评估或回放语义。
- 不向小程序增加诊断页面或视觉状态；本 change 只增加请求基础设施，因此不涉及 `docs/design/visuals/` 页面参考。
- 不使用 W3C Baggage 传播 actor ID、capability、私人内容或业务 payload。

## Decisions

### 1. W3C Trace Context 是唯一跨边界传播协议

HTTP 与 Celery message header 使用 W3C `traceparent` 和可选 `tracestate`。`X-Request-ID` 继续标识单次 HTTP 请求，`X-Client-Action-ID` 关联小程序的一次用户意图，稳定业务 `job_id` 关联后台任务；这些标识不替代 trace/span context。

FastAPI 接受格式合法的 `traceparent`，无值或无效时由 OpenTelemetry SDK 创建新 trace。外部 `tracestate` 按 W3C 限制验证；不符合限制时丢弃，不能导致请求失败。响应继续返回 `X-Request-ID`，并返回仅用于排障展示的 `X-Trace-ID`；后续请求的传播仍使用 `traceparent`，不能把 `X-Trace-ID` 当作父上下文。

小程序统一请求封装为每次关键用户动作附加 `X-Client-Action-ID`，并允许未来前端监控 adapter 提供标准 `traceparent`/`tracestate`。当前默认实现不自行模拟完整前端 span exporter：没有 provider 时由 API 创建 trace，客户端从响应保存 `X-Request-ID` 与 `X-Trace-ID` 用于错误关联。

使用自定义 `X-Trace-ID` 作为传播协议会失去供应商互操作；立即引入浏览器 OpenTelemetry SDK则没有微信小程序运行时兼容性证据，因此两者均不采用。

### 2. 后端使用 OpenTelemetry Python API/SDK 与官方 instrumentation

ADR 0007 接受后，backend 锁定兼容版本的：

- `opentelemetry-api`；
- `opentelemetry-sdk`；
- `opentelemetry-instrumentation-fastapi`；
- `opentelemetry-instrumentation-celery`；
- `opentelemetry-exporter-otlp`。

FastAPI instrumentation 创建 SERVER span；Celery instrumentation 在 publish/consume 边界注入和提取 context，并为生产与消费创建相应 span。项目代码只通过 platform/foundation infrastructure 初始化 tracer provider、resource、sampler 和 exporter；domain/application 不导入 OpenTelemetry 或厂商 SDK。

自动 instrumentation 与现有 middleware 分工：OpenTelemetry 负责 span 生命周期和标准属性，现有 middleware 负责 request ID、Problem Details 与安全应用日志。测试必须证明不会为同一 HTTP 请求或 Celery 执行重复创建项目自定义根 span。

手写完整 tracing SDK 会增加规范错误与导出兼容成本；直接使用 ARMS 或其他厂商 SDK 会把供应商选择扩散到应用，因此均不采用。

### 3. Resource、span 和日志字段使用稳定规范

API 与 Worker 使用：

- `service.namespace=probeinterview`；
- `service.name=probeinterview-api` 或 `probeinterview-worker`；
- `service.version` 来自应用构建版本；
- `deployment.environment.name` 来自已校验的运行 profile。

HTTP、异常和消息属性优先使用当前锁定版本的 OpenTelemetry semantic conventions。项目属性集中登记在 infrastructure 的属性模块中，并使用 `probeinterview.*` 命名空间。Span 名称使用路由模板、任务类型或稳定操作名，不包含 actor ID、job ID、URL 实参或用户文本。

JSON 日志保留现有安全摘要，并从当前 span context 输出小写十六进制 `trace_id`、`span_id` 和 `trace_flags`；适用时继续输出 request ID、client action ID 和 job ID。日志还输出与 span 一致的 service namespace、name、version 和 environment。Semantic conventions 随锁文件固定，升级时只修改 infrastructure 映射和 schema URL，不让业务模块依赖版本特有字段。

### 4. OTLP 只在 infrastructure 启用且默认关闭

Trace exporter 使用 OTLP，并接受标准 OTEL exporter endpoint、protocol、headers、timeout 和 sampler 配置；项目 Settings 对启用条件和取值做类型化校验。未配置 endpoint 时使用无导出的 provider，trace context、span/log correlation 和测试仍然工作。

Development/test 默认全采样并使用 in-memory exporter 断言；production 只有在显式配置 OTLP 时才启用批量 exporter，并必须显式设置合法采样比例。Exporter 使用有界队列、批量处理和短超时；队列满、超时或后端拒绝时只产生限流后的安全内部诊断，不向业务请求抛出异常。

本 change 只导出 traces。结构化日志继续写 stdout，由未来部署或平台按需采集；metrics 由独立 change 决定。这样可以验证云平台可移植出口，又不把 Collector 或厂商部署加入当前范围。

### 5. Celery 重试使用独立尝试 span 和稳定 job 关联

Producer 注入 trace context 时不改变现有“消息只携带稳定 ID”约束。Worker 为每次实际执行建立独立 span；重试不是覆盖原 span，而是通过继承或 link 与原后台操作关联，并使用稳定 job ID 将多次尝试聚合。

若消息没有合法上下文，Worker 创建新 trace 并继续执行。Trace 缺失不能成为任务失败原因。Celery task ID 只表示一次队列执行，不替代 PostgreSQL 中未来业务任务的稳定 job ID。

### 6. 小程序只实现关联封装，不实现监控平台

小程序新增共享请求模块，负责：

- 接收调用方的 client action ID，或为一次显式用户意图创建安全的本地关联 ID；
- 注入 `X-Client-Action-ID`，以及可选 provider 返回的 `traceparent`/`tracestate`；
- 保存响应的 `X-Request-ID` 与 `X-Trace-ID`；
- 把网络失败、Problem Details 和关联标识映射为不含正文的错误对象；
- 对同一用户动作的重试保留 client action ID，但让每次 HTTP 尝试获得独立 request ID。

当前不增加页面或产品导航。自动化测试使用可替换的 request adapter 验证 header、错误映射和重试关联；不依赖真实网络或监控平台。

## Risks / Trade-offs

- [客户端提供的 trace context 被滥用或格式污染] → 严格按 W3C 解析，拒绝全零/超长/非法值，不把 trace ID 当作身份或授权依据。
- [高基数属性增加监控费用] → ID 只进入 trace/log 关联字段，不进入指标维度；span 名称和公共属性保持低基数。
- [Exporter 阻塞请求或 Worker] → 默认关闭、批量异步导出、有界队列和短超时，任何导出错误与业务异常隔离。
- [自动 instrumentation 产生重复或不稳定 span] → 集中初始化一次，并以 in-memory exporter 测试 span 数量、kind 和父子关系。
- [OpenTelemetry semantic conventions 演进] → 锁定依赖和 schema version，版本差异只在 infrastructure 映射。
- [小程序没有完整前端 span] → 当前以 client action ID 和响应 trace ID 建立可靠关联；未来前端监控 adapter 可通过标准 trace context 接入，无需改变 API。
- [标准遥测意外包含敏感值] → 禁止自动捕获 body、query value、Prompt 或模型输出，并对 span attributes 与日志执行同一安全字段策略。

## Migration Plan

1. 新增并接受 ADR 0007，记录 W3C Trace Context、OpenTelemetry Python、OTLP、采样和供应商隔离决策，同步架构、ADR 索引和 OpenSpec 配置。
2. 增加锁定的 backend OpenTelemetry 依赖、类型化 telemetry 设置、resource/sampler/provider 初始化和 in-memory 测试 exporter。
3. 将 FastAPI request ID middleware 与 OpenTelemetry SERVER span 关联，增加 `X-Trace-ID` 并升级 JSON 日志字段；保持现有 API 响应与 Problem Details 兼容。
4. 为 Celery producer/Worker 启用标准 context 注入、提取和执行 span，验证正常消费、缺失上下文和重试关系。
5. 增加小程序共享请求封装与类型测试，验证 client action、可选 trace context、响应关联和安全错误映射。
6. 在未配置 OTLP 的 development/test 环境运行 focused checks；再使用本地接收器或 in-memory exporter 验证标准导出契约，不连接真实云平台。

部署采用向后兼容顺序：先部署 API/Worker，使其能接受有或无 trace context 的请求和消息；再让小程序发送 client action 或未来 trace context。回滚时关闭 OTLP 配置并移除 instrumentation，保留 `X-Request-ID` 与原结构化日志行为，不涉及数据库迁移或业务数据回滚。

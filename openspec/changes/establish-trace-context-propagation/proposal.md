# Proposal

## Why

现有运行基础只把单次 HTTP 的 request ID 复用为 trace ID，尚不能把小程序用户动作、API 请求、Celery 消息和 Worker 执行表示为标准、可移植的因果链。前后端并行开发开始前需要先固定厂商无关的 Trace 契约，使后续功能和未来云监控接入不必重写传播与埋点边界。

## What Changes

- 采用 W3C Trace Context 作为 HTTP 与异步消息的传播协议，明确 request ID、trace ID、span ID、trace flags、client action ID 和 job ID 的不同职责。
- 为微信小程序建立统一请求追踪封装，使关键用户动作、请求尝试、响应错误和后端 trace 可以关联，而不记录页面输入或私人业务正文。
- 使 FastAPI 接受或创建合法 trace context，为每次 HTTP 请求创建服务端 span，并继续保留独立的 `X-Request-ID` 排障标识。
- 使 Celery producer 在消息 header 注入 trace context，Worker 提取上下文并创建消费 span；消息仍只携带稳定业务 ID，不携带私人内容。
- 按 OpenTelemetry 数据模型与稳定语义约定规范化 span、resource 和日志关联字段，并为项目自定义字段使用 `probeinterview.*` 命名空间。
- 在 infrastructure 边界提供可配置的 OTLP 导出能力；未配置 exporter 时本地开发、测试和业务执行仍可正常工作，且不接入具体云厂商、Collector、Dashboard 或告警平台。
- 在添加 OpenTelemetry 主要依赖前新增并接受对应 ADR，同步 `docs/architecture.md`、ADR 索引和 `openspec/config.yaml`。
- 明确排除 Agent run/step/tool/model 语义 Trace；该能力由实际 Agent runtime 的后续 change 定义并复用本 change 的 trace context。

## Capabilities

### New Capabilities

- `trace-context-propagation`: 定义小程序、HTTP API、Celery producer/Worker 之间的标准 trace context 传播、span 关系、资源标识、隐私和可选 OTLP 导出行为。

### Modified Capabilities

- `runtime-api-foundation`: 将现有 request/trace/job 日志约定扩展为独立 request ID、W3C trace context、标准 span/log 关联字段和安全降级行为。

## Impact

- 依赖已归档的 `establish-runtime-api-foundation`，并应在后续前端 API、后台任务和 Agent changes 之前完成。
- 影响小程序请求基础封装、FastAPI middleware、结构化日志上下文、Celery 消息 header 与 Worker 执行上下文、运行配置和自动化测试。
- 计划引入 OpenTelemetry Python API/SDK 与 OTLP exporter；依赖增加必须由本 change 首个任务中的新 ADR 接受后才能实施。
- 不创建 Trace 数据库或 Probe 表，不实现业务工作流，不绑定 ARMS、SLS 或其他监控厂商，也不记录完整 Prompt、模型响应、请求正文、私人知识、密钥或令牌。

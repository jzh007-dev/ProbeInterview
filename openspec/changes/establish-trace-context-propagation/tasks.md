# Tasks

## 1. 服务端 HTTP Trace

- [x] 1.1 新增并接受精简的 ADR 0008，取代 ADR 0007 中超出当前 MVP 的客户端 tracing、生产采样、OTLP 与 exporter 脱敏决策，并同步 `docs/architecture.md`、`docs/adr/README.md` 与 `openspec/config.yaml`；以 `openspec validate establish-trace-context-propagation --strict` 验证规划一致
- [ ] 1.2 锁定 OpenTelemetry API/SDK 与 FastAPI/Celery instrumentation，移除 OTLP exporter 和生产采样配置，实现 API resource/provider、仅 Trace Context 的 propagator、公网 trace header 丢弃、FastAPI SERVER span、独立 `X-Request-ID`、诊断用 `X-Trace-ID`、安全 URL 属性与标准日志关联字段；以 `cd apps/backend && uv run pytest tests/unit && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy` 验证任意公网 trace header 均产生新的服务端 trace、Problem Details 保留关联 header、query 不进入 span、只有一个 SERVER 根 span，以及 production provider 使用固定关闭采样且没有 span processor 或 OTLP 配置但仍提供有效关联 context

## 2. Celery 内部传播

- [ ] 2.1 使用官方 Celery instrumentation 配置 producer/Worker 的 W3C context 注入与提取，使合法上下文产生相关联的 PRODUCER/CONSUMER span，缺失或无效上下文创建新 trace，并保持消息只携带稳定 job ID 与安全 header；以 `cd apps/backend && uv run pytest tests/unit -k "trace or telemetry or celery"` 验证父子关系、job ID 日志关联、service resource、无 Baggage 和私人内容

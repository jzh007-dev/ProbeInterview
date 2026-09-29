# Tasks

## 1. 固定标准并交付 HTTP Trace

- [x] 1.1 新增并接受 ADR 0007，确认 W3C Trace Context、OpenTelemetry Python/OTLP、采样、隐私和供应商隔离边界，同步 `docs/architecture.md`、`docs/adr/README.md` 与 `openspec/config.yaml`；以文档对账和 `openspec validate establish-trace-context-propagation --strict` 验证规划与架构约束一致
- [x] 1.2 在 ADR 0007 接受后锁定 OpenTelemetry backend 依赖，实现类型化 telemetry 配置、resource/sampler/provider 初始化、仅 Trace Context 的 propagator、FastAPI SERVER span、合法/缺失/无效 `traceparent` 处理、公开入口不信任远程采样位、独立 `X-Request-ID`、诊断用 `X-Trace-ID`、受限 `X-Client-Action-ID` 和标准日志关联字段；以 `cd apps/backend && uv run pytest tests/unit && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy` 验证正常请求、Problem Details、无效上下文、伪造采样位、Baggage 被忽略、安全异常 stack/fingerprint、敏感字段排除和单一根 span

## 2. 交付 Celery 传播与可选导出

- [ ] 2.1 为 Celery producer/Worker 配置标准 context 注入与提取，使正常消费、缺失上下文和重试尝试按“CONSUMER → retry PRODUCER → next CONSUMER”的父子链产生可区分且可关联的 span，并保持消息只携带稳定任务 ID、Trace Context 和安全 header；以 `cd apps/backend && uv run pytest tests/unit -k "trace or telemetry or celery"` 验证 trace/parent 关系、job ID 关联、独立重试 span、无 span link、Baggage 和私人内容不进入 header
- [ ] 2.2 实现默认关闭的 OTLP trace exporter、development/test in-memory exporter、production 显式采样配置、有界批量队列和导出失败隔离，随行为更新 `docs/development.md`；以 `cd apps/backend && uv run pytest tests/unit -k "telemetry or otlp"` 验证未配置 endpoint、超时、拒绝和队列压力均不改变 API 或 Worker 结果

## 3. 交付小程序请求关联与跨边界验收

- [ ] 3.1 建立小程序共享请求封装和可替换 request/trace-context provider，支持生成或校验最多 128 字符的安全 `X-Client-Action-ID`、可选 `traceparent`/`tracestate`、响应 `X-Request-ID`/`X-Trace-ID`、重试关联和不含正文的错误映射，并配置 Jest + `miniprogram-simulate` 测试入口；以 `cd apps/miniprogram && npm run typecheck && npm test` 验证成功、无效 client action ID、网络失败、Problem Details、同一动作重试和无 provider 场景
- [ ] 3.2 使用 in-memory exporter 与小程序 request mock 完成“客户端动作 → FastAPI → Celery producer/Worker”的契约验收，证明 trace context、独立 request ID、client action ID、job ID、service resource 和日志字段一致且 Agent 语义、Probe 表和云厂商配置未被引入；以 `scripts/test-compose-topology`、`cd apps/backend && uv run pytest tests/unit && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy` 及 `cd apps/miniprogram && npm run typecheck && npm test` 全部通过作为验收证据

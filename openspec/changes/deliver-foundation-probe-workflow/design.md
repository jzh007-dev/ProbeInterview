# Design

## Context

本 change 的动机见 `proposal.md`，行为契约见 `specs/foundation-probe-workflow/spec.md`。它依赖已归档的 `establish-persistence-actor-isolation`，承接原任务 3.1–3.4，并消费已存在的 HTTP、日志、ActorContext、probe job/vector schema 和 owner-scoped repository 契约。

设计遵循 `docs/architecture.md`、ADR 0002、0003、0004、0006。Foundation probe 是开发与验证能力，不是产品功能；真实供应商 adapter、微信登录、知识和面试实体均不进入本 change。

小程序只新增 development 诊断页。视觉使用 `docs/design/visuals/ui-direction.html` 的 Soft Bento / Gaussian Glass 方向作为风格参考；该视觉文件来自 MVP 方向讨论，不扩充诊断页功能范围。

## Goals / Non-Goals

**Goals:**

- 用一个稳定 probe ID 串通创建、持久化、投递、Worker、fake adapter、pgvector 和状态轮询。
- 实现 HTTP 202 + Location、幂等键、input hash 冲突、有限状态和安全错误摘要。
- 在至少一次投递、Worker 中断和投递空窗下保持数据库真相与单一结果。
- 通过 development 诊断页覆盖初始空态、加载、运行、成功和错误状态。

**Non-Goals:**

- 不实现通用工作流引擎、transactional outbox、复杂补偿或多步骤业务编排。
- 不实现正式微信登录、真实 OSS、百炼 LLM/Embedding、OCR、ASR 或 production fake fallback。
- 不建立知识、卡片、面试或复盘实体，也不验证模型质量。
- 不建立根级 `scripts/verify` 或完整 Compose E2E；这些属于下一 change。

## Decisions

### 1. Probe 使用独立开发/验证 API，不伪造业务实体

验证环境提供：

- `POST /api/v1/foundation/probes`
- `GET /api/v1/foundation/probes/{probe_id}`

创建入口只在 development、test 或显式允许的验证环境开放，production 默认关闭。创建成功返回 HTTP 202、`Location`、`X-Request-ID` 和类型化任务资源；查询返回 `QUEUED`、`RUNNING`、`SUCCEEDED` 或 `FAILED`、尝试次数、时间戳与非敏感摘要。

使用独立 probe 避免把首个知识或面试 API 变成基础设施测试夹具。Probe 成功只证明编排链路，不承诺业务检索或模型质量。该协议遵循 ADR 0004。

### 2. 命令幂等由 actor、命令类型、键和输入摘要共同决定

创建请求要求 `Idempotency-Key`。应用服务以 actor、命令类型、幂等键和规范化 input hash 创建或复用 job：

- 同 actor、同键、同输入返回既有任务及当前状态；
- 同 actor、同键、不同输入返回 RFC 9457 格式的 409；
- 不同 actor 的相同键互不冲突。

Job、响应、日志和后台执行保留创建请求的 request ID。只按幂等键判重会错误合并不同 actor 或输入，因此被排除。

### 3. Celery 消息只携带 probe ID

API 在数据库事务中创建或复用 job，提交后投递只含稳定 `probe_id` 的消息。Redis/Celery 不保存最终产品状态，也不携带输入正文、Prompt、完整可变 payload 或私密内容。

Worker 读取并锁定 job，终态直接安全返回；非终态进入 RUNNING 并执行：

1. fake object storage 小文本 put/get/delete；
2. fake embedding 生成固定测试向量；
3. 在当前 actor scope 写入 probe vector；
4. 在同一 scope 执行最近向量查询并验证返回自身；
5. 原子写入 SUCCEEDED 与安全摘要。

异常按配置有限重试，最终失败写入稳定错误码。重复消息不得产生第二份成功结果。该任务模型遵循 ADR 0003。

### 4. QUEUED 状态覆盖提交后投递空窗

本 change 不实现 transactional outbox。数据库提交成功但 dispatch 失败时保留 QUEUED job 和安全 dispatch 摘要；显式恢复命令重新投递超过阈值且尚未进入终态的 probe ID。

恢复命令从 PostgreSQL 选择稳定 ID，不从日志或 Redis 重建输入。未来若后台流程需要严格投递保证或多步骤补偿，必须以新 ADR 评估 outbox 或工作流引擎。

### 5. 外部能力通过端口和 deterministic fake adapter

Foundation 定义：

- `ObjectStorage`
- `EmbeddingProvider`
- `StructuredLlmClient`

Development/test 加载 deterministic fake。Fake 对相同输入返回可预测结果，支持显式成功/失败，记录不含正文的调用元数据，并遵守与真实 adapter 相同的应用端口。Probe 主路径使用 fake storage 与 fake embedding；fake LLM 只做契约测试，不人为扩展闭环。

真实供应商 SDK 只能由后续 infrastructure adapter 引入，domain/application 不导入 SDK。Production 不得加载 fake adapter 或把它作为降级答案。该边界遵循 ADR 0006。

### 6. 小程序诊断页只在 development 构建存在

诊断页复用 TDesign 与现有 TypeScript 工程，只提供 probe 开发操作，不进入产品导航。页面状态为：

- **Empty/initial**：尚未创建 probe，展示用途说明与创建操作；
- **Loading**：创建请求或轮询进行中，禁用重复创建并保留同一幂等意图；
- **Running**：展示 QUEUED/RUNNING、任务 ID、request ID 和最近更新时间；
- **Success**：展示 SUCCEEDED、完成时间和非敏感摘要并停止轮询；
- **Error**：展示创建/轮询 Problem Details 或 FAILED 稳定错误码，不展示后台异常详情。

组件测试覆盖状态转换、轮询停止、错误映射、重复点击和 production 构建不暴露入口。参考视觉只指导间距、卡片、状态层级与颜色，不引入首页、导航或产品化运营内容。

## Risks / Trade-offs

- [Probe 入口误暴露到 production] → 配置、路由注册和小程序构建三层限制，production 自动化测试验证不可用。
- [至少一次投递产生重复副作用] → 消息只带 ID，Worker 锁定 job、检查终态并依赖数据库唯一约束。
- [提交后投递失败造成 QUEUED 卡住] → 保留数据库真相并提供只重投稳定 ID 的恢复命令。
- [Fake 被误解为供应商质量验证] → specs、UI 摘要和文档明确只验证契约与编排，不证明模型质量。
- [诊断 UI 演变成产品页面] → 仅 development 构建注册，不进入 production 包和产品导航。

## Migration Plan

1. 定义三个应用端口、deterministic fake adapter 和契约/脱敏测试。
2. 实现 probe 创建/查询应用服务与 API，覆盖 202、Location、request ID、幂等复用和 409。
3. 实现 Celery 任务、有限重试、终态幂等、QUEUED 恢复与 owner-scoped pgvector 步骤。
4. 实现 development 诊断页及 empty/loading/running/success/error 组件测试。
5. 使用 focused API、数据库、Worker 和小程序测试验收本 change；完整 Compose E2E 留给 `complete-foundation-verification`。

这是 greenfield 验证工作流。回滚时关闭 probe 路由与诊断构建入口并停止投递新任务；已持久化 job 保留用于审计，不删除其他 actor 或后续业务数据。

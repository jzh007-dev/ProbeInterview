# ADR 0006: External adapters and verification strategy

## Status

Accepted

## Date

2026-09-28

## Context

ProbeInterview 未来依赖阿里云 OSS、百炼 LLM、Embedding，以及可能增加的 OCR、ASR 和 Rerank 服务。如果供应商 SDK 进入领域或应用逻辑，测试将依赖网络、云密钥和不可重复的模型结果，供应商替换也会扩散到业务代码。

`setup-foundation` 需要自动证明小程序、API、数据库、队列、Worker 和 pgvector 的完整链路，但不应因尚未实现真实知识功能而调用付费云服务。项目目前也没有确定代码托管平台，因此验证契约不能绑定某个 CI 厂商。

## Decision

应用层通过明确端口使用外部能力。foundation 至少定义：

- `ObjectStorage`；
- `EmbeddingProvider`；
- `StructuredLlmClient`。

供应商 SDK、鉴权、重试和供应商响应映射只能位于 infrastructure adapter。领域与应用代码不得直接导入 OSS 或百炼 SDK。

Development/test profile 使用确定性 fake adapter。Fake 必须：

- 对相同输入返回可预测结果；
- 支持成功和显式失败场景；
- 记录不含私人正文的调用元数据供测试断言；
- 遵守与真实 adapter 相同的应用端口契约；
- 不模拟业务智能或作为生产降级答案。

Production 启用真实 adapter 时必须在启动阶段校验必需配置；缺失配置应明确失败。Production 不得加载 fake adapter。真实 OSS 和百炼 adapter 由首次消费它们的功能 change 实现，而不是由 `setup-foundation` 提前实现。

仓库提供一个根级 `scripts/verify` 作为本地和 CI 的唯一完整验证入口，至少覆盖：

1. 后端格式、lint、类型检查和单元测试；
2. 小程序格式、类型检查以及 Jest + `miniprogram-simulate` 组件测试；
3. Alembic 空库升级和 schema 约束测试；
4. PostgreSQL、pgvector、owner 隔离和 repository 集成测试；
5. Redis/Celery 的重试、重复投递和恢复测试；
6. 使用真实本地 PostgreSQL、pgvector、Redis、API、Worker 和 gateway 的 foundation probe 端到端测试。

端到端测试使用 local actor 和 fake 云服务 adapter，因此不需要真实 OSS、LLM 或 Embedding 凭证。每层验证必须返回可靠的非零失败码，并使用隔离、可清理的测试数据。

CI 托管平台暂不确定。未来无论选择 GitHub Actions 或其他平台，workflow 只负责编排环境并调用同一个 `scripts/verify`，不复制验证逻辑。

## Alternatives

### Call real cloud services in foundation tests

可以验证供应商网络连接，但测试会产生费用、需要密钥、受到配额和模型非确定性影响，也超出 foundation 范围。

### Mock vendor SDK calls directly

测试编写较快，但会让应用层依赖供应商数据结构，无法证明应用端口在替换实现后仍然稳定。

### Provide fake adapters as production fallback

能让请求表面成功，但会生成虚假知识或评估结果，属于不可接受的数据完整性风险。

### Put all verification logic in hosted CI

会使本地验证和 CI 行为分叉，并在尚未选择代码托管平台时形成不必要绑定。

## Consequences

- 后续真实云服务 change 必须提供端口契约测试，并验证供应商错误被映射为稳定内部错误。
- `setup-foundation` 可以完整验证运行拓扑而不产生云调用费用。
- Fake 只能证明系统编排与契约，不能证明模型质量；模型质量需要后续离线评估。
- 根级验证时间会长于纯单元测试，因此必须分阶段报告失败位置，同时保留快速的局部测试命令。
- CI provider 的延期不阻塞 foundation；`scripts/verify` 的可重复执行才是准入条件。


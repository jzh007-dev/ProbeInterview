# Proposal

## Why

分层测试和完整 probe 链路存在后，项目仍需要一个全新环境可重复执行、CI 平台无关且失败阶段清晰的统一验收边界。本 change 将现有局部检查收口到根级验证入口，并用隔离 Compose E2E 证明完整 foundation walking skeleton。

## What Changes

- 建立根级 `scripts/verify`，依次运行 backend 格式、lint、类型、单元测试，小程序类型与组件测试，迁移、owner/pgvector 和 Celery 集成测试。
- 让每个验证阶段稳定返回非零失败码并报告失败阶段，文档化本地与未来 CI 的唯一完整调用方式。
- 使用隔离 Compose 环境运行“小程序请求等价客户端 → Caddy → API → PostgreSQL → Redis → Worker → pgvector → 状态查询”端到端测试。
- 使用 local actor 和 fake adapter，不要求真实云凭证；测试数据、容器和卷在成功或失败后均可清理。
- 以全新环境成功运行和故障注入回归证明统一入口能捕获关键依赖链路破坏。
- 保持 CI 托管平台未决；未来 workflow 只调用 `scripts/verify`，不复制验证逻辑。

## Capabilities

### New Capabilities

- `foundation-verification`: 定义统一验证入口、分阶段失败语义、隔离 Compose E2E 和自动清理的验收行为。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 依赖 `deliver-foundation-probe-workflow` 完成并归档。
- 影响根级验证脚本、backend/miniprogram 测试编排、Compose E2E harness、测试数据清理和验证文档。
- 完成本拆分序列的最终验收边界；其完成后 foundation walking skeleton 才可作为后续产品 changes 的已验证依赖。
- 不绑定 GitHub Actions 或其他 CI 托管平台，也不扩充 foundation probe 或产品能力。

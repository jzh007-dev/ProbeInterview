# Design

## Context

本 change 的动机见 `proposal.md`，行为契约见 `specs/foundation-verification/spec.md`。它依赖已归档的 `deliver-foundation-probe-workflow`，承接原任务 4.1–4.2，并只负责把前四个 changes 已有的 focused checks 与可运行 probe 链路收口为统一验收入口。

设计遵循 `docs/architecture.md`、ADR 0005 和 ADR 0006。CI 托管平台仍未决定；本 change 的契约是本地与未来 CI 调用同一根级命令，而不是新增某个平台 workflow。

## Goals / Non-Goals

**Goals:**

- 建立本地和未来 CI 唯一的根级 `scripts/verify`。
- 按明确阶段运行 backend、小程序、迁移、owner/pgvector、Celery 和 E2E 验证。
- 使用真实本地 Caddy、API、PostgreSQL + pgvector、Redis 和 Worker 完成隔离 probe E2E。
- 保证失败返回非零状态、标识阶段，并在成功或失败后清理测试状态。

**Non-Goals:**

- 不补写前置 changes 应随行为交付的单元、组件或 focused integration tests。
- 不修改 probe 协议、任务状态机、actor scope、数据库 schema 或诊断页功能。
- 不选择或配置 GitHub Actions、GitLab CI 或其他托管 CI 平台。
- 不调用真实 OSS、百炼或其他付费云服务，也不评估模型质量。

## Decisions

### 1. 根级验证入口按依赖层次分阶段执行

`scripts/verify` 依次运行：

1. backend Ruff format/lint、mypy 和单元测试；
2. 小程序类型检查及 Jest + `miniprogram-simulate` 组件测试；
3. Alembic 空库升级、允许的 downgrade 和 schema 约束测试；
4. owner 隔离与 pgvector repository 集成测试；
5. Redis/Celery 重试、重复投递、终态幂等和 QUEUED 恢复测试；
6. 隔离 Compose foundation probe E2E。

每阶段打印稳定名称并在失败时返回非零状态。早期阶段失败后不继续运行依赖它的昂贵阶段，避免级联噪声。Focused commands 继续存在用于开发，但不能替代完整验收。

将验证逻辑只放在托管 CI 会造成本地/CI 分叉，因此所有实际步骤留在仓库脚本中。该策略遵循 ADR 0006。

### 2. E2E 使用真实本地运行单元与 fake 业务供应商

E2E harness 启动隔离的 Caddy、API、Worker、PostgreSQL + pgvector 和 Redis，并使用小程序请求等价客户端：

1. 经 Caddy 创建 foundation probe；
2. 验证 202、Location 和 request ID；
3. 轮询状态资源；
4. 等待 Worker 完成 fake storage、fake embedding 和 owner-scoped pgvector query；
5. 验证 SUCCEEDED 与非敏感摘要。

测试使用 local actor 和 deterministic fake adapter，不需要真实云凭证。使用真实本地运行单元证明编排和网络边界，但不证明供应商连接或模型质量。

### 3. 测试环境按运行实例隔离并始终清理

Harness 为每次运行生成独立 Compose project name、端口和数据卷。清理逻辑在成功、断言失败和正常信号终止路径执行，停止容器并删除测试网络、卷和数据。

测试不得复用 development 持久卷或 production 配置。若需保留失败现场，必须通过显式调试开关选择，默认验收仍自动清理；该开关不能改变 CI 默认行为。

### 4. 故障注入证明失败码和阶段定位

回归测试至少破坏一个受控阶段，验证根级入口返回非零状态并标识阶段。故障注入使用隔离测试夹具，不修改已提交实现或依赖外部服务故障。

关键链路回归由其最接近的 focused test 与最终 E2E 共同覆盖：API、数据库、任务投递、Worker 或 pgvector 中任一边界破坏时，至少一个阶段可靠失败。

### 5. 未来 CI 只准备环境并调用 scripts/verify

未来托管 workflow 只负责 checkout、安装 Docker/语言运行时等前置环境并调用 `scripts/verify`。它不得复制 lint、测试、migration 或 E2E 步骤。

这使 CI provider 的选择与更换不改变验收契约。平台特有缓存、并发和报告上传可以在不复制验证逻辑的前提下单独配置。

## Risks / Trade-offs

- [完整验证耗时较长] → 保留 focused commands，根级入口按阶段快速失败并清晰报告。
- [Compose E2E 在共享机器端口或卷冲突] → 每次运行使用独立 project name、动态端口和隔离卷。
- [失败清理丢失现场] → 默认保证可重复与无污染；显式本地调试开关可选择保留，但 CI 不启用。
- [托管 CI 尚未选择] → 验收只依赖仓库脚本和标准前置环境，不绑定平台。

## Migration Plan

1. 建立 `scripts/verify` 阶段编排并接入前置 changes 已有 focused checks。
2. 增加阶段失败回归，验证非零退出码与阶段名称。
3. 建立隔离 Compose E2E harness、请求等价客户端和自动清理。
4. 在满足文档前置条件的全新环境完成一次全量成功运行并记录可重复命令。
5. 更新本地/CI 验证文档，明确未来平台只调用 `scripts/verify`。

本 change 不迁移生产数据。回滚只移除统一编排与 E2E harness；前置 changes 的 focused checks 和运行能力保持不变。

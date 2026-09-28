# Design

## Context

本 change 的动机见 `proposal.md`，可观察行为见 `specs/platform-foundation/spec.md`。原 `setup-foundation` 已按独立验收边界拆分；本 change 只保留已完成的原 1.1–1.2，运行拓扑、持久化、probe 闭环和完整验证分别由后续 changes 承担。

项目级技术结论见 `docs/architecture.md`、`docs/adr/README.md` 和 ADR 0001、0005、0006。当前工作树已经提交工程骨架与配置实现；原 2.1 的未提交 Docker/Compose/Caddy 文件不属于本 design，必须原样留给 `establish-runtime-api-foundation`。

## Goals / Non-Goals

**Goals:**

- 固定 monorepo、module-first modular-monolith 和 API/Worker/小程序入口的目录边界。
- 通过锁文件和文档化命令使 backend 与小程序依赖可复现安装。
- 通过 Pydantic Settings 在启动前校验 development、test、production 配置及 production 安全限制。
- 让已完成的工程骨架与配置工作可以作为独立 change 验收并归档。

**Non-Goals:**

- 不建立 Docker Compose 运行拓扑、Caddy 代理、健康接口或 HTTP 中间件。
- 不建立数据库迁移、probe 表、pgvector smoke query、ActorContext 或 repository。
- 不实现 Celery probe、fake adapter、probe API、小程序诊断页或根级 `scripts/verify`。
- 不建立知识、卡片、面试或复盘领域能力，也不连接真实 OSS、百炼、OCR 或 ASR。

## Decisions

### 1. 使用单仓库和 module-first 模块化单体骨架

仓库按运行职责组织：

```text
apps/
  backend/        Python 包、FastAPI 与 Celery 独立入口
  miniprogram/    TypeScript 微信小程序
infra/
  compose/        后续 change 的本地与单机部署编排
scripts/          根级开发与验证入口
```

`apps/backend` 按业务模块组织，每个模块内部再按需要划分 `api`、`application`、`domain` 和 `infrastructure`。共享运行能力位于明确的 platform/foundation 边界，不建立全局 `utils` 堆放区；业务模块不得直接访问其他模块的 repository 或 ORM model。

选择单仓库是为了让客户端、API、Worker、契约和版本同步演进。多仓库或提前拆分微服务会在没有独立团队与发布节奏时增加协调成本。该结构遵循 ADR 0001。

### 2. 使用已接受的技术栈并锁定可复现依赖

- Backend 使用 Python 3.12、uv、FastAPI、Pydantic 2、pytest、Ruff 和 mypy。
- 数据与任务相关依赖使用 SQLAlchemy 2、Alembic、PostgreSQL + pgvector、Redis 和 Celery，但其运行行为由后续 changes 交付。
- 小程序使用 TypeScript、TDesign、Jest 和 `miniprogram-simulate`。
- 所有直接依赖通过锁文件固定，全新环境按锁文件安装，不在功能 change 中隐式升级主版本或替换框架。

替代方案使用未锁定依赖或在后续 change 临时选择工具，会使安装结果与验证基线漂移。引入新语言、框架、数据库、云服务或主要依赖仍需先有接受的 ADR。

### 3. 配置按 profile 类型化并在启动前失败

Pydantic Settings 定义 development、test 和 production schema。无密钥示例配置只提供非敏感占位和本地默认值；真实密钥只从环境或部署 secret injection 获取。

Production profile 必须拒绝：

- local actor；
- fake adapter 作为 production fallback；
- foundation probe 创建入口。

Development/test 可以在没有真实云凭证时通过配置校验，但这不代表 fake adapter 是 production 降级答案。选择启动前明确失败，避免运行到请求路径后才发现缺少凭证或误启用验证捷径。该边界遵循 ADR 0005 与 ADR 0006。

## Risks / Trade-offs

- [骨架提前包含未来依赖名称] → 只建立包、入口和配置边界；运行行为与领域表必须留在后续 change。
- [配置默认值成为 production 假设] → production 使用独立必填校验并拒绝 local/fake/probe 开关。
- [已完成 change 与未提交 2.1 代码混淆] → tasks 仅保留已提交的 1.1–1.2，并在 proposal/design 明确 2.1 归属下一 change。

## Migration Plan

1. 保留已提交的目录、锁文件、基础入口和配置实现。
2. 运行现有 clean-room skeleton、backend 单元/静态检查和小程序类型检查，确认 1.1–1.2 仍完成。
3. 归档 `setup-foundation` 后，再以 `establish-runtime-api-foundation` 恢复原 2.1 的未提交实现工作。

这是 greenfield 工程骨架，没有旧服务或用户数据迁移。回滚仅涉及本 change 已提交的骨架与配置提交，不得处理当前未提交的 Docker/Compose/Caddy 文件。

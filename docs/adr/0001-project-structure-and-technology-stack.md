# ADR 0001: Project structure and technology stack

## Status

Accepted

## Date

2026-09-28

## Context

ProbeInterview 需要同时交付微信小程序、HTTP API、后台 Worker 和单机部署配置。项目仍处于绿地 MVP 阶段，尚不存在需要兼容的代码或团队级独立发布需求。后续知识导入、卡片生成和模拟面试会共享领域规则、身份上下文、数据库模型和外部服务端口。

如果在缺乏规模需求时拆成多个仓库或服务，会提前引入版本协调、跨仓库契约和多套 CI。另一方面，只按 `api`、`service`、`repository` 建立全局横向目录，会使知识、面试和复盘代码在规模增长后互相渗透。

## Decision

项目使用 Monorepo，基础目录为：

```text
apps/
  backend/
  miniprogram/
infra/
  compose/
scripts/
```

后端采用模块化单体。代码优先按业务模块组织，每个模块内部再按需要划分 `domain`、`application`、`api` 和 `infrastructure`。共享运行时能力放入明确的 platform/foundation 边界，不建立可被任意业务代码堆放的通用 `utils` 层。

业务模块不得直接访问其他模块的数据库 repository 或 infrastructure adapter。跨模块协作通过应用服务契约、端口或明确的领域事件完成。FastAPI 与 Celery 使用同一后端包和应用逻辑，但拥有独立进程入口。

基础技术栈确定为：

- 微信小程序使用 TypeScript 与 TDesign；
- 后端使用 Python 3.12、uv、FastAPI 和 Pydantic 2；
- 持久化使用 PostgreSQL + pgvector、SQLAlchemy 2 和 Alembic；
- 后端静态验证使用 Ruff 和 mypy，测试使用 pytest；
- 所有直接依赖必须通过锁文件固定并可在全新环境复现安装。

## Alternatives

### Separate repositories

小程序、API 和 Worker 分仓可以提供更独立的发布权限，但当前没有独立团队或发布节奏，反而会增加契约同步和端到端验证成本。

### Microservices from the beginning

微服务可以独立扩缩容，但 MVP 的领域边界仍在演化。现在拆分会把本地事务、部署和可观察性问题提前引入。

### Global horizontal backend layers

把全部 controller、service 和 repository 分别放在全局目录中，初期看起来简单，但会弱化业务边界，使未来拆分和权限审计更加困难。

### JavaScript mini program

JavaScript 减少少量构建配置，但无法提供跨 API 模型、页面状态和组件属性的一致静态约束。

## Consequences

- `setup-foundation` 必须先建立目录、锁文件和独立进程入口，但不得创建知识或面试领域模块。
- 后续 change 新增功能时，应在对应业务模块内纵向交付，而不是继续扩大全局基础层。
- 模块化单体保留未来拆分服务的边界，但当前不承担分布式系统成本。
- Python 或 TypeScript 的主版本升级属于显式维护工作；不能由单个功能 change 顺手升级。
- 引入新的语言、核心框架、数据库或主要包管理工具前，需要新的或替代 ADR。


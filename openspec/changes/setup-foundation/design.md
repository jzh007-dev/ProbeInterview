# Design

## Context

本 change 的动机见 `proposal.md`，可观察行为见 `specs/platform-foundation/spec.md`。仓库目前只有设计与 OpenSpec 文档，没有业务代码、构建命令或既有运行时需要兼容。

项目级技术结论见 `docs/architecture.md` 和 `docs/adr/README.md`。本 change 采用已确认的微信小程序、Caddy、FastAPI、PostgreSQL + pgvector、SQLAlchemy 2、Alembic、Python 3.12、uv、Pydantic 2、Redis + Celery、TypeScript + TDesign、pytest、Ruff、mypy、Jest 和 `miniprogram-simulate` 建立工程骨架；真实微信登录、OSS 和百炼调用留给后续功能 change。

## Goals / Non-Goals

**Goals:**

- 用一个最小 probe 串通客户端、API、数据库、任务投递、Worker 和 pgvector。
- 建立后续 change 必须复用的 API、actor scope、后台任务、配置、日志和测试契约。
- 让全新环境可以通过文档化命令启动本地运行时并自动验证完整链路。
- 使外部服务通过端口与 fake adapter 隔离，测试不依赖真实云凭证。

**Non-Goals:**

- 不实现正式微信身份交换、账户管理或产品权限页面。
- 不建立知识来源、主题、知识点、卡片、面试或复盘领域模型。
- 不实现文件上传、XMind/Markdown 解析、业务 chunk、真实 Embedding 或向量检索。
- 不实现真实 OSS、百炼 LLM/Embedding、OCR 或 ASR 调用。
- 不追求高可用、水平扩展、完整监控平台、告警或灾难恢复。

## Decisions

### 1. 使用单仓库承载三个入口与共享基础设施

仓库按运行职责组织：

```text
apps/
  backend/        Python 包、FastAPI 与 Celery 入口
  miniprogram/    TypeScript 微信小程序
infra/
  compose/        本地与单机部署编排
scripts/          根级启动、迁移与验证入口
```

`apps/backend` 是按业务模块组织的模块化单体。每个业务模块内部按需要包含 `api`、`application`、`domain` 和 `infrastructure`，共享运行能力位于明确的 platform/foundation 边界。FastAPI 与 Celery 复用领域与应用代码，但拥有独立进程入口。供应商 SDK 只能位于 infrastructure adapter，领域和应用层不得直接导入；业务模块也不得直接访问其他模块的 repository 或 ORM model。

选择单仓库是为了让 walking skeleton、契约和版本同步提交，并降低绿地 MVP 的维护成本。替代方案多仓库会在尚无团队扩展需求时增加版本协调和 CI 复杂度。

该结构遵循 `docs/adr/0001-project-structure-and-technology-stack.md`。

### 2. 使用已确认的基础技术栈并锁定可复现依赖

- Python 3.12 与 uv 管理 backend 虚拟环境和锁文件。
- FastAPI + Pydantic 2 定义 HTTP 与配置 schema。
- SQLAlchemy 2 + Alembic 管理 PostgreSQL + pgvector。
- Redis 作为 Celery broker；Celery Worker 只接收任务 ID。
- TypeScript + TDesign 建立最小小程序页面。
- pytest、Ruff 和 mypy 构成 backend 验证入口；Jest + `miniprogram-simulate` 验证小程序组件。

业务状态和执行结果只存 PostgreSQL，Redis 不保存最终真相。依赖必须锁定，自动验证使用锁文件安装。替代方案在请求内执行任务无法验证后续导入所需的异步链路；以 Redis 保存业务结果会使状态恢复和审计依赖易失数据。

### 3. Probe 是开发与验证能力，不是产品功能

验证环境提供：

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/foundation/probes`
- `GET /api/v1/foundation/probes/{probe_id}`

foundation probe 只在 development、test 或显式启用的验证环境开放；生产默认关闭创建入口。小程序只在开发构建中显示诊断页，发布产品包不展示该入口。

创建响应使用 HTTP 202，`Location` 指向状态资源，成功响应直接返回类型化任务资源：

```json
{
  "probe_id": "stable-id",
  "status": "QUEUED"
}
```

响应头返回 `Location: /api/v1/foundation/probes/stable-id` 和 `X-Request-ID`。查询返回 `QUEUED`、`RUNNING`、`SUCCEEDED` 或 `FAILED`、尝试次数、时间戳及不含内部异常的结果摘要。Probe 成功只证明基础链路可用，不承诺任何知识业务行为。

选择独立验证入口可使端到端测试不伪造知识实体。替代方案用首个业务 API 验证基础设施会让 foundation 与知识需求互相阻塞。

### 4. API 使用类型化成功资源、Problem Details 和请求上下文

所有版本化 API 位于 `/api/v1`。成功响应直接返回具体资源 schema，不增加通用 envelope。错误响应使用 RFC 9457 Problem Details，媒体类型为 `application/problem+json`：

```json
{
  "type": "urn:probeinterview:problem:validation-error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "/api/v1/foundation/probes",
  "code": "VALIDATION_ERROR",
  "errors": {}
}
```

`code` 和 `errors` 是稳定的业务扩展。中间件接受合法的客户端 request ID，否则生成新值；响应头 `X-Request-ID`、结构化日志和任务记录使用同一值。错误体不得包含堆栈、SQL、密钥、连接串或供应商原始异常。

写命令使用 `Idempotency-Key`。Foundation probe 将 owner、命令类型、幂等键和规范化输入 hash 一起持久化：相同输入返回原任务，不同输入返回 409。

选择标准 Problem Details 和具体成功 schema，是为了避免后续 changes 各自发明错误格式，同时保持 OpenAPI 模型直接。GraphQL、通用 `data/meta` envelope 或事件接口不会为当前简单移动端交互带来足够收益。

该协议遵循 `docs/adr/0004-api-and-identity-boundary.md`。

### 5. 正式认证延期，但 actor context 从第一天存在

应用层只依赖 `ActorContext(actor_id, capabilities)`，不读取微信或 HTTP header 细节。Development/test 使用仅在非生产环境启用的 local actor provider；后续微信登录 change 用真实 provider 替换，领域接口保持不变。

所有 owner 数据 repository 方法必须显式接收 `ActorScope`，SQL 查询在读取行或向量前应用 owner 条件。其他 actor 查询 probe 时返回统一不可见响应，不区分不存在和无权限。

选择先固定内部 actor contract、后接真实登录，可以测试隔离规则而不把微信外部依赖放进 foundation。使用全局固定用户会为后续多用户支持留下不可消除的数据捷径，因此禁止。

正式微信登录和白名单到公共知识发布 capability 的映射由后续 change 实现，但不得改变 `ActorContext`。该边界遵循 `docs/adr/0004-api-and-identity-boundary.md`。

### 6. PostgreSQL 是任务状态和测试向量的唯一真相源

Foundation 只创建两个业务无关表：

- `foundation_probe_job`：ID、owner、幂等键、input hash、status、attempts、request ID、safe result/error、时间戳和乐观锁版本。
- `foundation_probe_vector`：ID、probe ID、owner、固定维度测试向量、版本和有效状态。

数据库启用 pgvector 扩展。测试向量表仅验证扩展、SQLAlchemy 映射、事务和 owner 前置过滤，不会被后续知识检索复用。后续 change 为真实 embedding 建立独立表和索引策略；来源内容和版本是事实依据，向量是可重建的派生数据。

Alembic 必须支持从空库升级到 head，并在测试数据库验证升级与允许的降级。应用启动不自动修改 schema；迁移由显式命令执行。

使用独立 probe 表可避免为 smoke test 提前决定真实 embedding 维度、距离函数和索引。直接创建知识向量表会越过 `associate-knowledge-concepts` 的设计边界。

该数据边界遵循 `docs/adr/0002-data-and-rag-foundation-boundary.md`。

### 7. Worker 任务以数据库 ID 为输入并实现幂等恢复

API 提交 probe 的顺序为：

1. 在事务中创建或复用 `foundation_probe_job`。
2. 提交事务后投递仅包含 `probe_id` 的 Celery 消息。
3. 投递失败时保留 QUEUED 记录并保存安全的 dispatch 错误；恢复命令可重新投递超时 QUEUED 任务。

Worker 读取并锁定 job，检查终态后再进入 RUNNING。执行步骤为：

1. 调用 fake object storage adapter 完成小文本 put/get/delete。
2. 调用 fake embedding adapter取得固定向量。
3. 写入 owner-scoped probe vector。
4. 在相同 owner scope 内执行最近向量查询并验证返回自身。
5. 原子写入 SUCCEEDED 和安全摘要。

异常按照配置的有限次数重试；最终失败写入稳定错误码。重复消息看到 SUCCEEDED 时直接结束，不重复创建结果。fake LLM adapter通过独立契约测试验证，不放入 probe 主路径，以免人为扩展闭环。

该方案比把完整参数放进队列更安全，也便于版本、权限和重试控制。Foundation 不实现通用工作流引擎或复杂 outbox；QUEUED 恢复命令覆盖 MVP 的投递空窗。

该任务模型遵循 `docs/adr/0003-asynchronous-job-architecture.md`。

### 8. 外部服务使用端口、fake adapter 和启动配置校验

Foundation 定义 `ObjectStorage`、`EmbeddingProvider` 和 `StructuredLlmClient` 端口。Local/test profile 默认加载确定性 fake adapter；production profile 若启用某真实 adapter，则必须在启动时校验必需配置，但本 change 不实现真实调用。

fake adapter 只返回固定、可预测结果并记录调用元数据。它们不得模拟业务智能，也不得成为生产降级答案。这样后续 changes 可以先通过契约测试，再单独加入 OSS 和百炼 adapter。

该适配器边界遵循 `docs/adr/0006-external-adapters-and-verification-strategy.md`。

### 9. 自动验证按层次组织，但提供一个根级入口

根级验证入口依次运行：

1. backend 格式、lint、类型检查和单元测试；
2. 小程序格式、类型检查和 Jest + `miniprogram-simulate` 组件测试；
3. Alembic 空库升级与 schema 约束测试；
4. owner 隔离与 pgvector 集成测试；
5. Redis/Celery 重试、重复投递和恢复测试；
6. 启动隔离 Compose 环境并运行 foundation probe API 端到端测试。

端到端测试使用真实 Caddy、PostgreSQL、pgvector、Redis、API 和 Worker，但使用 local actor 与 fake 外部 adapter。验证失败必须返回非零退出码，并保证测试容器与数据可清理。仓库当前不绑定 CI 托管平台；未来平台只调用同一个 `scripts/verify`，不得复制验证逻辑。

该验证策略遵循 `docs/adr/0006-external-adapters-and-verification-strategy.md`。

### 10. Compose 使用 Caddy 保持单机 MVP 拓扑

Compose 至少包含 Caddy、API、Worker、PostgreSQL + pgvector 和 Redis。API/Worker 使用同一 backend 镜像但不同启动命令；数据库和 Redis 使用持久卷，测试 profile 使用隔离临时卷。服务依赖以健康检查和显式重试为准，不能只依赖容器启动顺序。

Caddy 是唯一公网入口，负责反向代理、自动 TLS 和 HTTP 到 HTTPS 跳转；API、Worker、数据库和 Redis 不直接暴露公网。本地测试可以使用明确的本地 HTTP/TLS 配置，production 在提供域名后启用自动证书。本地默认不需要真实云密钥。生产 OSS、百炼、备份、监控和告警只保留配置边界，不在本 change 内交付。

配置通过 Pydantic Settings 定义 development、test 和 production schema。日志使用结构化 JSON，并以 request ID、trace ID 和 job ID 关联；正常日志不记录请求正文、上传内容、完整 Prompt/模型响应、密钥、令牌或连接串。

该运行规范遵循 `docs/adr/0005-deployment-and-runtime-operations.md`。

## Risks / Trade-offs

- [Foundation 演变为基础设施大包] → 只允许两个 probe 表、四个 probe/health 接口和一条闭环；出现知识或面试领域名词即移出本 change。
- [Probe 入口被误暴露到生产] → 由 environment profile 和显式开关双重限制，生产默认关闭创建入口。
- [Local actor provider 成为认证捷径] → production profile 禁止加载，应用层只能依赖可替换 `ActorContext`。
- [Celery 至少一次投递产生重复结果] → 消息只带数据库 ID，Worker 锁定记录并检查终态，数据库唯一约束保护幂等。
- [API 提交后投递失败造成 QUEUED 卡住] → 保留数据库真相、暴露安全错误并提供超时 QUEUED 恢复命令。
- [pgvector smoke 表影响真实向量设计] → 使用独立固定维度 probe 表，真实 embedding schema 由后续 change 决定。
- [端到端测试过慢或不稳定] → 单元测试不依赖容器，集成环境固定版本并使用确定性 fake adapter；根级入口分别报告阶段。
- [Caddy 自动 TLS 在本地测试中依赖公网域名] → 测试 profile 使用明确的本地配置验证反向代理；production 域名和证书行为由部署配置启用。

## Migration Plan

1. 创建锁文件、目录结构和本地配置模板，不包含真实密钥。
2. 启动 PostgreSQL + pgvector 与 Redis，执行 Alembic 初始迁移。
3. 启动 API、Worker 和 Caddy，验证存活、就绪与反向代理。
4. 启动小程序开发诊断页，运行完整 foundation probe。
5. 在全新环境运行根级验证入口；未来 CI 平台必须调用同一入口。

这是 greenfield change，没有旧服务或数据迁移。回滚时停止 Compose 运行单元并回退本 change 的初始迁移；不删除用户业务数据，因为 foundation 不创建业务实体。

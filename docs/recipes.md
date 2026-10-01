# Recipes（标准做法）

给 agent 和人的端到端菜谱。照着做，不要重新发明结构。每个菜谱以现有代码为参照实现。

**维护规则**：每当发现 agent 在会话里重新探索同一个地方（某个测试怎么写、某个约定在哪），
就把它补进本文件。这个文件变厚 = 探索阶段变短；它停止生长 = 你在为同一件事反复付费。

## 0. 落点索引（先看这里，不要全仓 grep）

| 你要做的事 | 落点 | 照抄哪个 |
|---|---|---|
| 新增后端 API | `<module>/api/contracts.py`、`<module>/api/router.py`、`<module>/application/service.py`、`<module>/application/errors.py`、`entrypoints/api.py` | `knowledge/source` |
| 新增/改表 | `<module>/infrastructure/models.py`、`migrations/versions/` | `candidate/profile` |
| 改鉴权/身份 | `identity/access/application/authentication.py`、`identity/access/api/dependencies.py`、`entrypoints/api.py` 挂载点 | 现有 `identity/access` |
| 接外部服务（LLM/存储/消息） | `<module>/application` 定义端口 → `<module>/infrastructure/` 写适配器 → `entrypoints/` 装配 | `platform/foundation`、`identity/access/infrastructure/wechat_adapters.py` |
| 新增小程序页面 | `miniprogram/pages/<name>/index.{ts,wxml,wxss,json}`、`miniprogram/app.json` | `pages/login` |
| 新增小程序组件 | `miniprogram/components/<name>/index.{ts,wxml,wxss,json}` | `components/profile-overview` |
| 页面/组件调接口 | `miniprogram/services/<name>.ts`（请求）+ `miniprogram/utils/<name>.ts`（运行时校验） | `services/transport.ts` |
| 新增小程序测试 | `apps/miniprogram/tests/<name>-model.test.cjs` / `-client.test.cjs` / `-component.test.cjs` | `tests/profile-overview-*` |
| 新增后端单测 | `apps/backend/tests/unit/<module>/` | `tests/unit/identity/` |
| 新增后端集成测试 | `apps/backend/tests/integration/<module>/` | `tests/integration/profile/` |
| 改配置项 | `<module>` 配置类型 + `infra/compose/*.env*.example` 模板 | `PROBEINTERVIEW_*` |
| 改 Compose/拓扑 | `infra/compose/compose*.yaml`、`scripts/test-compose-topology` | 同文件既有断言 |

## 1. 新增一个业务 API（backend）

参照实现：`knowledge/source`（上传接口）。

1. **契约**：`<module>/api/contracts.py` 定义请求/响应 Pydantic 资源。成功返回类型化资源，错误走 Problem Details。
2. **错误**：`<module>/application/errors.py` 定义领域异常（携带 title/status/code/errors）。在 `entrypoints/api.py` 注册对应 exception handler。
3. **用例**：`<module>/application/service.py` 写应用服务。依赖通过构造函数注入端口（repository/storage/clock），禁止直接 import 别的模块的 ORM 或 vendor SDK。授权检查（capability/owner）放在任何数据库或存储访问之前。
4. **持久化**：需要新表时先做菜谱 2；否则在 `<module>/infrastructure/repository.py` 写 SQLAlchemy 查询，owner 过滤条件必须出现在 SQL 里。
5. **路由**：`<module>/api/router.py` 声明路由，挂到 `entrypoints/api.py`。业务路由一律挂在受保护边界下，认证依赖不写在 handler 里。
6. **单测**：`tests/unit/<module>/` 测不变量（授权先于变更、补偿顺序、校验边界），用确定性 fake 端口。
7. **集成测试**：`tests/integration/<module>/` 测真实 PG 行为（幂等重放、约束、隔离、迁移），环境变量约定见 `scripts/verify --full`。
8. `scripts/verify`，红了不提交。

## 2. 新增一张表（backend）

参照实现：`candidate/profile/infrastructure/models.py` + `migrations/versions/20260929_0001_profile_overview.py`。

1. 在所属模块的 `infrastructure/models.py` 定义 ORM 模型（UUID 主键、显式 created_at/updated_at、owner 外键带 unique 约束按需）。
2. `cd apps/backend && uv run alembic revision --autogenerate -m "<描述>"`，检查生成的迁移：可空性、默认值、索引、downgrade 是否安全。
3. 迁移测试进 `tests/integration/profile/test_migrations.py` 的既有模式：空库升级、已有库升级、约束存在性、需要的列不存在性、downgrade。
4. 本地库跑 `uv run python -m probeinterview.entrypoints.database_initializer`（Alembic upgrade head，Compose 里由 initializer 容器自动执行）。
5. `scripts/verify --full`。

> **表里要带默认行时注意**：`knowledge_upload_policies` 曾只在回填迁移时插入，导致回填之后创建的
> 用户没有 policy 行，列表接口 500。凡"每个用户都该有一行"的表，要么在首次访问时惰性创建，
> 要么在创建用户的事务里写入——不要只靠一次性回填。

## 3. 新增小程序页面 / 组件

参照实现：`miniprogram/components/profile-overview/` + `services/profile-overview.ts`。

1. **页面**：`pages/<name>/` 四件套（ts/wxml/wxss/json），在 `app.json` 注册（tab 页需同时配 icon）。
2. **数据访问**：`services/<name>.ts` 封装请求，禁止页面直接 `wx.request`；响应体先过 `utils/<name>.ts` 的运行时校验（不信任服务端返回结构）。
3. **状态**：每个页面/组件必须显式实现 loading、success、empty、error 四态；错误信息不得透出原始异常。
4. **WXSS 约束**：自定义组件样式禁用 ID/属性/标签选择器（微信编译器限制），用 class；全局样式放 `styles/page-shell.wxss`。
5. **测试**：`tests/<name>-model.test.cjs`（纯逻辑）、`tests/<name>-client.test.cjs`（service，mock `wx.request`）、`tests/<name>-component.test.cjs`（组件，`miniprogram-simulate`）。参照 `tests/setup.cjs` 的 wx mock。
6. `cd apps/miniprogram && npm test && npm run typecheck`，然后 `scripts/verify`。

## 4. 小程序认证/传输约定（改造既有页面前必读）

阶段 ③ 起，小程序分三层，**新页面一律走这三层，不要再写匿名 `wx.request` 封装**：

| 层 | 文件 | 职责 |
|---|---|---|
| 凭证 | `miniprogram/services/auth-store.ts` | token + schema v1 |
| 展示缓存 | `miniprogram/services/current-user-store.ts` | schema v2，可空签名头像 / 目标画像摘要，被首页/我的/上传三处引用 |
| 传输 | `miniprogram/services/transport.ts` | 统一 JSON/multipart，集中附 Bearer；调用方不能覆盖 `Authorization`；401 单飞双清并重进登录页 |
| 登录 | `miniprogram/services/login-coordinator.ts` | **唯一**允许调 `wx.login` 的位置；先校验响应再原子落两个缓存 |

不变量：

- 启动**永不**调 `wx.login`，只做本地缓存校验。
- 401 只处理一次（单飞），失败一次后不静默重试。
- 改 `current-user-store` 的 schema 必须同步三处引用方与 `tests/current-user-store.test.cjs`。
- 本机开发用 `fake` 存储适配器时，展示 URL 走 `platform/foundation/api/local_display.py` 的本地路由；
  假适配器不产生真实签名 URL。

## 5. 这份仓库的常驻事实（会话开场不必重新发现）

- 快筛命令：`scripts/verify`（format / lint / mypy / 后端单测 / 小程序 jest + typecheck）。加 `--full` 才带 PostgreSQL 集成测试。
- 另有独立脚本：`scripts/test-compose-topology`、`scripts/test-beta-smoke`、`scripts/check-skeleton`、`scripts/test-*-postgres`。
- `scripts/test-*-postgres` 会起 Docker Postgres；一次约 3 分钟。纯文档改动不要跑它。
- 小程序工具链配置：`apps/miniprogram/jest.config.cjs`、`tsconfig.json`、`package.json`（`npm test` / `npm run typecheck`）。
- 后端模块布局：`apps/backend/src/probeinterview/<module>/{api,application,domain,infrastructure}/`；测试在 `apps/backend/tests/{unit,integration}/<module>/`。
- 小程序的 wx API mock 统一在 `apps/miniprogram/tests/setup.cjs`，不要各自造。
- 本机默认 `PROBEINTERVIEW_AUTHENTICATION_MODE=wechat` + `PROBEINTERVIEW_WECHAT_ADAPTER=fake`。fake 适配器把 `code` 直接当作 `<openid>`，所以 `{"code":"oProbeInterviewDemoOpenId01"}` 就是 `entrypoints/profile_seed.py` 种下的 demo 身份。

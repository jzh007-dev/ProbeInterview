# Recipes（标准做法）

给 agent 和人的端到端菜谱。照着做，不要重新发明结构。每个菜谱以现有代码为参照实现。

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

## 3. 新增小程序页面 / 组件

参照实现：`miniprogram/components/profile-overview/` + `services/profile-overview.ts`。

1. **页面**：`pages/<name>/` 四件套（ts/wxml/wxss/json），在 `app.json` 注册（tab 页需同时配 icon）。
2. **数据访问**：`services/<name>.ts` 封装请求，禁止页面直接 `wx.request`；响应体先过 `utils/<name>.ts` 的运行时校验（不信任服务端返回结构）。
3. **状态**：每个页面/组件必须显式实现 loading、success、empty、error 四态；错误信息不得透出原始异常。
4. **WXSS 约束**：自定义组件样式禁用 ID/属性/标签选择器（微信编译器限制），用 class；全局样式放 `styles/page-shell.wxss`。
5. **测试**：`tests/<name>-model.test.cjs`（纯逻辑）、`tests/<name>-client.test.cjs`（service，mock `wx.request`）、`tests/<name>-component.test.cjs`（组件，`miniprogram-simulate`）。参照 `tests/setup.cjs` 的 wx mock。
6. `cd apps/miniprogram && npm test && npm run typecheck`，然后 `scripts/verify`。

# Proposal

## Why

ProbeInterview 目前只有运行基础骨架，无法在尚未接入微信登录的本地环境中展示由真实持久化数据驱动的“我的”页面。需要先交付一个受控的只读闭环，验证用户身份、目标画像、当前简历元数据、API 和小程序展示之间的边界，同时不提前引入登录、上传或面试历史业务。

## What Changes

- 建立首个 PostgreSQL 业务迁移和开发数据初始化流程，持久化用户、微信身份预留字段、多份目标画像，并定义每位用户至多一份当前简历的存储无关元数据格式。
- 开发种子只创建用户、微信身份和目标画像，不伪造尚未上传的简历记录；本地首次展示使用真实的无简历状态。
- 实现仅允许在 development/test 启用的 local actor provider；production 继续拒绝该验证捷径。
- 提供 owner-scoped、类型化的 `GET /api/v1/me/overview`，返回当前用户的展示信息、默认目标画像、可空的当前简历元数据和空的历史成绩集合。
- 提供至少两名 actor 的自动化隔离覆盖，证明接口不会读取其他用户的画像或简历。
- 按 `docs/design/visuals/home-overview.html` 实现本地可运行的“我的”页面，覆盖加载、成功、无简历、空历史和错误状态。
- 配置首页、复盘、模拟、上传、我的五个 tab；其他四页只提供空页面壳，“我的”为默认可验收页面。
- 为设置、简历和历史栏目保留命名动作契约，但本次不执行跳转、预览、更换、上传或其他副作用。
- 明确排除微信登录/注册/会话、目标画像 CRUD 或切换、文件存储、简历上传/替换/预览、历史成绩查询和其他业务页面；简历上传入口归后续模拟面试 change。

## Capabilities

### New Capabilities

- `my-profile-overview`: 当前 actor 读取持久化个人概览，并在微信小程序“我的”页面及五 tab 页面壳中展示的端到端行为。

### Modified Capabilities

无。

## Impact

- Backend：新增 identity/profile 业务边界、`ActorContext` 的 local provider、SQLAlchemy 模型与 repository、首个 Alembic migration、不含简历的开发种子数据、`/api/v1/me/overview` 契约及测试。
- Database：新增 `users`、`wechat_identities`、`candidate_profiles`、`user_resume`；`user_resume` 只定义未来上传成功后写入的文件元数据与存储对象引用，不保存 PDF、永久 URL 或供应商细节。
- Mini program：新增五个 tab 页面、个人概览数据访问与状态展示；继续使用原生微信小程序 TypeScript 和 TDesign。
- Runtime/configuration：复用现有 `local_actor_enabled` 环境边界；development/test 可选择本地 actor，production 不允许启用。
- Dependencies：使用现有 FastAPI、Pydantic 2、SQLAlchemy 2、Alembic 和 TDesign，不新增语言、框架、云服务或主要依赖。

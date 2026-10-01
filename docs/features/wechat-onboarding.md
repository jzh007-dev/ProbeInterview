# 微信登录与 Onboarding

> 本文件取代 `openspec/changes/establish-wechat-authenticated-onboarding/`（保留为历史归档）。
> 本 feature 较大，按 workflow.md L2 规则分四个阶段交付，每阶段独立可验证、独立提交：

| 阶段 | 内容 | 状态 |
|---|---|---|
| ① 后端认证基础 | 配置类型化、对象存储端口、迁移 0003、交换+会话、注册+头像 | ✅ 完成 |
| ② 全局鉴权与概览 | 受保护路由、Bearer 会话解析、可空概览、PUT 目标画像 | ✅ 完成 |
| ③ 小程序认证边界 | auth store v1/v2、transport、登录协调器、登录页 | ✅ 完成 |
| ④ 页面改造与收尾 | 首页/我的/上传改造、Compose/smoke、完整验收 | ✅ 完成（真机验收待测） |

## 为什么

生产环境没有可用的微信身份与会话，业务 API 靠进程配置的 local actor 隐式鉴权。
交付端到端微信认证后，真实用户可注册、登录、填写目标岗位，现有概览与知识来源
能力统一到 `ActorContext` 边界下。相关：ADR 0004（身份边界）、`docs/architecture.md` §5。

## 范围

- **做**：`code2Session` 登录、首次注册（昵称 + 可选头像）、`(app_id, openid)` 唯一绑定、
  30 天 opaque Bearer session（只存 SHA-256 摘要，多设备独立）、全局业务 API 鉴权、
  默认目标画像创建/修改、头像存私有 OSS（DB 只存 object key）、小程序统一
  auth/transport/缓存边界、登录页与首页/我的/上传页改造。
- **不做**：UnionID 合并、手机号绑定、logout、注销、设备管理、refresh token/JWT、
  注册后改昵称头像、简历上传、面试历史、自动重试业务请求、新云服务或认证 SDK。

## 接口

| Method | Path | 鉴权 | 请求 | 响应 | 错误码 |
|---|---|---|---|---|---|
| POST | `/api/v1/auth/wechat/exchanges` | 公开 | `{code}` | 判别式：已绑定→session+currentUser；未绑定→一次性注册凭证（10 分钟有效，不建临时用户） | `wechat_code_exchange_failed`、`wechat_service_unavailable` |
| POST | `/api/v1/auth/wechat/registrations` | 公开 | 昵称 + 注册凭证（JSON，默认头像） | session + currentUser（`default_target_profile: null`） | 凭证过期/未知、昵称非法 422 |
| POST | `/api/v1/auth/wechat/avatar-registrations` | 公开 | 昵称 + 凭证 + multipart 头像（JPEG/PNG/WebP magic bytes，有界） | 同上，头像为私有对象 + 签名 URL | 头像非法 422、存储失败 503 |
| GET | `/api/v1/me/overview` | Bearer | — | 可空签名头像 + 可空 `default_target_profile`（**移除** `profile_overview_incomplete` 409） | 401 |
| PUT | `/api/v1/me/default-target-profile` | Bearer | `target_role`(1–200) + `relevant_experience_months`(0–600) | 创建或更新；昵称/头像不动；actor 级并发串行化 | 401、字段级 422 |

全局：除 2 个 health 路由和 3 个 auth bootstrap 路由外，`/api/v1/**` 一律 401
`authentication_required`；鉴权在挂载点结构化实现，不靠每个 handler 记得解析 header。
配置：`PROBEINTERVIEW_AUTHENTICATION_MODE=wechat|local_test`、
`PROBEINTERVIEW_WECHAT_ADAPTER=real|fake`；production 拒绝 fake/local 组合；
AppSecret 仅服务端；`session_key` 不下发不持久化。
数据库：`users.avatar_object_key` 转 nullable、新增 `wechat_registration_attempts`、`auth_sessions`。

## 收尾状态（2026-10-01）

阶段 ④ 已完成。seed 的微信身份绑定到进程配置的 `wechat_app_id`，compose 拓扑
检查与 beta smoke 都通过 fake 适配器的确定性登录码（demo 身份 openid）换会话后
携带 Bearer 调用受保护路由；compose 检查同时断言匿名概览请求 401。
`docs/development.md` 的示例全部携带 token。真机验收清单仍待开发者工具/真机执行。

## 小程序页面与模块

**新增 `pages/login/index`（非 tab 页，启动首屏）**
- 状态机：idle → exchanging →（已绑定）成功切换首页 /（未绑定）registration_required
  表单态（昵称输入 + chooseAvatar 选头像或默认头像）→ registering → 成功 / 可恢复错误
- 启动只做本地缓存校验：有效双缓存 → `wx.switchTab` 进首页；缺失/过期/损坏 → 留在登录页；
  **启动永不调用 `wx.login`**，只有点击"微信登录"才调用
- 注册表单：微信昵称输入 capability + `button open-type="chooseAvatar"` 临时路径；
  默认头像 = 无文件的显式选择；提交中禁用；成功后表单不再可编辑
- 错误态只渲染安全文案，不透出供应商/存储细节；视觉遵循 `docs/design/visuals/ui-direction.html`

**新增基础设施（登录页与各 tab 共用）**
- auth store（token，schema v1）+ current-user display cache（schema v2）
- 登录协调器（唯一允许调 `wx.login` 的位置；校验响应后原子落两个缓存）
- 统一 JSON / multipart transport（集中附 Bearer；401 单飞失效双清并重进登录页）

**改造既有页面**
- 首页：删除 overview 回退；空目标画像提示 + switchTab 到"我的"
- 我的：只读昵称头像 + 目标画像创建/编辑；简历/历史卡片仍来自受保护的概览接口
- 上传：迁移到共享 transport，失效清 owner 记录

## 验收

**配置与存储基础（已完成待提交）**
- [x] 合法/非法 auth mode × adapter 组合、production 禁用组合、缺 AppID/Secret 均被类型化配置拒绝
- [x] 对象存储端口含幂等 delete 与 10 分钟签名 GET；knowledge-source 迁移到共享端口后行为不变

**交换与会话**
- [x] 已知/未知身份、可空 UnionID、无效/已用 code、超时、服务不可用：fake 与 real adapter 行为一致且错误安全映射
- [x] `session_key`/AppSecret/原始供应商错误不出现在端口边界、响应或日志
- [x] 256-bit token 只在签发时返回明文；DB 只存摘要；到期精确；两设备独立 session
- [x] 已绑定 `(app_id, openid)` 交换 → 新 session + 最新 capability/display；未绑定 → 仅注册凭证，无临时用户/会话
- [x] bootstrap 路由免 token；响应与日志无 code/token/secret/session_key/openid

**注册与头像**
- [x] 昵称 trim/长度/控制字符校验；一次性凭证校验；用户+绑定+session 原子创建
- [x] magic-byte 校验（空/超限/不支持/不符）；`avatars/<user-id>/<avatar-id>.<ext>` 私有存储；无临时路径、无永久公开 URL（响应携带签名 URL，阶段②已落地）
- [x] 上传失败回滚账户状态；提交失败删除未引用对象——两种注入都无残留
- [x] 并发同 token/异 token 注册：恰一个用户与绑定、至多一个头像对象、只有胜者拿到 session、败者凭证不可收敛即拒绝

**全局鉴权**
- [x] OpenAPI 路由清单证明：仅 health + bootstrap 公开；新挂业务路由默认受保护
- [x] valid/缺失/非 Bearer/空/畸形/未知/过期/吊销 token → 稳定 `authentication_required`；鉴权失败零仓储/存储调用；capability 变更下次请求生效
- [x] overview 与 knowledge-source 移入受保护挂载；两用户 overview/source/quota 完全隔离；无 local actor 回退
- [x] 鉴权与供应商错误路径的安全码 + 捕获日志回归（无明文 token/凭证/签名 URL/请求体/原始错误）

**概览与目标画像**
- [x] 可空签名头像 + 可空默认目标画像；新用户 200；无 object key 泄漏；签名 URL 带过期元数据
- [x] PUT 目标画像：创建/修改/重复归一化；字段级 422；未认证 401；昵称头像不被触碰
- [x] actor 并发首写串行化 + 部分唯一约束兜底；客户端伪造他人 profile ID 不可读写

**小程序**
- [x] auth store(v1) + display cache(v2，可空过期头像/画像摘要) 读写往返、版本失效、损坏清理、一键双清
- [x] 共享 JSON/multipart transport：只给受保护调用附 Bearer；调用方不能覆盖 Authorization；幂等键保留
- [x] 401 单飞失效：双清、原调用失败一次、重进登录页、无静默登录/重试
- [x] 登录协调器：先校验两个响应资源再落缓存；半写回滚；只有显式登录动作才调 `wx.login`
- [x] 登录页全状态机；启动只做缓存校验；重复提交阻断
- [x] 首页：缓存命中零 overview 请求；缓存缺失/损坏进登录；空画像提示 + `wx.switchTab` 到"我的"；失效后清空上一用户内容
- [x] "我的"：只读昵称头像 + 可编辑目标画像；保存成功原子更新缓存，失败保留输入与旧缓存；首页返回时观察到新值
- [x] 上传 tab 迁移到共享 transport；失效后清 owner 记录；配额/上传行为不变

**收尾**
- [x] 文档/环境模板/seed/Compose/beta smoke 更新且文档命令可照跑；无示例泄漏 secret
- [x] `scripts/verify --full` + `scripts/test-compose-topology` + 小程序全套全绿（完成定义见 `docs/workflow.md`）

## 真机验收

- [ ] 真机微信（最新稳定版）：首次登录 → 授权昵称/头像 → 注册成功进入首页；杀进程重进 30 天内免登录
- [ ] 真机：chooseAvatar 返回临时路径 → 注册上传成功 → 我的页显示签名头像且过期后回退默认头像
- [ ] 真机：未填目标画像时首页出现提示 → switchTab 到"我的"→ 填写保存 → 返回首页提示消失
- [ ] 弱网/断网：登录与上传的错误态可恢复，不暴露原始错误
- [ ] （落地后）手动在开发者工具验证：token 过期触发 → 双缓存清除 → 回登录页 → 重新登录成功

## 决策

- auth mode 与 adapter 是两个独立类型化配置轴；fake adapter 含确定性身份表，development/test 默认 `wechat+fake`。
- token 生成 256-bit URL-safe，存储仅 SHA-256 摘要；注册尝试 10 分钟一次性，session 30 天。
- 注册原子性：PostgreSQL 事务级锁串行化 + 唯一约束兜底；外部写（OSS）失败走补偿删除。
- 对象存储端口从 knowledge/source 上提到 platform/foundation，签名单独授权。
- 小程序分三层：auth store（token，v1）/ display cache（展示，v2）/ transport（请求与上传）；
  登录协调器是唯一允许调 `wx.login` 的位置。
- 目标画像编辑用选择器：岗位为固定目录（先只含"AI 全栈开发"，岗位归一化 feature 落地前不开放自由文本），
  经验按 1–10 年选择、以月数提交。
- fake 对象存储适配器在配置了 `PROBEINTERVIEW_FAKE_OBJECT_STORAGE_DISPLAY_BASE_URL` 时，
  签名 URL 指向 API 的 `/local-objects/` 开发展示路由（每次请求校验签名过期；生产禁用 fake 适配器故不挂载），
  使开发者工具能渲染注册头像。
- 知识上传策略对迁移后注册的新用户在首次访问时惰性创建（与 0002 迁移回填相同的默认值）。

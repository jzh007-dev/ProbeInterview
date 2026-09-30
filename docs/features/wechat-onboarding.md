# 微信登录与 Onboarding

> 状态：进行中。配置/存储基础（原 tasks 1.1–1.2）已完成。
> 本文件取代 `openspec/changes/establish-wechat-authenticated-onboarding/`（保留为历史归档）。

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

## 当前已知中间态（2026-10-01）

后端已默认 `wechat + fake`，匿名请求开始返回 401 `actor_required`；但 Compose 拓扑检查
（`scripts/test-compose-topology` 尾部 4 个匿名 HTTP 断言）和 beta smoke 仍按旧匿名流程编写，
在本分支上会失败。这属于下方"小程序/收尾"组验收的一部分（等价于原 change 任务 8.1/8.2）：
补齐 fake 会话下发与 smoke 携带 token 后，两者转绿。CI 中 compose-topology job 在本
feature 合并前预期为红。

## 验收

**配置与存储基础（已完成待提交）**
- [x] 合法/非法 auth mode × adapter 组合、production 禁用组合、缺 AppID/Secret 均被类型化配置拒绝
- [x] 对象存储端口含幂等 delete 与 10 分钟签名 GET；knowledge-source 迁移到共享端口后行为不变

**交换与会话**
- [ ] 已知/未知身份、可空 UnionID、无效/已用 code、超时、服务不可用：fake 与 real adapter 行为一致且错误安全映射
- [ ] `session_key`/AppSecret/原始供应商错误不出现在端口边界、响应或日志
- [ ] 256-bit token 只在签发时返回明文；DB 只存摘要；到期精确；两设备独立 session
- [ ] 已绑定 `(app_id, openid)` 交换 → 新 session + 最新 capability/display；未绑定 → 仅注册凭证，无临时用户/会话
- [ ] bootstrap 路由免 token；响应与日志无 code/token/secret/session_key/openid

**注册与头像**
- [ ] 昵称 trim/长度/控制字符校验；一次性凭证校验；用户+绑定+session 原子创建
- [ ] magic-byte 校验（空/超限/不支持/不符）；`avatars/<user-id>/<avatar-id>.<ext>` 私有存储 + 签名 URL；无临时路径、无永久公开 URL
- [ ] 上传失败回滚账户状态；提交失败删除未引用对象——两种注入都无残留
- [ ] 并发同 token/异 token 注册：恰一个用户与绑定、至多一个头像对象、只有胜者拿到 session、败者凭证不可收敛即拒绝

**全局鉴权**
- [ ] OpenAPI 路由清单证明：仅 health + bootstrap 公开；新挂业务路由默认受保护
- [ ] valid/缺失/非 Bearer/空/畸形/未知/过期/吊销 token → 稳定 `authentication_required`；鉴权失败零仓储/存储调用；capability 变更下次请求生效
- [ ] overview 与 knowledge-source 移入受保护挂载；两用户 overview/source/quota 完全隔离；无 local actor 回退
- [ ] 鉴权与供应商错误路径的安全码 + 捕获日志回归（无明文 token/凭证/签名 URL/请求体/原始错误）

**概览与目标画像**
- [ ] 可空签名头像 + 可空默认目标画像；新用户 200；无 object key 泄漏；签名 URL 带过期元数据
- [ ] PUT 目标画像：创建/修改/重复归一化；字段级 422；未认证 401；昵称头像不被触碰
- [ ] actor 并发首写串行化 + 部分唯一约束兜底；客户端伪造他人 profile ID 不可读写

**小程序**
- [ ] auth store(v1) + display cache(v2，可空过期头像/画像摘要) 读写往返、版本失效、损坏清理、一键双清
- [ ] 共享 JSON/multipart transport：只给受保护调用附 Bearer；调用方不能覆盖 Authorization；幂等键保留
- [ ] 401 单飞失效：双清、原调用失败一次、重进登录页、无静默登录/重试
- [ ] 登录协调器：先校验两个响应资源再落缓存；半写回滚；只有显式登录动作才调 `wx.login`
- [ ] 登录页全状态机；启动只做缓存校验；重复提交阻断
- [ ] 首页：缓存命中零 overview 请求；缓存缺失/损坏进登录；空画像提示 + `wx.switchTab` 到"我的"；失效后清空上一用户内容
- [ ] "我的"：只读昵称头像 + 可编辑目标画像；保存成功原子更新缓存，失败保留输入与旧缓存；首页返回时观察到新值
- [ ] 上传 tab 迁移到共享 transport；失效后清 owner 记录；配额/上传行为不变

**收尾**
- [ ] 文档/环境模板/seed/Compose/beta smoke 更新且文档命令可照跑；无示例泄漏 secret
- [ ] `scripts/verify --full` + `scripts/test-compose-topology` + 小程序全套全绿（完成定义见 `docs/workflow.md`）

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

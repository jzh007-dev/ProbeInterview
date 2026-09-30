# Proposal

## Why

ProbeInterview 目前依赖 development/test local actor，生产环境没有可用的微信身份、会话或全局业务 API 鉴权，首页和各业务 service 也各自处理用户数据与请求。需要交付端到端微信认证和首次 onboarding，使真实用户能够安全注册、登录、填写目标岗位，并让现有个人概览与知识来源能力在统一身份边界下运行。

## What Changes

- 新增用户主动触发的微信 code2Session 登录、首次注册和基础资料采集；已绑定身份直接登录，未绑定身份以内部用户 ID、`app_id + openid` 唯一绑定、昵称和可选私有头像完成注册。
- 新增 PostgreSQL 持久化的 30 天随机 opaque Bearer session；仅保存 token 安全摘要，允许多设备独立 session，不实现 JWT、refresh token、logout、账号注销或设备管理。
- **BREAKING**：除 `/health/live`、`/health/ready` 和认证 bootstrap 接口外，所有 `/api/v1/**` 业务接口改由共享 protected-router/auth dependency 统一鉴权；缺少或无效 token 不再隐式回退 local actor。
- 新增 production 真实微信 adapter 与 development/test 确定性 fake adapter 的配置边界；AppSecret 只存在于服务端 secret 配置，`session_key` 不下发、不持久化，production 拒绝 local actor 与 fake WeChat adapter。
- 将自定义头像保存到现有私有 OSS 能力，数据库只保存 provider-neutral object key；没有自定义头像时 API 返回可空头像信息，由小程序渲染内置默认头像。
- 建立小程序共享 auth store、current-user display store、登录协调器、JSON API transport 和 multipart upload transport，集中附加 Bearer token，并在 token 失效时同时清除两类缓存、显示登录页且不静默登录或重试业务请求。
- **BREAKING**：首页删除 `/api/v1/me/overview` 回退，昵称与可空默认目标画像只从经过版本化和运行时校验的当前用户缓存读取；缓存缺失或损坏时进入登录流程。
- 新增默认目标画像创建/修改能力；新用户默认目标画像为 `null`，“我的”页面保持 nickname/avatar 只读，保存 `target_role` 和 `relevant_experience_months` 后同步当前用户缓存。
- **BREAKING**：`GET /api/v1/me/overview` 在没有默认目标画像时返回 `200` 和 `default_target_profile: null`，不再返回 `profile_overview_incomplete`。
- 首页在目标画像为空时展示“请在我的页面填写目标岗位”，并通过 `wx.switchTab` 进入“我的”；首页不为此调用 overview。
- 为微信交换失败、并发重复注册、头像补偿、token 全生命周期、全局路由保护、owner 隔离、缓存清理、默认头像、空目标画像及相关 UI 状态增加自动化验收覆盖。

## Capabilities

### New Capabilities

- `wechat-authentication`: 微信身份交换、首次注册、头像持久化、opaque session、全局业务 API 鉴权、服务端 capability 解析以及小程序统一认证/传输/缓存边界。
- `target-profile-management`: 当前 actor 创建或修改默认目标岗位与相关经验月份，并保持 owner 隔离及小程序缓存同步。

### Modified Capabilities

- `home-knowledge-overview`: 删除 overview 回退，要求首页只消费已认证流程写入的当前用户缓存，并增加空目标画像提示及切换到“我的”的行为。
- `my-profile-overview`: 允许 nullable 默认目标画像和 nullable 自定义头像，要求经过全局认证读取，并让“我的”页面展示只读身份资料与可编辑目标画像状态。

## Impact

- Backend：扩展 `identity/access` 的微信端口、真实/fake adapter、注册与 session 持久化、Bearer 解析和 protected-router；扩展 `candidate/profile` 的默认目标画像命令；调整 profile/knowledge-source router 挂载边界。
- Database：迁移 `users` 的头像字段为 nullable provider-neutral object key，新增 registration bootstrap/session 状态，并复用 `(app_id, openid)` 唯一约束、`user_capabilities` 和 `candidate_profiles`。
- External services/configuration：复用现有私有 OSS，提取可供多个模块使用的对象存储端口；新增微信 AppID/AppSecret 与 adapter/auth-mode 类型化配置，不引入新云服务、数据库、语言或框架。
- API：新增公开的微信 exchange/registration bootstrap 资源和受保护的默认目标画像写接口；现有 overview 与知识来源 GET/POST 改为必须携带 Bearer token。
- Mini program：新增登录页和 onboarding 状态、版本化 auth/current-user stores、统一 request/upload transports；修改首页、“我的”和上传页面的数据流、401 行为与自动化测试。
- Operations/tests：更新 development/test fake 微信身份路径、聚焦 local actor 测试方式、迁移/后端/小程序/Compose/beta smoke 文档与验证。

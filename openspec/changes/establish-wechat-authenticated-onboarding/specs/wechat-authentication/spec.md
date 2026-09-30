# Spec Delta

## Purpose

定义微信小程序用户主动登录、首次注册、私有头像、服务端 opaque session、全局业务 API 保护以及客户端统一认证状态与请求边界，使生产请求能够安全映射为现有 `ActorContext`。

## ADDED Requirements

### Requirement: 用户主动触发微信身份交换
微信小程序 SHALL 只在用户主动点击“微信登录”后调用 `wx.login`，并 SHALL 将临时 code 发送到公开的 `POST /api/v1/auth/wechat/exchanges`。后端 SHALL 通过 identity application port 调用所选微信 adapter，并 SHALL 把配置的 `app_id`、微信返回的 `openid` 和可空 `unionid` 映射为 provider-neutral 交换结果。已存在 `(app_id, openid)` 绑定时，系统 SHALL 直接返回新的认证 session 和类型化当前用户展示快照；未绑定时 SHALL 返回短期、一次性的注册凭据和 `registration_required` 结果，且 MUST NOT 为该结果创建用户或认证 session。

#### Scenario: 已注册微信用户成功登录
- **WHEN** 用户主动点击微信登录，code2Session 成功返回已绑定的 `app_id` 和 `openid`
- **THEN** 系统返回新的 Bearer session、30 天到期时间和该用户的展示快照，客户端进入已登录状态

#### Scenario: 未注册微信用户进入首次资料流程
- **WHEN** 用户主动点击微信登录，code2Session 成功返回尚未绑定的 `(app_id, openid)`
- **THEN** 系统返回 `registration_required` 和短期一次性注册凭据，不创建用户、微信绑定或认证 session

#### Scenario: 无效或已使用的微信 code
- **WHEN** 微信拒绝临时 code，因为 code 无效、过期或已经使用
- **THEN** 系统返回稳定、安全的 RFC 9457 Problem Details，客户端保持未登录，响应不包含供应商原始错误、openid 或 session_key

#### Scenario: 微信服务超时或不可用
- **WHEN** code2Session 调用超时或微信服务不可用
- **THEN** 系统返回可重试的服务不可用 Problem Details，不创建用户、绑定、注册凭据或 session

#### Scenario: 登录动作不会在后台静默发生
- **WHEN** 小程序启动、业务请求失败或已有 token 过期，但用户没有再次点击微信登录
- **THEN** 客户端不调用 `wx.login`，并保持或切换到显式登录页面

### Requirement: 首次注册原子创建用户和微信绑定
系统 SHALL 允许持有有效一次性注册凭据的未注册用户提交合法 nickname，并 SHALL 为其创建新的内部用户 ID、`(app_id, openid)` 唯一微信绑定和新的认证 session。nickname SHALL 去除首尾空白后保持非空、符合服务端长度与安全字符约束，并在注册后保持只读。本 change MUST NOT 使用 `unionid` 合并不同 `(app_id, openid)` 绑定，且 MUST NOT 提供 nickname 修改接口。

#### Scenario: 未注册用户使用默认头像完成注册
- **WHEN** 用户提交有效注册凭据和合法 nickname，并选择使用小程序内置默认头像
- **THEN** 系统原子创建一个用户、一个微信绑定和一个 session，用户没有自定义头像 object key，响应中的 `avatar_url` 为 `null`

#### Scenario: nickname 缺失或不合法
- **WHEN** 用户提交空白、过长或包含禁止字符的 nickname
- **THEN** 系统返回字段级 RFC 9457 Problem Details，不创建用户、绑定、session 或头像对象，注册凭据仍按其安全消费规则处理

#### Scenario: 同一微信身份并发注册
- **WHEN** 两个有效注册请求并发尝试为同一 `(app_id, openid)` 创建账户
- **THEN** 数据库中最终只有一个内部用户和一个微信绑定，成功请求均只关联该用户，不覆盖胜出注册资料，也不遗留重复头像对象

#### Scenario: 注册凭据无效、过期或已消费
- **WHEN** 注册请求使用未知、过期或已经消费且无法收敛到既有绑定的注册凭据
- **THEN** 系统拒绝注册并返回安全 Problem Details，不创建或修改用户、绑定、session 或头像对象

#### Scenario: UnionID 不触发账号合并
- **WHEN** 微信为两个不同 app_id/openid 组合返回相同 unionid
- **THEN** 本 change 不自动合并账户，身份唯一性和登录解析仍以 `(app_id, openid)` 为准

### Requirement: 自定义头像使用私有对象存储
首次注册 SHALL 支持 `chooseAvatar` 产生的可选头像文件。选择自定义头像时，系统 SHALL 校验受支持的图片类型、大小和非空内容，将其保存到配置的私有对象存储，并只在数据库保存 provider-neutral avatar object key。系统 MUST NOT 保存微信临时路径、永久公开 URL、供应商私有响应或访问凭据；读取展示资源时 MAY 返回短期签名 `avatar_url` 及其到期信息。未选择自定义头像时，系统 SHALL 不创建头像对象，由小程序渲染内置默认头像。

#### Scenario: 用户选择并保存自定义头像
- **WHEN** 未注册用户提交有效注册凭据、合法 nickname 和有效头像文件
- **THEN** 注册成功，私有对象存储存在一个用户头像对象，数据库只保存其 provider-neutral object key，响应可包含短期签名头像 URL

#### Scenario: 用户使用默认头像
- **WHEN** 未注册用户完成注册但没有选择自定义头像
- **THEN** 注册成功且不写入头像对象，API 以 `avatar_url: null` 表达没有自定义头像，小程序展示内置默认头像

#### Scenario: 头像输入无效
- **WHEN** 头像为空、超过限制、媒体类型不受支持或内容签名与允许类型不符
- **THEN** 系统返回字段级 Problem Details，不创建有效用户、绑定、session 或头像对象

#### Scenario: 头像上传失败
- **WHEN** 私有对象存储在首次注册期间拒绝或无法完成头像写入
- **THEN** 系统返回安全的服务错误，不产生半注册用户、微信绑定、有效 session 或被数据库引用的头像状态

#### Scenario: 头像写入后数据库提交失败
- **WHEN** 头像对象已经写入但用户、绑定或 session 的数据库事务无法提交
- **THEN** 系统不返回成功、不产生可登录账户，并对该未引用头像对象执行补偿清理

#### Scenario: 签名头像 URL 不成为持久化真相
- **WHEN** API 为有自定义头像的用户生成短期签名 URL
- **THEN** URL 仅作为临时展示值返回，数据库和客户端持久化缓存均不把永久公开 URL 当作头像真相

### Requirement: 认证 session 使用可撤销的 opaque Bearer token
系统 SHALL 为每次成功登录或注册生成独立、高熵、随机 opaque Bearer token，有效期为签发后 30 天。明文 token SHALL 只在创建响应中返回，PostgreSQL SHALL 只保存其安全摘要、所属用户、签发时间、到期时间和可空撤销状态；系统 MUST NOT 使用 JWT、refresh token、Redis 产品状态或 token 内权限声明。同一用户 MAY 在多个设备拥有相互独立的 session。

#### Scenario: 有效 token 访问业务接口
- **WHEN** 客户端以格式正确、已知、未撤销且未过期的 Bearer token 请求受保护业务 API
- **THEN** 系统解析其用户并继续处理请求

#### Scenario: 多设备 session 相互独立
- **WHEN** 同一用户在两个设备分别登录
- **THEN** 系统创建两个不同 token 和 session 记录，其中一个 session 的到期或撤销不改变另一个 session

#### Scenario: 缺少或格式错误的 token
- **WHEN** 受保护业务 API 请求缺少 Authorization、使用非 Bearer scheme、包含空 token 或无法解析的格式
- **THEN** 系统返回 `401` RFC 9457 Problem Details，且不执行业务数据库或对象存储操作

#### Scenario: 未知 token
- **WHEN** Bearer token 格式合法但其摘要不存在
- **THEN** 系统返回 `401`，不泄露 token 是否曾存在或对应哪个用户

#### Scenario: 已过期 token
- **WHEN** 当前时间达到或超过 session 的到期时间
- **THEN** 系统返回 `401`，不延长 session 且不签发替代 token

#### Scenario: 已撤销 token
- **WHEN** session 已被服务端标记撤销
- **THEN** 系统返回 `401`，不影响该用户其他未撤销 session

#### Scenario: capability 不来自 token
- **WHEN** 有效 session 对应用户的 capability 持久化状态发生变化
- **THEN** 后续请求生成的 `ActorContext.capabilities` 反映服务端当前持久化状态，而不是 token 或客户端缓存中的旧声明

### Requirement: 业务 API 通过统一保护边界认证
系统 SHALL 仅公开 `/health/live`、`/health/ready` 和完成微信 exchange/registration 所需的认证 bootstrap 接口。其余 `/api/v1/**` 业务路由 SHALL 统一挂载到共享 protected-router/auth dependency 边界，在进入业务 handler 前解析 Bearer session并生成现有 `ActorContext(actor_id, capabilities)`。业务模块 MUST NOT 自行解析 Authorization header，新业务路由 MUST NOT 因遗漏局部 dependency 而意外公开。

#### Scenario: health 接口公开可用
- **WHEN** 未认证客户端请求 `/health/live` 或 `/health/ready`
- **THEN** 系统按既有健康契约响应，不要求 Bearer token

#### Scenario: auth bootstrap 不要求已有 session
- **WHEN** 未认证客户端请求微信 exchange 或首次注册 bootstrap 接口
- **THEN** 系统处理该 bootstrap 请求，不要求 Authorization header

#### Scenario: overview 拒绝未认证请求
- **WHEN** 未认证客户端请求 `/api/v1/me/overview`
- **THEN** 共享认证边界返回 `401`，个人概览 handler 不执行

#### Scenario: 知识来源接口拒绝未认证请求
- **WHEN** 未认证客户端请求知识来源 GET 或 POST 接口
- **THEN** 共享认证边界返回 `401`，不查询配额、不读取来源、不写入对象

#### Scenario: 新业务路由默认受保护
- **WHEN** 一个新的业务 router 被挂载到 `/api/v1` 业务入口且没有声明自己的 Authorization 解析逻辑
- **THEN** 该路由仍经过共享认证边界，只有显式加入公开 bootstrap allowlist 的路由可以绕过认证

#### Scenario: 登录用户之间保持 owner 隔离
- **WHEN** 两个有效 session 分别访问个人概览、目标画像或知识来源
- **THEN** 每个请求在数据库访问前使用各自 ActorContext 的 owner scope，任何响应或计数都不包含另一用户的数据

### Requirement: 身份模式和微信 adapter 由类型化配置唯一选择
系统 SHALL 通过类型化配置明确选择认证模式和微信 adapter。production SHALL 使用微信 Bearer 认证与真实微信 adapter，并 SHALL 在启动时要求服务端 AppID/AppSecret 等 secret 配置；production MUST 拒绝 local actor、fake 微信 adapter 或同时启用多个身份 provider。development/test SHALL 能使用确定性 fake 微信 adapter。local actor SHALL 只在明确选择的聚焦测试模式中使用，不得作为普通业务请求缺少 token 时的隐式回退。

#### Scenario: production 使用真实微信认证
- **WHEN** production 以完整真实微信配置启动
- **THEN** 系统只注册微信 session 认证与真实微信 adapter，AppSecret 不暴露给客户端

#### Scenario: production 拒绝测试身份捷径
- **WHEN** production 配置选择 local actor、fake 微信 adapter或互相冲突的认证 provider
- **THEN** 系统在开始处理请求前拒绝启动

#### Scenario: development/test 使用确定性 fake adapter
- **WHEN** development/test 明确选择 fake 微信 adapter 并提交预定义 code
- **THEN** adapter 返回可预测身份或预定义失败，测试不需要真实微信网络或 AppSecret

#### Scenario: local actor 仅用于显式聚焦测试
- **WHEN** 聚焦测试明确选择 local actor 模式和 actor ID
- **THEN** 系统可生成该 actor 的 ActorContext；普通 development/test 微信模式中的无 token 请求仍返回 `401`

### Requirement: 小程序认证状态和传输集中管理
小程序 SHALL 建立相互分离且带 schema version 与运行时校验的 auth token store 和 current-user display store，并 SHALL 由登录协调器、统一 JSON API transport 与统一 multipart upload transport 使用。current-user 缓存 SHALL 只包含用户 ID、nickname、可空头像展示信息和可空默认目标画像摘要；它 MUST NOT 作为认证或 capability 依据。受保护的 `wx.request` 和 `wx.uploadFile` SHALL 由共享 transport 添加 `Authorization: Bearer <token>`，页面和具体业务 service MUST NOT 自行拼接 auth header。

#### Scenario: 登录成功写入分离缓存
- **WHEN** 微信登录或首次注册返回认证 session 和当前用户展示快照
- **THEN** 登录协调器分别写入 auth store 与 current-user store，并通过运行时校验后进入首页

#### Scenario: JSON 业务请求统一添加 token
- **WHEN** 已登录客户端通过共享 API transport 发起受保护的 overview GET 或目标画像写请求
- **THEN** transport 从 auth store 读取 token 并添加 Bearer header，调用页面不接触 token 字符串

#### Scenario: multipart 业务请求统一添加 token
- **WHEN** 已登录客户端通过共享 upload transport 上传知识来源
- **THEN** upload transport 添加同一 Bearer header并保留业务所需的其他 header，上传页面不自行拼接 Authorization

#### Scenario: 公开 bootstrap 显式不附带旧 token
- **WHEN** 登录协调器调用微信 exchange 或首次注册 bootstrap 接口
- **THEN** transport 按公开路由策略发送请求，不把已清除、过期或上一用户的 token 附加到请求

#### Scenario: 损坏或未知版本的缓存
- **WHEN** auth 或 current-user 持久化值无法通过当前 schema version 和运行时校验
- **THEN** 客户端清除两类缓存并显示登录页面，不展示损坏值或上一用户信息

### Requirement: token 失效会原子退出客户端登录状态
客户端 SHALL 在本地发现 token 已过期或共享 transport 收到任一受保护 API 的 `401` 时，同时清除 auth token 和 current-user display 缓存，并显示登录页面。客户端 MUST NOT 静默调用 `wx.login`、MUST NOT 自动重试原业务请求，也 MUST NOT 在清理后继续展示上一位用户的信息。

#### Scenario: 本地到期检查退出登录
- **WHEN** 小程序启动或准备业务请求时发现缓存 token 的到期时间已到
- **THEN** 客户端清除两类缓存并显示登录页面，不发送原业务请求

#### Scenario: API 返回 401 后退出登录
- **WHEN** 共享 request 或 upload transport 收到 `401`
- **THEN** 客户端只执行一次集中失效处理，清除 token 与当前用户缓存并显示登录页面

#### Scenario: 不静默登录或重试
- **WHEN** token 失效导致某个 overview、目标画像或知识来源请求返回 `401`
- **THEN** 客户端不调用 `wx.login`，不重放该请求，直到用户重新点击微信登录

#### Scenario: 清理避免展示上一用户
- **WHEN** 一个用户的 token 失效后另一用户尚未登录
- **THEN** 首页、“我的”和上传页面均不显示前一用户的 nickname、头像、目标画像、简历或来源数据

### Requirement: 认证敏感值不会泄露
系统 MUST NOT 在数据库、客户端响应或普通结构化日志中泄露不应持久化或展示的认证敏感值。日志与 Problem Details MUST NOT 包含明文 Bearer token、微信临时 code、AppSecret、session_key、完整供应商原始响应或原始异常详情；注册 token 与 session token 的服务端持久化 SHALL 只保存安全摘要。

#### Scenario: 成功认证日志保持脱敏
- **WHEN** 微信 exchange、注册或 Bearer 认证成功并产生日志
- **THEN** 日志只包含 request ID、稳定事件名、内部用户或 session 的安全标识，不包含 code、token、AppSecret、session_key 或完整微信响应

#### Scenario: 供应商错误响应保持安全
- **WHEN** 微信或 OSS adapter 抛出包含供应商请求、凭证或原始错误文本的异常
- **THEN** 客户端只收到稳定 Problem Details，普通日志只记录安全错误码和异常类型

#### Scenario: 数据库不保存禁止字段
- **WHEN** 检查微信身份、注册 bootstrap、session 和用户头像相关表
- **THEN** 不存在 session_key、明文 session token、明文注册 token、微信临时路径、永久公开头像 URL 或 AppSecret 字段

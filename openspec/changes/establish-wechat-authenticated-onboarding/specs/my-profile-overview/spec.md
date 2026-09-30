# Spec Delta

## MODIFIED Requirements

### Requirement: 系统持久化个人概览所需的当前业务数据
系统 SHALL 在 PostgreSQL 中持久化用户展示信息、外部微信身份映射、零个或多个目标画像以及零个或一个当前简历元数据记录。用户展示信息 SHALL 包含不可在本 change 修改的 nickname 和可空、provider-neutral 的 avatar object key，MUST NOT 保存微信临时路径、永久公开头像 URL 或供应商凭证。目标画像 SHALL 描述用户希望模拟的岗位和该目标对应的经验月份，而不是用户现实职业；新用户 MAY 没有默认目标画像。当前简历元数据 SHALL 使用与存储供应商无关的格式，包含原始文件名、媒体类型、文件大小、内容 SHA-256、存储对象 key、内容修订号、上传时间和更新时间；它 MUST NOT 包含 PDF 二进制、永久公开 URL 或供应商凭证。微信身份映射 SHALL 保留 `app_id`、`openid` 和可空 `unionid`，并 MUST NOT 持久化 `session_key`。

#### Scenario: 一个用户拥有多个目标画像
- **WHEN** 同一用户保存多个不同岗位或经验月份的目标画像
- **THEN** 系统保留全部目标画像，并明确标记其中至多一个为默认目标画像

#### Scenario: 新用户没有目标画像
- **WHEN** 微信首次注册创建新用户但尚未保存目标岗位
- **THEN** 系统不创建候选画像记录，并以默认目标画像不存在表达 onboarding 未完成

#### Scenario: 一个用户只有一份当前简历
- **WHEN** 系统检查某个用户的当前简历关系
- **THEN** 该用户至多关联一条当前简历元数据记录，记录只代表未来上传流程成功提交的当前文件，且本次能力不创建历史简历版本或真实文件生命周期

#### Scenario: development 用户尚未上传简历
- **WHEN** development 的确定性 fake 微信用户首次注册或测试 fixture 尚未上传简历
- **THEN** 用户不包含 `user_resume` 记录，系统以记录不存在表达“尚未上传”，而不是创建占位元数据

#### Scenario: 用户使用默认头像
- **WHEN** 用户没有自定义头像
- **THEN** avatar object key 为 `null`，系统不创建占位头像对象或保存永久公开 URL

#### Scenario: 用户拥有自定义头像
- **WHEN** 用户在首次注册期间成功保存自定义头像
- **THEN** 用户记录只保存 provider-neutral object key，个人概览可按需返回短期签名 URL

#### Scenario: 微信身份不保存 session_key
- **WHEN** 微信 adapter 完成 code2Session
- **THEN** 持久化身份只包含 `app_id`、`openid` 和可空 `unionid`，任何表都不包含 `session_key`

#### Scenario: 微信身份字段为后续登录预留
- **WHEN** development/test 使用确定性 fake 微信 adapter 创建或读取微信身份
- **THEN** `app_id`、`openid` 和可空 `unionid` 作为当前登录绑定使用，任何持久化记录都不包含 `session_key`

### Requirement: 非生产 local actor 提供稳定的当前身份
系统 SHALL 只在明确选择的聚焦 test 认证模式中，根据类型化配置把一个已持久化用户解析为 `ActorContext`。系统 MUST NOT 从任意调试请求头直接接受 actor ID，MUST NOT 在普通 development 微信认证模式下把 local actor 作为缺少 token 的回退，并 MUST NOT 在 production 注册或启用 local actor provider。

#### Scenario: 聚焦测试显式解析 local actor
- **WHEN** test 配置明确选择 local actor 模式并指定已持久化 actor ID
- **THEN** 个人概览聚焦测试使用该用户的 ActorContext 执行

#### Scenario: development 解析种子用户
- **WHEN** 聚焦 test 明确选择 local actor 模式并使用已种子的 actor ID
- **THEN** 个人概览查询使用该用户的 ActorContext；普通 development 微信模式不自动采用该 actor

#### Scenario: 普通 development 请求缺少 token
- **WHEN** development 使用微信认证模式且业务请求没有有效 Bearer token
- **THEN** 系统返回 `401`，不回退到 demo user 或全局固定用户

#### Scenario: 未提供可用身份
- **WHEN** 请求个人概览但没有有效 Bearer session，且当前聚焦测试也未显式选择 local actor
- **THEN** 系统返回 `401` RFC 9457 Problem Details，而不是退回到全局固定用户

#### Scenario: 任意 actor header 不受信任
- **WHEN** 客户端发送自定义 actor ID header
- **THEN** 系统忽略该 header，身份只来自已选择的认证模式

#### Scenario: production 不接受 local actor
- **WHEN** production 配置尝试选择 local actor provider
- **THEN** 系统在开始处理请求前拒绝该配置

### Requirement: 当前用户可以读取类型化个人概览
系统 SHALL 提供受保护的 `GET /api/v1/me/overview`，并 SHALL 直接返回类型化资源，其中包含当前用户的 `id`、`nickname`、可空短期签名 `avatar_url`、可空默认目标画像、可空当前简历展示元数据以及 `recent_scores` 集合。默认目标画像非空时 SHALL 包含 `id`、`target_role` 和 `relevant_experience_months`。当前简历展示元数据 MUST NOT 暴露存储对象 key、内容 SHA-256、永久访问 URL 或供应商信息。当前 change 未接入面试历史，因此 `recent_scores` SHALL 返回空集合。

#### Scenario: 返回有目标画像和自定义头像的概览
- **WHEN** 已认证用户拥有默认目标画像和自定义头像并请求 overview
- **THEN** 响应为 `200`，返回 owner-scoped 展示字段、默认目标画像和短期签名 avatar_url，不返回 avatar object key

#### Scenario: 返回 development 种子用户概览
- **WHEN** 聚焦 test 通过显式 local actor 或 development fake 微信登录请求种子用户 overview
- **THEN** 响应为 `200`，用户展示字段、可空默认目标画像和可空当前简历均来自该 actor 的持久化记录，`recent_scores` 为空

#### Scenario: 返回默认头像
- **WHEN** 已认证用户没有自定义头像并请求 overview
- **THEN** 响应为 `200` 且 `avatar_url` 为 `null`，客户端负责渲染内置默认头像

#### Scenario: 返回已有当前简历的概览
- **WHEN** 已认证用户拥有已持久化的当前简历元数据并请求个人概览
- **THEN** 响应为 `200`，`current_resume` 包含文件标识、原始文件名、媒体类型、文件大小、修订号和时间信息，但不包含存储定位或访问凭证

#### Scenario: 当前用户没有简历
- **WHEN** 已认证用户没有当前简历并请求个人概览
- **THEN** 响应为 `200`，`current_resume` 为 `null`，其余用户字段正常返回

#### Scenario: 当前用户有多个目标画像
- **WHEN** 已认证用户有多个目标画像并请求个人概览
- **THEN** 响应只返回明确标记的默认目标画像，不以创建时间或数据库返回顺序隐式选择

#### Scenario: 当前用户没有默认目标画像
- **WHEN** 已认证用户没有明确标记的默认目标画像并请求个人概览
- **THEN** 系统返回 `200` 和 `default_target_profile: null`，不返回 `profile_overview_incomplete` 且不猜测其他画像

#### Scenario: 未认证请求被拒绝
- **WHEN** 客户端没有有效 session 并请求 `/api/v1/me/overview`
- **THEN** 共享认证边界返回 `401`，个人概览读取不执行

### Requirement: “我的”页面按真实数据呈现完整状态
微信小程序 SHALL 按 `docs/design/visuals/home-overview.html` 的“我的”页面方向展示个人卡片、默认目标画像、当前简历、历史成绩空态和设置栏目。页面 SHALL 通过统一 authenticated API transport 请求 `/api/v1/me/overview`，并 SHALL 区分加载、成功、默认头像、空目标画像、无简历、空历史、目标画像保存中、保存成功和错误状态。nickname 与头像 SHALL 只读；目标画像的创建和修改行为由 `target-profile-management` 定义。页面不得用硬编码用户数据、虚假岗位或伪造成绩补齐展示。

#### Scenario: 加载个人概览
- **WHEN** “我的”页面正在等待携带 auth token 的 overview 响应
- **THEN** 页面显示明确加载状态，且不短暂展示上一用户或种子用户的姓名、头像、岗位、经验或简历

#### Scenario: 展示成功响应
- **WHEN** overview 成功并包含用户、默认目标画像和当前简历
- **THEN** 页面展示响应中的只读 nickname、头像、目标岗位、格式化经验和当前简历文件名

#### Scenario: 展示默认头像
- **WHEN** overview 成功且 `avatar_url` 为 `null` 或短期 URL 不可用
- **THEN** 页面展示小程序内置默认头像，不显示损坏的永久 URL 或头像编辑入口

#### Scenario: 展示空目标画像
- **WHEN** overview 成功且 `default_target_profile` 为 `null`
- **THEN** 页面显示可填写目标岗位和经验月份的 onboarding 状态，而不是把响应解释为错误

#### Scenario: 展示无简历状态
- **WHEN** overview 成功且 `current_resume` 为 `null`
- **THEN** 当前简历栏目展示“尚未上传，将在模拟面试时添加”的明确空态，不伪造文件名、下载链接或本 change 内的上传入口

#### Scenario: 展示空历史状态
- **WHEN** overview 成功且 `recent_scores` 为空
- **THEN** 历史成绩栏目展示无记录空态，不绘制虚假趋势线、分数或最近场次

#### Scenario: 展示 overview 错误
- **WHEN** 非 401 的 overview 请求失败
- **THEN** 页面展示可理解的错误和重试动作，且不会把失败解释为空目标画像、无简历或无历史

#### Scenario: 展示请求错误
- **WHEN** 非认证类网络或服务错误导致个人概览请求失败
- **THEN** 页面展示可理解的错误状态和重试动作，且不会把失败解释为空目标画像、无简历或无历史

#### Scenario: 401 清除页面用户状态
- **WHEN** overview 返回 `401`
- **THEN** 共享 transport 清除 auth 与 current-user 缓存并显示登录页面，“我的”不保留上一用户内容或自动重试

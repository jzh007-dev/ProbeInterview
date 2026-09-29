# my-profile-overview Specification

## Purpose

定义当前用户个人概览的持久化、身份隔离、只读 API 和微信小程序展示契约，使尚未接入微信登录的本地环境也能用真实数据库数据验收“我的”页面。

## Requirements

### Requirement: 系统持久化个人概览所需的当前业务数据
系统 SHALL 在 PostgreSQL 中持久化用户展示信息、外部微信身份映射、零个或多个目标画像以及零个或一个当前简历元数据记录。目标画像 SHALL 描述用户希望模拟的岗位和该目标对应的经验月份，而不是用户现实职业。当前简历元数据 SHALL 使用与存储供应商无关的格式，包含原始文件名、媒体类型、文件大小、内容 SHA-256、存储对象 key、内容修订号、上传时间和更新时间；它 MUST NOT 包含 PDF 二进制、永久公开 URL 或供应商凭证。微信身份映射 SHALL 保留 `app_id`、`openid` 和可空的 `unionid`，并 MUST NOT 持久化 `session_key`。

#### Scenario: 一个用户拥有多个目标画像
- **WHEN** 同一用户保存多个不同岗位或经验月份的目标画像
- **THEN** 系统保留全部目标画像，并明确标记其中至多一个为默认目标画像

#### Scenario: 一个用户只有一份当前简历
- **WHEN** 系统检查某个用户的当前简历关系
- **THEN** 该用户至多关联一条当前简历元数据记录，记录只代表未来上传流程成功提交的当前文件，且本次能力不创建历史简历版本或真实文件生命周期

#### Scenario: development 用户尚未上传简历
- **WHEN** development 初始化个人概览演示数据
- **THEN** 种子用户不包含 `user_resume` 记录，系统以记录不存在表达“尚未上传”，而不是创建没有实际文件的占位元数据

#### Scenario: 微信身份字段为后续登录预留
- **WHEN** development 初始化个人概览演示数据
- **THEN** 种子用户拥有符合微信标识字段形态的 `app_id`、`openid` 和可空 `unionid`，且任何持久化记录都不包含 `session_key`

### Requirement: 非生产 local actor 提供稳定的当前身份
系统 SHALL 在 development/test 且 local actor 已启用时，根据类型化配置把一个已持久化用户解析为 `ActorContext`。系统 MUST NOT 从任意调试请求头直接接受 actor id，并 MUST NOT 在 production 注册或启用 local actor provider。

#### Scenario: development 解析种子用户
- **WHEN** development 使用已启用的 local actor 配置启动并指定一个已种子的 actor id
- **THEN** 个人概览查询使用该用户的 `ActorContext` 执行

#### Scenario: 未提供可用身份
- **WHEN** 请求个人概览但没有任何身份 provider 解析出当前 actor
- **THEN** 系统返回 `401` RFC 9457 Problem Details，而不是退回到全局固定用户

#### Scenario: production 不接受 local actor
- **WHEN** production 配置尝试启用 local actor provider
- **THEN** 系统在开始处理请求前拒绝该配置

### Requirement: 当前用户可以读取类型化个人概览
系统 SHALL 提供 `GET /api/v1/me/overview`，并 SHALL 直接返回类型化资源，其中包含当前用户的 `id`、`nickname`、`avatar_url`，默认目标画像的 `id`、`target_role`、`relevant_experience_months`，可空的当前简历展示元数据，以及 `recent_scores` 集合。当前简历展示元数据 MUST NOT 暴露存储对象 key、内容 SHA-256、永久访问 URL 或供应商信息。当前 change 未接入面试历史，因此 `recent_scores` SHALL 返回空集合。

#### Scenario: 返回 development 种子用户概览
- **WHEN** development 种子用户请求 `/api/v1/me/overview`
- **THEN** 响应为 `200`，用户展示字段和默认目标画像来自该 actor 的持久化记录，`current_resume` 为 `null`，且 `recent_scores` 为空

#### Scenario: 返回已有当前简历的概览
- **WHEN** 已解析 actor 的用户拥有已持久化的当前简历元数据并请求个人概览
- **THEN** 响应为 `200`，`current_resume` 包含文件标识、原始文件名、媒体类型、文件大小、修订号和时间信息，但不包含存储定位或访问凭证

#### Scenario: 当前用户没有简历
- **WHEN** 已解析 actor 的用户没有当前简历并请求个人概览
- **THEN** 响应为 `200`，`current_resume` 为 `null`，其余用户和默认目标画像字段仍正常返回

#### Scenario: 当前用户有多个目标画像
- **WHEN** 已解析 actor 的用户有多个目标画像并请求个人概览
- **THEN** 响应只返回明确标记的默认目标画像，不以创建时间或数据库返回顺序隐式选择

#### Scenario: 当前用户没有默认目标画像
- **WHEN** 已解析 actor 的用户没有明确标记的默认目标画像并请求个人概览
- **THEN** 系统返回 `409` RFC 9457 Problem Details，且不猜测或隐式选择其他目标画像

### Requirement: 个人概览读取在数据库查询前按 actor 隔离
系统 MUST 在读取用户、目标画像或当前简历前应用当前 `ActorContext` 的 owner scope，并 MUST NOT 组合或返回其他 actor 的个人数据。

#### Scenario: 两名 actor 读取各自数据
- **WHEN** 两个不同 actor 分别请求个人概览，且各自拥有不同昵称、目标画像和简历
- **THEN** 每个响应只包含对应 actor 的记录

#### Scenario: 当前 actor 缺少简历但其他 actor 拥有简历
- **WHEN** 当前 actor 没有简历而另一 actor 拥有当前简历
- **THEN** 当前 actor 的响应仍返回 `current_resume: null`，不会回退或泄露另一 actor 的简历

### Requirement: “我的”页面按真实数据呈现完整状态
微信小程序 SHALL 按 `docs/design/visuals/home-overview.html` 的“我的”页面方向展示个人卡片、当前简历、历史成绩空态和设置栏目。页面 SHALL 从 `/api/v1/me/overview` 读取数据，并 SHALL 区分加载、成功、无简历、空历史和错误状态，不得用页面内硬编码用户数据或伪造成绩补齐展示。

#### Scenario: 加载个人概览
- **WHEN** “我的”页面正在等待概览响应
- **THEN** 页面显示明确的加载状态，且不短暂展示种子用户的硬编码姓名、岗位、经验或简历

#### Scenario: 展示成功响应
- **WHEN** 个人概览请求成功并包含用户、默认目标画像和当前简历
- **THEN** 页面展示响应中的昵称、头像、目标岗位、按经验月份格式化的目标经验以及当前简历文件名

#### Scenario: 展示无简历状态
- **WHEN** 个人概览请求成功且 `current_resume` 为 `null`
- **THEN** 当前简历栏目展示“尚未上传，将在模拟面试时添加”的明确空态，不伪造文件名、下载链接或本 change 内的上传入口

#### Scenario: 展示空历史状态
- **WHEN** 个人概览请求成功且 `recent_scores` 为空
- **THEN** 历史成绩栏目展示无记录空态，不绘制虚假趋势线、分数或最近场次

#### Scenario: 展示请求错误
- **WHEN** 个人概览请求失败
- **THEN** 页面展示可理解的错误状态和重试动作，且不会把失败解释为无简历或无历史

### Requirement: 五个 tab 和未来动作保持可扩展边界
微信小程序 SHALL 按“首页、复盘、模拟、上传、我的”的顺序提供五个 tab 页面。“我的” SHALL 展示个人概览，其他四个 tab 在本次 change 中 SHALL 只展示空页面壳。个人页上的设置、已有简历和历史栏目 SHALL 暴露稳定的命名动作，但 MUST NOT 在本次 change 中执行页面跳转、预览、上传、更换、下载或配置写入；简历上传入口 SHALL 留给后续模拟面试能力。

#### Scenario: 从其他 tab 进入“我的”
- **WHEN** 用户从首页、复盘、模拟或上传 tab 点击“我的”
- **THEN** 小程序切换到“我的”tab 并加载个人概览页面

#### Scenario: 进入未实现业务 tab
- **WHEN** 用户点击首页、复盘、模拟或上传 tab
- **THEN** 小程序展示对应的空页面壳且保持五个 tab 可继续切换

#### Scenario: 触发预留栏目动作
- **WHEN** 用户点击设置、已有当前简历、历史成绩、面试语言、隐私与数据或关于栏目
- **THEN** 页面识别对应的稳定命名动作，但不导航、不修改数据库且不启动文件操作

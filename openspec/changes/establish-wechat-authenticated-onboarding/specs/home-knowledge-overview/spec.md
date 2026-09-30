# Spec Delta

## MODIFIED Requirements

### Requirement: 首页优先使用客户端缓存中的当前用户昵称
微信小程序首页 SHALL 只通过类型化 current-user display store 读取 `nickname` 和可空默认目标画像摘要，并 MUST NOT 把缓存作为 API 鉴权或 capability 判断依据。缓存命中时页面 MUST NOT 请求 `/api/v1/me/overview`；缓存缺失、损坏或 schema version 不受支持时，页面 SHALL 清除 auth token 与当前用户缓存并进入登录页面，MUST NOT 回退请求 overview。登录或注册成功 SHALL 写入该缓存。页面在未获得有效缓存时 MUST NOT 展示硬编码 nickname、上一位用户数据或首页成功内容。

#### Scenario: 缓存命中直接展示昵称
- **WHEN** 已登录用户进入首页且存在通过运行时校验的当前用户展示缓存
- **THEN** 页面展示缓存中的 nickname 和首页内容，且不请求 `/api/v1/me/overview`

#### Scenario: 缓存缺失时进入登录页面
- **WHEN** 用户进入首页但不存在有效 current-user 缓存
- **THEN** 页面不请求 overview，清除任何残留 auth 状态并显示登录页面

#### Scenario: 缓存缺失时回退当前用户概览
- **WHEN** 登录能力已交付后用户进入首页但不存在有效 current-user 缓存
- **THEN** 旧的 overview 回退路径不再执行，页面清除残留状态并显示登录页面

#### Scenario: 损坏缓存不泄露旧值
- **WHEN** current-user 缓存无法通过 schema version 或运行时字段校验
- **THEN** 页面清除 auth 与 current-user 缓存，不展示其中的 nickname、头像或目标画像，并进入登录页面

#### Scenario: 回退请求失败
- **WHEN** 首页缓存不可用且旧 overview client 即使会返回失败
- **THEN** 首页也不调用该 client，而是直接显示登录页面且不把失败解释为空知识库

#### Scenario: 重试后恢复成功
- **WHEN** 用户在登录页面重新主动完成微信登录或注册并返回首页
- **THEN** 首页从新写入的 current-user 缓存恢复成功状态，不重试旧 overview 回退请求

#### Scenario: 登录成功后首页使用新缓存
- **WHEN** 用户完成微信登录或首次注册并进入首页
- **THEN** 页面展示登录协调器写入的当前用户 nickname，不为补充昵称或目标画像请求 overview

#### Scenario: token 失效后不展示上一用户
- **WHEN** 共享 transport 因 `401` 清除 token 和 current-user 缓存
- **THEN** 首页退出成功状态并显示登录页面，不继续展示先前 nickname 或目标画像

### Requirement: 首页展示确定性的 fake 知识训练概览
首页 SHALL 按 `docs/design/visuals/home-knowledge-categories.html` 的视觉层级展示本周训练覆盖、待复盘数量、继续学习卡片和“按主题学习”分类。除 current-user 缓存中的 nickname 与默认目标画像摘要外，本 change 的训练、进度、知识卡片和主题数据 SHALL 全部来自单一确定性 fake fixture，MUST NOT 从知识 API、数据库或页面内分散硬编码中拼装。

#### Scenario: 展示固定训练概览
- **WHEN** 首页读取到有效 current-user 缓存并进入成功状态
- **THEN** 页面展示 fixture 中的本周训练覆盖、待复盘数量、继续学习标题、摘要和进度

#### Scenario: 展示六个主题
- **WHEN** 首页处于成功状态
- **THEN** 页面展示 Agent 系统、RAG、Prompt 与上下文、模型应用、评测与可靠性、工程化六个主题及 fixture 中的说明和知识点数量

#### Scenario: 不请求用户或知识 API
- **WHEN** 首页完成一次加载并展示成功状态
- **THEN** 页面不请求 overview、知识来源、知识点、学习进度、复盘统计或搜索 API

#### Scenario: 不请求尚未存在的知识 API
- **WHEN** 首页完成一次加载并展示成功状态
- **THEN** 页面不请求知识来源、知识点、学习进度、复盘统计或搜索 API，也不以 overview 作为身份展示回退

## ADDED Requirements

### Requirement: 首页根据缓存提示填写目标岗位
首页 SHALL 从 current-user display store 的 `default_target_profile` 判断当前用户是否已有默认目标画像。值为 `null` 时，页面 SHALL 在“按主题学习”区域下方展示“请在我的页面填写目标岗位”，并 SHALL 提供通过 `wx.switchTab` 进入“我的”页面的动作；页面 MUST NOT 展示虚假默认岗位或经验，也 MUST NOT 为确认该状态调用 overview。

#### Scenario: 空目标画像显示提示
- **WHEN** 有效 current-user 缓存的 `default_target_profile` 为 `null`
- **THEN** 首页在“按主题学习”下方展示“请在我的页面填写目标岗位”，不展示虚假岗位或经验

#### Scenario: 提示切换到“我的”
- **WHEN** 用户点击目标岗位填写提示
- **THEN** 小程序通过 `wx.switchTab` 进入“我的”页面，不调用 overview 或目标画像写接口

#### Scenario: 已有目标画像不显示提示
- **WHEN** 有效 current-user 缓存包含非空默认目标画像摘要
- **THEN** 首页不展示目标岗位填写提示，且不为该判断发起网络请求

#### Scenario: 保存目标画像后提示消失
- **WHEN** 用户在“我的”页面成功保存默认目标画像并返回首页
- **THEN** 首页重新读取已更新缓存，提示消失且不请求 overview

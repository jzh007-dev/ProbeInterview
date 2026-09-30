# Spec Delta

## Purpose

定义已认证当前用户创建或修改默认目标岗位与相关经验月份的行为、校验、owner 隔离和小程序缓存同步，使新用户无需虚假默认值即可完成基础面试目标 onboarding。

## ADDED Requirements

### Requirement: 新用户可以没有默认目标画像
新注册用户 SHALL 在没有用户输入时保持 `default_target_profile: null`，系统 MUST NOT 创建虚假的默认岗位、经验月份或候选画像。默认目标画像只有在当前 actor 明确保存合法 `target_role` 和 `relevant_experience_months` 后才存在。

#### Scenario: 新用户初始没有目标画像
- **WHEN** 首次注册成功但用户尚未填写目标岗位
- **THEN** 用户展示快照和个人概览均包含 `default_target_profile: null`，数据库不包含该用户的默认目标画像

#### Scenario: 其他用户的目标画像不能填充空值
- **WHEN** 当前 actor 没有默认目标画像而另一 actor 已有默认目标画像
- **THEN** 当前 actor 仍得到 `null`，系统不复制、猜测或回退到另一用户的数据

### Requirement: 当前用户可以创建或修改默认目标画像
系统 SHALL 提供受保护的 `PUT /api/v1/me/default-target-profile`，接受 `target_role` 和 `relevant_experience_months`，并直接返回类型化默认目标画像资源。`target_role` SHALL 去除首尾空白后保持非空并符合长度与安全字符约束；`relevant_experience_months` SHALL 为服务端允许范围内的非负整数。当前 actor 没有默认目标画像时该命令 SHALL 创建一个，有默认目标画像时 SHALL 修改同一默认画像；它 MUST NOT 修改 nickname、头像或其他用户的画像。

#### Scenario: 创建默认目标画像
- **WHEN** 已认证且没有默认目标画像的用户提交合法岗位和经验月份
- **THEN** 系统创建并返回该用户唯一的默认目标画像

#### Scenario: 修改默认目标画像
- **WHEN** 已认证且已有默认目标画像的用户提交新的合法岗位或经验月份
- **THEN** 系统更新并返回同一默认目标画像，不创建第二个默认画像

#### Scenario: 重复提交相同表示
- **WHEN** 用户重复 PUT 相同的规范化岗位和经验月份
- **THEN** 系统返回相同默认目标画像表示且不创建重复记录

#### Scenario: 拒绝无效岗位
- **WHEN** 用户提交空白、过长或包含禁止字符的 target_role
- **THEN** 系统返回字段级 RFC 9457 Problem Details，现有默认目标画像保持不变

#### Scenario: 拒绝无效经验月份
- **WHEN** 用户提交负数、非整数或超过服务端允许范围的 relevant_experience_months
- **THEN** 系统返回字段级 RFC 9457 Problem Details，现有默认目标画像保持不变

#### Scenario: 未认证用户不能保存
- **WHEN** 缺少有效 session 的客户端调用目标画像写接口
- **THEN** 共享认证边界返回 `401`，不创建或修改任何目标画像

### Requirement: 目标画像命令在数据库访问前应用 owner scope
目标画像读取和写入 SHALL 在查询、创建或更新数据库记录前使用当前 `ActorContext.actor_id` 作为 owner scope。不可见目标画像 SHALL 与不存在保持一致，客户端提供的用户 ID 或画像 ID MUST NOT 改变 owner。

#### Scenario: 两名用户创建各自目标画像
- **WHEN** 两个 actor 分别保存不同岗位和经验月份
- **THEN** 每个 actor 只创建或修改自己的默认目标画像

#### Scenario: 当前用户不能修改另一用户画像
- **WHEN** 当前 actor 的输入或请求上下文包含另一用户的画像标识
- **THEN** 系统忽略或拒绝该跨用户标识，另一用户记录保持不变且其存在性不被泄露

#### Scenario: 并发首次保存保持唯一默认
- **WHEN** 同一 actor 并发提交两个首次默认目标画像写请求
- **THEN** 数据库最终至多有一个默认画像，成功结果收敛到 owner-scoped 默认记录且不会突破唯一约束

### Requirement: “我的”页面支持目标画像 onboarding 和更新
微信小程序“我的”页面 SHALL 在 overview 成功后展示目标画像的只读摘要或编辑表单，并 SHALL 支持创建和修改目标岗位及相关经验月份。页面 SHALL 区分 overview 加载、空目标画像、编辑、保存中、保存成功和保存错误状态；nickname 与头像在本 change 中保持只读。

#### Scenario: 空目标画像显示填写状态
- **WHEN** overview 返回 `default_target_profile: null`
- **THEN** “我的”页面显示目标岗位与经验月份输入，不把空值渲染成虚假岗位或错误状态

#### Scenario: 已有目标画像显示当前值
- **WHEN** overview 返回非空默认目标画像
- **THEN** 页面展示当前岗位和格式化经验，并允许用户进入编辑状态

#### Scenario: 保存期间防止重复提交
- **WHEN** 合法目标画像写请求尚未完成
- **THEN** 页面显示保存中状态并阻止重复提交

#### Scenario: 保存成功同步当前用户缓存
- **WHEN** 创建或修改 API 成功返回默认目标画像
- **THEN** 页面更新显示值，并把返回的 nullable 目标画像摘要写入 current-user display store，保留原用户 ID、nickname 和头像信息

#### Scenario: 保存失败保留可修正输入
- **WHEN** 校验、网络或服务错误导致保存失败
- **THEN** 页面显示可理解的错误，保留用户输入并允许重试，不写入虚假的成功缓存

#### Scenario: nickname 和头像保持只读
- **WHEN** 用户查看或编辑目标画像
- **THEN** 页面不提供 nickname 或头像修改动作，也不调用相关修改 API

### Requirement: 目标画像缓存更新可被首页立即观察
current-user display store 中的默认目标画像摘要 SHALL 与成功登录、注册或目标画像保存结果同步。目标画像保存成功后，返回首页 SHALL 读取更新后的缓存而不调用 overview。

#### Scenario: 保存后首页提示消失
- **WHEN** 用户从空目标画像状态保存成功并返回首页
- **THEN** 首页从缓存读取非空目标画像摘要，不再展示“请在我的页面填写目标岗位”，且不请求 overview

#### Scenario: 修改后首页读取新岗位
- **WHEN** 用户修改默认目标岗位并返回首页
- **THEN** current-user 缓存包含新的岗位和经验月份，旧摘要不再显示

#### Scenario: 保存失败不污染首页缓存
- **WHEN** 目标画像保存失败
- **THEN** current-user 缓存保持保存前状态，首页仍反映原目标画像或空目标画像提示

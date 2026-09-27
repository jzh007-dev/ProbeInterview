# Spec Delta

## Purpose

为微信小程序封闭试用用户提供私有 Markdown 知识资料、个人题库和知识卡片管理能力，并通过首页卡片流支持持续学习、来源识别和复盘关联。

## ADDED Requirements

### Requirement: MVP 仅允许指定微信身份访问
系统 SHALL 仅允许配置的微信身份进入 MVP，并 SHALL 为该身份建立内部 `user_id`；所有私人内容 SHALL 显式保存 owner 归属。

#### Scenario: 指定微信身份登录
- **WHEN** 配置允许的微信身份完成登录
- **THEN** 系统将其映射到内部用户并允许访问其私人内容

#### Scenario: 未授权微信身份登录
- **WHEN** 不在允许名单中的微信身份尝试进入 MVP
- **THEN** 系统拒绝访问且 MUST NOT 自动注册新用户

### Requirement: 小程序提供固定的用户导航结构
系统 SHALL 在用户主界面提供“首页、复盘、模拟、上传、我的”五个入口，并将“模拟”作为底部导航中央的突出入口。

#### Scenario: 用户从首页开始模拟面试
- **WHEN** 用户点击底部导航中央的“模拟”
- **THEN** 系统进入模拟面试配置流程

#### Scenario: 用户切换到知识上传
- **WHEN** 用户点击底部导航中的“上传”
- **THEN** 系统展示开始上传、历史上传记录和个人知识库入口

### Requirement: 首页以知识卡片流为主要内容
系统 SHALL 在首页以可滑动翻页的知识卡片流展示知识点，并展示卡片来源、学习状态、复盘次数和当前待复盘状态。

#### Scenario: 用户浏览下一张知识卡片
- **WHEN** 用户滑动离开当前知识卡片
- **THEN** 系统记录一次浏览但 MUST NOT 自动将该卡片标记为已学习

#### Scenario: 用户明确完成学习
- **WHEN** 用户点击知识卡片上的“已学习”
- **THEN** 系统更新该卡片的学习状态

### Requirement: 私人知识资料仅支持 Markdown
系统 SHALL 仅允许用户上传 Markdown 格式的私人知识资料，并 SHALL 在上传页展示处理状态、历史记录和解析失败原因。

#### Scenario: 用户上传可解析的 Markdown 知识资料
- **WHEN** 用户提交可读取的 Markdown 知识资料
- **THEN** 系统解析内容、分配或关联知识点 ID，并加入该用户的个人知识库

#### Scenario: 用户上传非 Markdown 知识资料
- **WHEN** 用户提交 PDF、DOCX、图片、XMind 或其他非 Markdown 文件作为私人知识资料
- **THEN** 系统拒绝入库并提示私人知识资料仅支持 Markdown

#### Scenario: Markdown 内容无法解析
- **WHEN** 用户提交的 Markdown 缺少可识别内容或结构无法处理
- **THEN** 系统保留失败记录并展示可操作的失败原因

### Requirement: 私人面试题库仅支持 Markdown
系统 SHALL 允许用户通过 Markdown 上传私人题目；题目正文 MUST 存在，参考答案和评分要点可以省略。

#### Scenario: 题目包含完整评分信息
- **WHEN** Markdown 题目包含题目正文、参考答案和评分要点
- **THEN** 系统保存用户提供的内容并标记其来源为用户

#### Scenario: 题目缺少参考答案或评分要点
- **WHEN** Markdown 题目仅包含题目正文或评分信息不完整
- **THEN** 系统生成候选知识点、参考答案、评分要点和难度，并明确标记为 AI 推断

#### Scenario: 用户上传非 Markdown 私人题库
- **WHEN** 用户提交 XMind、PDF、图片或其他非 Markdown 文件作为私人题库
- **THEN** 系统拒绝入库并提示私人题库仅支持 Markdown

### Requirement: 知识卡片区分来源并允许修正
系统 SHALL 标记知识卡片来自用户资料还是 AI 生成，并 SHALL 允许用户编辑 AI 生成的卡片。

#### Scenario: 用户编辑 AI 生成卡片
- **WHEN** 用户保存对 AI 生成卡片的修改
- **THEN** 系统保留其原始来源并将状态显示为“AI 生成，用户已修改”

#### Scenario: 已修改卡片再次用于复盘
- **WHEN** 新复盘项关联到用户已修改的同一知识点 ID
- **THEN** 系统复用现有卡片且 MUST NOT 用新生成内容覆盖用户修改

### Requirement: 知识卡片使用稳定 ID 进行确定性关联
系统 SHALL 优先按稳定平台知识点 ID 或私人临时知识点 ID 关联已有卡片，并可使用规范化文本指纹阻止同一来源内容的确定性重复；MVP MUST NOT 使用向量相似度自动合并卡片。

#### Scenario: 短板知识点已有卡片
- **WHEN** 一个短板携带的知识点 ID 已关联到该用户的知识卡片
- **THEN** 系统关联现有卡片并更新复盘次数及最近复盘时间

#### Scenario: 短板知识点没有卡片
- **WHEN** 一个有效知识点 ID 没有关联的用户知识卡片
- **THEN** 系统允许创建标记为 AI 生成的通用知识卡片

#### Scenario: 两张卡片内容相似但 ID 不同
- **WHEN** 两张卡片文本相似但没有相同知识点 ID 或确定性来源指纹
- **THEN** 系统 MUST NOT 自动将它们合并

### Requirement: 用户私人内容默认隔离
系统 SHALL 将用户上传的资料、私人题库、知识卡片和学习状态限制为 owner 可访问，且 MUST NOT 自动发布到平台核心知识库、公共评估集或模型训练数据。

#### Scenario: 其他用户访问私人内容
- **WHEN** 其他身份请求不属于自己的私人内容
- **THEN** 系统拒绝访问且不泄露内容是否存在

#### Scenario: 系统创建离线评估样本
- **WHEN** 系统准备全局或共享的离线评估输入
- **THEN** 系统 MUST NOT 自动复制用户的简历、JD、完整回答、私人资料或私人题库

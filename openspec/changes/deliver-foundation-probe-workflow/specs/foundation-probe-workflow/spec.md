# Spec Delta

## Purpose

定义验证环境中的非业务 foundation probe 工作流，使客户端、API、数据库、Redis/Celery、Worker、pgvector 与 fake 外部服务可以在 actor scope 内以幂等、可恢复且不泄露敏感信息的方式完成闭环。

## ADDED Requirements

### Requirement: 客户端可以完成异步 foundation probe
系统 SHALL 允许验证环境中的客户端创建 foundation probe、获得任务标识并轮询最终状态。

#### Scenario: 创建 probe
- **WHEN** 具有 actor context 的客户端提交有效 probe 请求
- **THEN** 系统持久化任务、返回任务标识和 QUEUED 状态，并异步投递执行

#### Scenario: probe 成功完成
- **WHEN** Worker 完成数据库与 pgvector 验证步骤
- **THEN** 系统将 probe 状态更新为 SUCCEEDED，客户端轮询可看到完成时间和非敏感结果摘要

#### Scenario: probe 执行失败
- **WHEN** Worker 在允许的重试后仍无法完成 probe
- **THEN** 系统将状态更新为 FAILED，并返回稳定错误码而不是后台异常详情

### Requirement: 异步命令支持幂等提交
系统 SHALL 按 actor、命令类型和幂等键识别重复提交，并 MUST NOT 为同一有效命令创建多个后台任务。

#### Scenario: 重复提交相同命令
- **WHEN** 同一 actor 使用相同幂等键和相同输入重复创建 probe
- **THEN** 系统返回原任务标识和当前状态

#### Scenario: 幂等键对应不同输入
- **WHEN** 同一 actor 使用已存在的幂等键提交不同输入
- **THEN** 系统拒绝请求并返回幂等冲突错误

### Requirement: 后台任务状态可恢复且可审计
系统 SHALL 持久化 QUEUED、RUNNING、SUCCEEDED 和 FAILED 状态、尝试次数及时间戳，并 SHALL 使重复投递不会重复产生成功结果。

#### Scenario: Worker 重复收到同一任务
- **WHEN** 同一任务因至少一次投递语义被 Worker 再次接收
- **THEN** Worker 根据持久化状态和幂等标识复用或安全完成原任务，不创建第二份结果

#### Scenario: Worker 执行中断
- **WHEN** Worker 在任务完成前中断
- **THEN** 系统保留已持久化状态并允许任务按照重试规则继续或最终失败

#### Scenario: QUEUED 任务投递空窗
- **WHEN** 数据库事务已提交但任务消息未成功投递且超过恢复阈值
- **THEN** 恢复命令只重新投递仍未进入终态的稳定 probe ID

### Requirement: Probe request ID 贯穿后台执行
系统 SHALL 在 probe 记录、后台执行记录、API 响应和相关安全日志中保留创建请求的 request ID。

#### Scenario: 请求创建后台任务
- **WHEN** 一个请求成功创建 foundation probe
- **THEN** probe 记录和后台执行记录引用同一个 request ID

### Requirement: Foundation probe 不依赖真实业务供应商
系统 SHALL 在 foundation probe 中通过应用端口使用可替换的 deterministic fake adapter，并 MUST NOT 要求真实 OSS、LLM 或 Embedding 凭证。

#### Scenario: 本地执行 probe
- **WHEN** 开发者在 development 或 test 未配置真实供应商密钥并发起 foundation probe
- **THEN** fake object storage 与 fake embedding 按相同输入返回可预测结果，probe 可以完成或触发显式可测试失败

#### Scenario: 日志记录 adapter 调用
- **WHEN** fake adapter 被 foundation probe 调用
- **THEN** 日志仅记录 adapter 类型、调用结果和 request ID，不记录输入正文或虚构的密钥值

### Requirement: 开发诊断客户端展示完整 probe 状态
系统 SHALL 仅在 development 构建中提供 foundation probe 诊断页，并 SHALL 展示创建、轮询和终态所需的安全信息。

#### Scenario: 诊断页发起并轮询 probe
- **WHEN** 开发者在 development 构建打开诊断页并发起有效 probe
- **THEN** 页面展示加载状态并按 QUEUED、RUNNING 到 SUCCEEDED 或 FAILED 的状态变化轮询更新

#### Scenario: probe 成功
- **WHEN** 轮询返回 SUCCEEDED
- **THEN** 页面展示完成时间和非敏感结果摘要，并停止继续轮询

#### Scenario: probe 失败或请求错误
- **WHEN** 创建、轮询或后台执行返回可展示错误
- **THEN** 页面展示稳定错误信息和可追踪 request ID，且不展示后台异常详情

#### Scenario: 用户重复点击创建
- **WHEN** 用户在同一提交进行中重复点击创建
- **THEN** 客户端复用同一幂等意图且不会产生多个不同任务

#### Scenario: production 构建
- **WHEN** 小程序以 production 配置构建
- **THEN** 诊断入口和页面不可访问

# Spec Delta

## Purpose

定义 ProbeInterview 后续业务能力共同依赖的运行与验证契约，使客户端、API、数据库、后台任务和向量扩展能通过一条隔离且可重复的 walking skeleton 被自动验证。

## ADDED Requirements

### Requirement: 服务公开存活与就绪状态
系统 SHALL 提供独立的存活检查和就绪检查，并 SHALL 仅在处理请求所需的基础依赖可用时报告就绪。

#### Scenario: API 进程存活
- **WHEN** 运维或自动化测试请求存活检查
- **THEN** 系统返回成功且不因非关键外部供应商不可用而失败

#### Scenario: 基础依赖不可用
- **WHEN** 数据库或任务投递依赖不可用
- **THEN** 系统的就绪检查返回不可用状态并标识失败的依赖类别

### Requirement: API 响应携带可追踪请求标识
系统 SHALL 为每个 API 请求接受或生成唯一 request ID，并 SHALL 在响应、错误和由该请求创建的后台任务中保留该标识。

#### Scenario: 客户端未提供 request ID
- **WHEN** 客户端发起请求但未提供 request ID
- **THEN** 系统生成 request ID 并在响应中返回

#### Scenario: 请求创建后台任务
- **WHEN** 一个请求成功创建 foundation probe
- **THEN** probe 记录和后台执行记录引用同一个 request ID

### Requirement: API 错误使用稳定结构
系统 SHALL 使用统一错误结构返回稳定错误码、用户可读消息和 request ID，并 MUST NOT 在响应中暴露堆栈、密钥或内部连接信息。

#### Scenario: 请求参数无效
- **WHEN** 客户端提交不符合接口约束的请求
- **THEN** 系统返回统一验证错误、字段信息和 request ID

#### Scenario: 服务发生未处理错误
- **WHEN** API 处理过程中发生未处理异常
- **THEN** 系统返回通用内部错误码和 request ID，且不返回内部堆栈或敏感配置

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

### Requirement: Foundation 数据按 actor 隔离
系统 SHALL 为 foundation probe 和测试向量保存 owner，并 MUST 在查询任务、状态和向量之前限制为公共范围或当前 actor 的范围。

#### Scenario: owner 查询自己的 probe
- **WHEN** actor 查询属于自己的 probe
- **THEN** 系统返回该 probe 的当前状态

#### Scenario: actor 查询其他 owner 的 probe
- **WHEN** actor 查询属于其他 owner 的 probe
- **THEN** 系统拒绝访问且不透露目标是否存在

#### Scenario: 向量 smoke query 执行
- **WHEN** Worker 为 probe 写入并查询固定测试向量
- **THEN** 查询只允许使用当前 actor 的有效测试向量且不会返回其他 owner 的记录

### Requirement: 后台任务状态可恢复且可审计
系统 SHALL 持久化 QUEUED、RUNNING、SUCCEEDED 和 FAILED 状态、尝试次数及时间戳，并 SHALL 使重复投递不会重复产生成功结果。

#### Scenario: Worker 重复收到同一任务
- **WHEN** 同一任务因至少一次投递语义被 Worker 再次接收
- **THEN** Worker 根据持久化状态和幂等标识复用或安全完成原任务，不创建第二份结果

#### Scenario: Worker 执行中断
- **WHEN** Worker 在任务完成前中断
- **THEN** 系统保留已持久化状态并允许任务按照重试规则继续或最终失败

### Requirement: 工程提供可重复的自动验证入口
系统 SHALL 提供文档化的统一验证入口，自动执行格式检查、静态检查、单元测试、数据库迁移测试、Worker 集成测试和 foundation probe 端到端测试。

#### Scenario: 全新环境执行验证
- **WHEN** 开发者按文档在满足前置条件的全新环境运行统一验证命令
- **THEN** 系统自动启动或连接隔离测试依赖并报告每类检查的成功或失败

#### Scenario: 关键依赖链路回归
- **WHEN** API、数据库、任务投递、Worker 或 pgvector 链路被破坏
- **THEN** 至少一个自动化测试失败并定位到对应阶段

### Requirement: Foundation probe 不依赖真实业务供应商
系统 SHALL 在 foundation 验证中使用可替换的本地或 fake adapter，并 MUST NOT 要求真实 OSS、LLM 或 Embedding 凭证。

#### Scenario: 未配置真实供应商密钥
- **WHEN** 开发者运行本地服务或自动测试且未配置真实供应商密钥
- **THEN** foundation probe 和完整自动验证仍可执行

#### Scenario: 日志记录 adapter 调用
- **WHEN** fake adapter 被 foundation probe 调用
- **THEN** 日志仅记录 adapter 类型、调用结果和 request ID，不记录输入正文或虚构的密钥值

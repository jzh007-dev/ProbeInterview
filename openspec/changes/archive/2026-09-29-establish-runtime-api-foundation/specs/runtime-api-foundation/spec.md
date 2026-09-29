# Spec Delta

## Purpose

定义 ProbeInterview 后续持久化与异步工作流共同依赖的可运行服务拓扑和 HTTP 基础契约，使网关、API、Worker、数据库、队列、健康状态、错误和追踪能被独立验证。

## ADDED Requirements

### Requirement: 基础运行拓扑可以按环境启动
系统 SHALL 提供包含 gateway、API、Worker、PostgreSQL + pgvector 和 Redis 的可重复运行拓扑，并 SHALL 使 API 与 Worker 使用同一应用版本但独立启动。

#### Scenario: 本地拓扑启动
- **WHEN** 开发者使用 development 配置启动基础运行拓扑
- **THEN** gateway、API、Worker、PostgreSQL 和 Redis 全部达到健康状态且 gateway 可以代理 API 请求

#### Scenario: 测试拓扑隔离
- **WHEN** 自动化测试启动 test profile
- **THEN** 系统使用可清理且不与 development 或 production 共享的测试容器、网络和数据卷

#### Scenario: production 入口配置
- **WHEN** 运维使用有效域名和 production 配置启动 gateway
- **THEN** gateway 作为唯一外部入口提供 TLS 并将 HTTP 请求跳转到 HTTPS，应用与数据服务不直接暴露公网

### Requirement: 服务公开存活与就绪状态
系统 SHALL 提供独立的存活检查和就绪检查，并 SHALL 仅在处理请求所需的基础依赖可用时报告就绪。

#### Scenario: API 进程存活
- **WHEN** 运维或自动化测试请求存活检查
- **THEN** 系统返回成功且不因非关键外部供应商不可用而失败

#### Scenario: 基础依赖不可用
- **WHEN** 数据库或任务投递依赖不可用
- **THEN** 系统的就绪检查返回不可用状态并标识失败的依赖类别

### Requirement: API 响应携带可追踪请求标识
系统 SHALL 为每个 API 请求接受或生成唯一 request ID，并 SHALL 在成功响应、错误响应和结构化日志中保留该标识。

#### Scenario: 客户端未提供 request ID
- **WHEN** 客户端发起请求但未提供 request ID
- **THEN** 系统生成 request ID 并在响应中返回

#### Scenario: 客户端提供合法 request ID
- **WHEN** 客户端发起请求并提供合法 request ID
- **THEN** 系统在响应与该请求的结构化日志中返回并保留同一标识

### Requirement: API 错误使用稳定结构
系统 SHALL 使用 RFC 9457 Problem Details 返回稳定错误码、用户可读消息和 request ID，并 MUST NOT 在响应中暴露堆栈、密钥或内部连接信息。

#### Scenario: 请求参数无效
- **WHEN** 客户端提交不符合接口约束的请求
- **THEN** 系统返回 `application/problem+json` 验证错误、字段信息和 request ID

#### Scenario: 服务发生未处理错误
- **WHEN** API 处理过程中发生未处理异常
- **THEN** 系统返回通用内部错误码和 request ID，且不返回内部堆栈或敏感配置

### Requirement: 运行日志结构化且不包含私密内容
系统 SHALL 输出可按 request ID、trace ID 和 job ID 关联的结构化日志，并 MUST NOT 在正常日志中记录请求正文、私人来源文本、完整 Prompt 或模型响应、密钥、令牌和连接串。

#### Scenario: 请求与运行单元产生日志
- **WHEN** API 或 Worker 记录一次正常运行事件
- **THEN** 日志包含适用的 request、trace 或 job 标识以及安全事件摘要

#### Scenario: 敏感值出现在异常上下文
- **WHEN** 异常上下文包含请求正文、密钥、令牌或连接信息
- **THEN** 结构化日志对敏感值进行排除或脱敏且仍保留可排障的稳定错误摘要

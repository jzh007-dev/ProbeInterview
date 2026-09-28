# Spec Delta

## Purpose

定义 foundation walking skeleton 的统一验收契约，使全新环境和未来任意 CI 平台都能通过同一根级入口验证代码质量、迁移、隔离、后台恢复及真实本地运行拓扑。

## ADDED Requirements

### Requirement: 工程提供可重复的自动验证入口
系统 SHALL 提供文档化的统一验证入口，自动执行格式检查、静态检查、单元测试、数据库迁移测试、Worker 集成测试和 foundation probe 端到端测试。

#### Scenario: 全新环境执行验证
- **WHEN** 开发者按文档在满足前置条件的全新环境运行统一验证命令
- **THEN** 系统自动启动或连接隔离测试依赖并报告每类检查的成功或失败

#### Scenario: 关键依赖链路回归
- **WHEN** API、数据库、任务投递、Worker 或 pgvector 链路被破坏
- **THEN** 至少一个自动化测试失败并定位到对应阶段

### Requirement: 完整验证不依赖真实业务供应商
系统 SHALL 使用 local actor 和 fake 外部服务 adapter 执行完整自动验证，并 MUST NOT 要求真实 OSS、LLM 或 Embedding 凭证。

#### Scenario: 未配置真实供应商密钥
- **WHEN** 开发者运行本地服务或自动测试且未配置真实供应商密钥
- **THEN** foundation probe 和完整自动验证仍可执行

### Requirement: Foundation E2E 使用隔离且可清理的真实本地拓扑
系统 SHALL 通过 gateway、API、PostgreSQL + pgvector、Redis 和 Worker 的真实本地运行单元执行 foundation probe E2E，并 SHALL 在成功或失败后清理隔离测试状态。

#### Scenario: 完整 probe 链路成功
- **WHEN** E2E harness 以小程序请求等价客户端创建并轮询 foundation probe
- **THEN** 请求经过 gateway、API、PostgreSQL、Redis、Worker 和 pgvector 后返回 SUCCEEDED 与非敏感摘要

#### Scenario: E2E 环境自动清理
- **WHEN** 完整验证成功、失败或被测试 harness 正常终止
- **THEN** 隔离容器、网络、测试卷和测试数据被清理且不会污染 development 环境

### Requirement: CI 只编排统一验证入口
系统 SHALL 使未来 CI 平台只负责准备前置环境并调用根级统一验证入口，且 MUST NOT 在托管 workflow 中复制验证逻辑。

#### Scenario: 更换 CI 托管平台
- **WHEN** 项目选择或更换 CI 托管平台
- **THEN** 平台调用同一根级验证命令且本地与 CI 的验收阶段保持一致

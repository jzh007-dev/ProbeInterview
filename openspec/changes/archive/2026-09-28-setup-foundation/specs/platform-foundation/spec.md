# Spec Delta

## Purpose

定义 ProbeInterview 后续 foundation changes 共同依赖的可复现工程骨架与运行配置契约，使 backend、小程序和环境配置能在进入运行拓扑与业务无关 probe 实现前被独立验证。

## ADDED Requirements

### Requirement: 工程骨架可以从锁定依赖复现
系统 SHALL 提供 backend、小程序、Compose 目录和根级脚本的 monorepo 骨架，并 SHALL 通过锁文件使受支持环境能够重复安装和执行基础检查。

#### Scenario: 全新环境安装工程依赖
- **WHEN** 开发者在满足文档前置条件的全新环境按锁文件安装 backend 与小程序依赖
- **THEN** 安装成功，backend 包可以导入且小程序类型检查可以执行

#### Scenario: 工程边界保持最小
- **WHEN** 开发者检查初始目录与模块结构
- **THEN** 系统包含明确的 platform/foundation 与独立 API、Worker 入口，但不包含知识、卡片、面试或复盘领域实现

### Requirement: 运行配置按环境进行安全校验
系统 SHALL 为 development、test 和 production 提供类型化配置 schema，并 MUST 在启动前拒绝缺失必填项或违反环境安全边界的配置。

#### Scenario: 缺少环境必填配置
- **WHEN** 某运行环境缺少该 profile 的必填配置
- **THEN** 启动校验明确失败并标识无效配置字段

#### Scenario: production 启用验证捷径
- **WHEN** production 配置启用 local actor、fake adapter fallback 或 foundation probe
- **THEN** 启动校验拒绝该配置

#### Scenario: 本地配置不要求真实云密钥
- **WHEN** development 或 test 使用允许的本地配置且未提供真实 OSS 或百炼凭证
- **THEN** 配置校验成功且不把 fake adapter 声明为 production 降级实现

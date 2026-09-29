# Spec Delta

## Purpose

定义小程序、HTTP API、异步消息和 Worker 之间厂商无关的追踪上下文与遥测契约，使一次用户操作可以跨运行单元关联，并可在不改变业务代码的情况下接入兼容 OpenTelemetry 的监控平台。

## ADDED Requirements

### Requirement: 客户端与 HTTP API 使用标准追踪上下文
系统 SHALL 使用标准 trace context 关联小程序用户动作与 HTTP 请求，SHALL 为每次请求保留独立 request ID，并 MUST 在上下文缺失或无效时安全创建新的 trace。

#### Scenario: 客户端发送合法 trace context
- **WHEN** 小程序请求携带合法 trace context 和 client action ID
- **THEN** API 继续同一 trace、创建新的服务端 span，并在响应与安全日志中返回可关联的 request ID 和 trace 信息

#### Scenario: 客户端未发送 trace context
- **WHEN** 客户端请求没有携带 trace context
- **THEN** API 创建新的 trace 和服务端 span，同时生成或保留独立 request ID

#### Scenario: 客户端发送无效 trace context
- **WHEN** 客户端请求携带格式无效或禁止接受的 trace context
- **THEN** API 忽略该上下文并创建新的合法 trace，且请求处理不会因追踪输入无效而失败

#### Scenario: 小程序请求失败
- **WHEN** 小程序请求发生网络失败或收到错误响应
- **THEN** 客户端保留 client action ID、请求尝试和已获得的安全关联标识，但不记录请求正文或页面私人输入

### Requirement: 异步消息延续追踪因果关系
系统 SHALL 在 Celery 消息 header 中传播 trace context，并 SHALL 使 Worker 消费、重试和最终结果事件能够关联原始生产者，同时 MUST NOT 把私人业务内容加入追踪 header。

#### Scenario: API 投递后台任务
- **WHEN** API 在有效 trace 内投递只携带稳定任务 ID 的 Celery 消息
- **THEN** producer 将 trace context 注入消息 header，Worker 提取上下文并创建与生产者相关联的消费 span

#### Scenario: Worker 收到缺失或无效的 trace context
- **WHEN** Worker 收到的消息没有合法 trace context
- **THEN** Worker 创建新的 trace、保留稳定 job ID 并继续安全执行任务

#### Scenario: 后台任务发生重试
- **WHEN** 同一 job 因重试再次执行
- **THEN** 每次尝试具有可区分的执行 span，并通过 job ID 和 trace 关系关联到原始后台操作

### Requirement: 遥测字段具有稳定且可移植的语义
系统 SHALL 使用标准 trace、span、resource 和日志关联字段，SHALL 为自定义字段使用 `probeinterview.*` 命名空间，并 MUST 避免在 span 名称中包含高基数资源 ID 或私人内容。

#### Scenario: API 与 Worker 产生遥测
- **WHEN** API 或 Worker 产生 span 或结构化日志
- **THEN** 遥测包含适用的 trace ID、span ID、trace flags、service namespace、service name、service version 和 deployment environment

#### Scenario: 记录项目自定义属性
- **WHEN** 标准语义约定没有对应的项目属性
- **THEN** 系统使用版本化的 `probeinterview.*` 属性名称并记录安全摘要或稳定引用，而不是私人正文

#### Scenario: 语义约定版本发生变化
- **WHEN** 项目升级使用的 OpenTelemetry 语义约定版本
- **THEN** 兼容映射在 infrastructure 边界集中更新且业务模块不依赖厂商或版本特有字段

### Requirement: 追踪导出是可选且不影响业务正确性
系统 SHALL 允许通过 infrastructure 配置启用标准 OTLP 导出，并 MUST 在未配置或导出失败时保持业务请求和后台任务的正确执行。

#### Scenario: 未配置遥测导出
- **WHEN** development 或 test 环境没有配置 OTLP endpoint
- **THEN** trace context、日志关联和自动化测试仍然工作且不要求云监控凭证

#### Scenario: 遥测后端暂时不可用
- **WHEN** 已配置的 OTLP endpoint 超时或拒绝导出
- **THEN** 系统以有界方式丢弃或缓冲遥测并报告安全诊断事件，且不阻塞业务请求或 Worker 执行

#### Scenario: 更换兼容的监控平台
- **WHEN** 运维更换兼容 OTLP 的云监控或自托管平台
- **THEN** 应用通过修改 infrastructure exporter 配置完成迁移且业务模块与传播契约保持不变

### Requirement: 通用 Trace 不预定义 Agent 执行语义
系统 SHALL 允许未来 Agent runtime 复用标准 trace context，但 MUST NOT 在 Agent 尚未设计时固化 Agent run、step、tool、model、Prompt 或评估字段。

#### Scenario: 后续 Agent change 使用追踪基础
- **WHEN** 后续 change 实现 Agent runtime 与语义追踪
- **THEN** 该 change 复用既有 trace context 和 exporter 边界，并独立定义 Agent 运行、步骤、工具和模型语义

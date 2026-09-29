# Spec Delta

## MODIFIED Requirements

### Requirement: API 响应携带可追踪请求标识
系统 SHALL 为每个 API 请求接受或生成唯一 request ID，SHALL 独立接受或创建合法的标准 trace context，并 SHALL 在成功响应、错误响应和结构化日志中保留可安全关联的标识。

#### Scenario: 客户端未提供 request ID
- **WHEN** 客户端发起请求但未提供 request ID
- **THEN** 系统生成 request ID 并在响应中返回，且 request ID 不替代 trace ID

#### Scenario: 客户端提供合法 request ID
- **WHEN** 客户端发起请求并提供合法 request ID
- **THEN** 系统在响应与该请求的结构化日志中返回并保留同一 request ID

#### Scenario: 客户端提供合法 trace context
- **WHEN** 客户端请求携带合法的标准 trace context
- **THEN** 系统继续该 trace、创建新的服务端 span，并在响应与日志中提供安全关联信息

#### Scenario: 客户端未提供或提供无效 trace context
- **WHEN** 客户端没有提供 trace context 或提供的上下文无效
- **THEN** 系统创建新的合法 trace 且正常处理请求

### Requirement: 运行日志结构化且不包含私密内容
系统 SHALL 输出与标准 trace/span context 关联的结构化日志，SHALL 包含适用的 request ID、trace ID、span ID、trace flags、job ID 和服务资源标识，并 MUST NOT 在正常日志或追踪属性中记录请求正文、私人来源文本、完整 Prompt 或模型响应、密钥、令牌和连接串。

#### Scenario: 请求与运行单元产生日志
- **WHEN** 小程序请求、API 或 Worker 记录一次正常运行事件
- **THEN** 日志包含适用的 request、trace、span、job 和服务资源标识以及低基数安全事件摘要

#### Scenario: 日志与 span 相关联
- **WHEN** 运行事件发生在活动 span 内
- **THEN** 结构化日志使用标准格式记录同一 trace ID、span ID 和 trace flags

#### Scenario: 敏感值出现在异常上下文
- **WHEN** 异常上下文包含请求正文、私人文本、Prompt、模型响应、密钥、令牌或连接信息
- **THEN** 结构化日志和追踪属性排除或脱敏敏感值且仍保留可排障的稳定错误摘要

#### Scenario: 追踪系统不可用
- **WHEN** trace exporter 未配置或暂时不可用
- **THEN** 结构化日志、request ID 和业务执行继续工作且不会因遥测失败而失败

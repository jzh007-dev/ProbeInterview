# Proposal

## Why

当前项目还没有真实 Celery 业务任务或已选定的监控平台。单独建设分布式
trace foundation 会先引入依赖、采样和隐私决策，却没有当前 MVP 需要消费的
可观察行为。

## What Changes

- 通过正常 Git revert 撤销本分支过早引入的 OpenTelemetry 规划、依赖和实现，
  保留完整提交历史。
- 继续使用 main 已有的 `X-Request-ID`、Problem Details 和安全结构化日志，不改变
  当前运行时行为。
- 不在当前 change 引入 OpenTelemetry、OTLP、Collector、W3C Trace Context、
  客户端 tracing、生产采样或 exporter 脱敏。
- 当首个真实 Celery 业务任务出现时，由对应纵向 change 按实际工作流增加
  `job_id` 与 request correlation。
- 当项目选定真实监控平台并需要跨运行单元 trace 时，再以独立 change 评估官方
  OpenTelemetry SDK、Collector、采样和隐私边界。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。该回退不改变 main 已有的行为契约，因此 change 设置 `skip_specs: true`。

## Impact

- 分支运行代码、依赖、架构文档和项目配置恢复为 main 基线。
- 不增加或修改 API、Celery 消息、日志字段、部署组件或第三方依赖。
- 本 change 只保留回退证据和延期触发条件，不产生后续实现任务。

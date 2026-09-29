# Design

## Context

动机见 `proposal.md`。main 已提供 `X-Request-ID`、RFC 9457 Problem Details、
安全结构化日志，以及可选的 request/trace/job 日志上下文槽位。当前 Celery
只有 Worker 和 broker 基础设施，还没有需要跨 HTTP 与 Worker 关联的真实业务任务；
项目也没有选定 trace 后端或 Collector。

本 change 遵循 `docs/architecture.md`、ADR 0003、ADR 0004 和 ADR 0005。由于最终运行行为
与 main 相同，没有 capability delta，specs 按 OpenSpec 规则跳过。

## Goals / Non-Goals

**Goals:**

- 通过正常 Git revert 撤销过早的 tracing 规划、依赖和实现，并保留历史。
- 保持 main 已有的 Request ID、结构化日志和安全边界不变。
- 固定未来重新讨论跨运行单元 correlation 与可观测平台的触发条件。

**Non-Goals:**

- 不实现 W3C Trace Context、OpenTelemetry、OTLP、Collector 或客户端 tracing。
- 不提前设计 sampling、exporter 脱敏、异常事件或 Celery retry span 拓扑。
- 不为尚不存在的业务任务增加通用消息 header 或 tracing abstraction。

## Decisions

### 1. 当前不建立分布式 tracing foundation

现有 Request ID 和结构化日志足以支持当前 HTTP foundation 的诊断。没有真实跨运行
单元业务链路时，新增 tracing SDK 只能验证 SDK 本身，不能验证产品需求。

因此本 change 不增加依赖、配置或运行时代码。此前分支提交通过 `git revert` 撤销，
而不是 reset 或改写历史。

### 2. Correlation 随首个真实 Celery 纵向功能交付

首个实际发布和消费 Celery 任务的 change 必须根据其持久化 job、重试和日志需求，
决定如何关联 request ID 与稳定 job ID。该决定与业务任务及其自动化场景一起交付，
不建立当前没有消费者的通用协议。

### 3. OpenTelemetry 随真实监控平台单独决策

当项目需要跨运行单元 trace 并已确定监控平台时，再建立独立 change。届时优先评估
官方 OpenTelemetry SDK 与 Collector，并同时确定数据出口、sampling、隐私过滤、
故障隔离和运维验证。

### 4. 不创建行为 spec delta

回退后的运行代码、API、日志和部署契约与 main 一致。`.openspec.yaml` 使用
`skip_specs: true`，避免为了保留一个 change 而发明没有行为差异的 requirement。

## Risks / Trade-offs

- [当前无法查看真正的跨进程 trace] → 在真实 Celery 业务 change 中先用稳定
  request/job correlation 满足诊断，再按实际需求决定 tracing。
- [未来接入监控时需要重新设计] → 将平台、采样和隐私作为同一个独立 change，
  避免现在做无使用证据的兼容层。
- [revert 历史增加提交数量] → 保留可审计的决策过程，且最终文件树与 main 基线一致。

## Migration Plan

1. 按时间逆序正常 revert 误提交的缩减规划和原四个 trace 提交。
2. 验证 backend、架构文档和项目配置与 main 基线一致，且无 OpenTelemetry/OTLP。
3. 运行现有 skeleton、backend 和 mini-program 验证命令。
4. 保留本 change 作为延期与回退记录，不进入 trace 功能实施。

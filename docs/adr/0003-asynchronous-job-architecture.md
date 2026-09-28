# ADR 0003: Asynchronous job architecture

## Status

Accepted

## Date

2026-09-28

## Context

知识文件解析、Embedding、知识关联、卡片生成和未来的面试报告都可能超过普通 HTTP 请求的稳定处理时间，并需要重试、进度查询和失败恢复。`setup-foundation` 需要用最小链路证明后台任务运行方式，但不能演变成通用工作流平台。

队列通常采用至少一次投递，消息可能重复。API 提交数据库事务后也可能在投递消息前失败，因此仅依赖队列消息不能作为任务状态真相。

## Decision

后台任务使用 Redis 作为 Celery broker，并由独立 Celery Worker 处理。PostgreSQL 是任务状态、输入引用、尝试次数和安全结果的唯一真相；Redis 不保存最终业务状态。

队列消息只携带稳定任务 ID 和必要的路由信息，不携带完整上传内容、Prompt、知识正文或可变业务快照。Worker 根据任务 ID 从 PostgreSQL 重新读取经过权限和版本约束的输入。

任务必须按照至少一次投递设计：

- API 在数据库事务中创建或复用任务记录；
- 数据库提交成功后再投递消息；
- Worker 锁定任务并检查终态后再执行；
- 每个产生副作用的步骤必须可幂等重试；
- 相同任务的重复消息不得创建重复最终结果；
- 最终失败写入稳定错误码和安全摘要，内部异常不得直接返回客户端。

MVP 不实现完整 transactional outbox。若提交成功但消息投递失败，任务保留为 `QUEUED`，由显式恢复命令重新投递超过阈值且尚未进入终态的任务。需要更强投递保证时，再通过独立 ADR 引入 outbox。

## Alternatives

### Execute long work inside HTTP requests

实现简单，但会受到请求超时、客户端断线和进程重启影响，也无法稳定提供重试和进度查询。

### PostgreSQL polling worker without Redis

可以减少一个运行组件，但需要自行实现调度、退避、并发领取和队列运维能力。当前已有多类未来后台任务，Celery 的成熟任务模型更合适。

### Dramatiq

Dramatiq 的概念更轻，但项目没有需要通过更换 Celery 来解决的明确问题，选择它不会消除幂等和数据库真相设计。

### Full transactional outbox from the beginning

可以增强投递可靠性，但会扩大 foundation 的表、调度器和清理职责。MVP 的可恢复 `QUEUED` 状态已经覆盖主要空窗。

## Consequences

- Docker Compose 至少需要 Redis、API 和 Worker 三个相关运行单元。
- 所有后台功能必须先持久化任务，再投递任务 ID。
- 业务代码不能把 Redis 或 Celery result backend 当作产品状态来源。
- 测试必须覆盖重复消息、有限重试、终态幂等和投递空窗恢复。
- 若未来出现多步骤长流程、补偿事务或严格投递要求，应新增 ADR，而不是继续扩充单个 Celery task。


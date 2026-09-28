# Tasks

依赖：`establish-persistence-actor-isolation` 已完成并归档。原 `setup-foundation` 任务 3.1–3.4 映射到本 change。

## 1. 交付 Probe 工作流与客户端诊断

- [ ] 1.1 定义 `ObjectStorage`、`EmbeddingProvider`、`StructuredLlmClient` 端口及确定性 fake adapter，增加 adapter 契约测试和日志脱敏测试，验证本地与测试运行不需要真实 OSS 或百炼凭证
- [ ] 1.2 实现 `POST /api/v1/foundation/probes` 与 `GET /api/v1/foundation/probes/{id}`，包括 HTTP 202、`Location` 状态地址、类型化任务资源、幂等键和 input hash 冲突处理；以 API/数据库测试验证重复相同命令复用原任务、不同输入返回 RFC 9457 格式的 409
- [ ] 1.3 实现只接收 probe ID 的 Celery 任务、状态锁定、fake 存储往返、fake embedding、owner-scoped pgvector 查询、有限重试和超时 QUEUED 恢复命令，并以重复投递、中断恢复、最终失败和单一结果测试验证幂等性
- [ ] 1.4 创建仅开发构建可见的小程序诊断页，支持发起 probe、轮询 QUEUED/RUNNING/SUCCEEDED/FAILED 和展示安全摘要，并以 Jest + `miniprogram-simulate` 组件测试验证初始空态、加载/状态变化/成功/错误态、重复点击幂等及 production 构建不暴露入口

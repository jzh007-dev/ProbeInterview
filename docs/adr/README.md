# Architecture Decision Records

本目录记录 ProbeInterview 已确认的项目级架构决策。ADR 不与 OpenSpec change 一一对应：一个 change 可以引用多篇 ADR，一篇 ADR 也可以约束多个 change。

ADR 只追加、不静默改写。若未来推翻已接受的决策，应创建新的 ADR，并在新旧 ADR 中标明替代关系。

## Index

| ADR | Status | Decision | Primary consumers |
|---|---|---|---|
| [0001](0001-project-structure-and-technology-stack.md) | Accepted | Monorepo、模块化单体及基础技术栈 | `setup-foundation` 及全部后续 changes |
| [0002](0002-data-and-rag-foundation-boundary.md) | Accepted | PostgreSQL/OSS 为内容与版本真相，向量为可重建派生数据 | `setup-foundation`、知识导入、知识关联及检索 |
| [0003](0003-asynchronous-job-architecture.md) | Accepted | Redis + Celery 执行后台任务，PostgreSQL 保存任务真相 | `setup-foundation` 及后台处理 changes |
| [0004](0004-api-and-identity-boundary.md) | Accepted | HTTP API、幂等、错误格式及 `ActorContext` 边界 | `setup-foundation` 及全部 API changes |
| [0005](0005-deployment-and-runtime-operations.md) | Accepted | 单 ECS + Docker Compose + Caddy，以及配置和日志规范 | `setup-foundation` 及部署运行 |
| [0006](0006-external-adapters-and-verification-strategy.md) | Accepted | 外部服务端口、确定性 fake 及统一自动验证入口 | `setup-foundation` 及云服务接入 changes |
| [0007](0007-w3c-trace-context-and-opentelemetry.md) | Superseded | 原 W3C Trace Context、客户端 trace 延续和 OTLP 决策 | 被 ADR 0008 取代 |
| [0008](0008-server-owned-public-traces-and-deferred-export.md) | Accepted | 最小服务端 trace 与 API/Celery/Worker 内部传播 | `establish-trace-context-propagation` |

## Deliberately deferred decisions

以下决策不阻塞 `setup-foundation`，应由首次使用它们的知识库 change 在实现前单独讨论：

- XMind/Markdown 的解析与语义切片策略；
- Embedding 模型、向量维度、距离函数和 pgvector 索引类型；
- 全文、向量和结构化候选的混合召回权重；
- LLM 知识关联的候选阈值、置信度和人工复核策略；
- Rerank 模型及进入模拟面试题库的质量门槛；
- 托管 CI 平台；无论平台如何选择，都必须调用统一的根级验证入口。

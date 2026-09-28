# ADR 0002: Data and RAG foundation boundary

## Status

Accepted

## Date

2026-09-28

## Context

ProbeInterview 的知识库同时包含个人知识与公共知识，未来会为知识卡片、模拟面试出题和回答评估提供召回。上传文档可能更新，公共知识与个人知识也可能冲突。如果向量库成为唯一真相，系统将难以解释知识来源、撤销旧版本或重新生成 Embedding。

`setup-foundation` 需要证明 PostgreSQL、pgvector 和 owner 隔离可以工作，但此时尚未选择 Embedding 模型、向量维度、切片策略、距离函数和索引类型。过早创建正式知识向量表会把后续知识导入和关联设计锁定在未经验证的假设上。

## Decision

PostgreSQL 保存结构化业务状态、来源元数据、版本关系、权限范围和处理状态。原始上传文件由对象存储保存，PostgreSQL 保存其对象引用、内容摘要和版本记录。对象存储中的文件和 PostgreSQL 中的版本记录共同构成可追溯的来源真相。

pgvector 中的 Embedding 是可重新生成的派生数据，不是知识内容或任务状态的唯一真相。未来的业务向量必须能够追溯到：

- 来源及来源版本；
- 被切分内容的版本；
- Embedding provider、模型和模型版本；
- 生成时间及当前是否有效。

召回只能使用当前可见范围内仍然有效的版本。文档更新时，新版本完成解析和向量生成后才能切换为有效版本；旧向量退出正常召回，但保留必要的审计关联或按保留策略清理。具体表结构由知识导入与知识关联 change 确定。

公共知识与个人知识使用统一的知识结构和检索链路，通过来源范围、owner 和能力进行区分。个人上传但公共库不存在的知识可以独立存在；是否与已有知识关联由后续知识关联流程决定。

`setup-foundation` 只负责：

- 启用 PostgreSQL 的 pgvector 扩展；
- 建立与真实知识模型隔离的固定向量 probe；
- 验证迁移、事务、owner 前置过滤及基本距离查询；
- 定义可替换的 Embedding provider 端口。

下列内容有意延期到首次使用它们的 change：

- 业务 chunk 与知识概念表；
- Embedding 模型、维度和批处理策略；
- 距离函数及 HNSW、IVFFlat 等索引选择；
- 语义、全文和结构化候选的混合召回；
- Rerank、LLM 关联阈值和人工复核。

## Alternatives

### Treat the vector store as the source of truth

实现路径更短，但无法可靠支持来源审计、版本切换、权限删除、模型升级和重新向量化。

### Design the final vector schema in setup

可以提前建立表和索引，但当前缺少模型维度、数据规模和召回质量证据，容易产生昂贵迁移。

### Separate vector database immediately

专用向量数据库可能在大规模检索时更有优势，但 MVP 使用 PostgreSQL 已能同时提供事务、权限过滤和向量能力，单独服务会增加运维与一致性成本。

## Consequences

- 文档更新和模型升级可以通过生成新派生版本完成，不需要覆盖旧向量。
- 后续召回必须先执行 owner/公共范围过滤，再做相似度查询，不能召回后再过滤权限。
- `setup-foundation` 的 probe 表不得演变为真实知识向量表。
- 后续 Agent 可以通过稳定的来源、版本和 provider 端口使用 RAG，而不依赖某个固定模型或索引。
- 数据版本字段和切换流程会增加知识导入实现量，但这是避免过期引用和支持增量更新的必要成本。


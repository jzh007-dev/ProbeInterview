# Knowledge Upload MVP Overview

更新时间：2026-09-29

## 1. 文档定位

本文记录 ProbeInterview 知识上传、知识关联和首页主题展示 MVP 的产品设想与 change 拆分共识。它用于解释整体方向和依赖，不替代 OpenSpec proposal、spec、design 或 tasks；每个 change 的可验收范围仍以对应 OpenSpec artifacts 为准。

本阶段的目标是先交付可信、可工作的最小闭环，不建设完整知识卡片、模拟面试、通用管理后台或完整可观察性平台。

## 2. MVP 用户结果

MVP 完成后：

- 用户可在微信小程序上传小于 500 KiB 的 UTF-8 Markdown 知识资料。
- 知识资料分为 `PUBLIC` 和 `PRIVATE`：
  - 公共知识在审核发布后对所有用户可见；
  - 私人知识只对 owner 可见。
- 普通用户默认每天最多提交 2 个文件；当前种子用户拥有配额豁免能力。
- 当前种子用户同时拥有公共知识提交、公共知识审核、知识目录管理和上传配额豁免能力。
- 系统异步解析 Markdown，根据六个技术主题和当前目标岗位关联已有知识点，或提出新的知识点。
- 公共新知识点必须经 reviewer 确认；经过持续评测校准后，关联到已有知识点的高置信度公共内容可以自动发布。
- 首页“按主题学习”最终读取当前用户可见、与默认 `target_role` 相关的真实知识点；首页其他训练、复盘和继续学习指标在本阶段仍可使用明确的 fake 数据。

私人题库、知识卡片生成、学习进度、模拟面试和面试报告不属于本 MVP。

## 3. 页面范围

### 3.1 首页

首页遵循 `docs/design/visuals/home-knowledge-categories.html`：

- 问候中的昵称来自 `/api/v1/me/overview`。
- 初始 change 中，本周训练、待复盘、继续学习和主题分类使用小程序内确定性 fake 数据。
- 最终 change 只把“按主题学习”替换为真实知识库数据。
- 搜索、继续学习和主题详情在尚未有对应能力时只保留明确的无副作用交互边界。

### 3.2 上传与管理

上传页遵循 `docs/design/visuals/home-overview.html` 的“上传与管理”方向，但只保留“知识资料”，不提供“私人题库”。

首版管理范围：

- 选择 Markdown 文件；
- 选择公共或私人知识，默认私人；
- 提交上传；
- 查看自己的上传记录、处理状态和失败摘要；
- reviewer 条件可见地查看公共知识审核队列。

删除、替换、修改 scope 和完整历史版本管理不在首版。

## 4. 身份、能力与配额

应用层继续使用 `ActorContext(actor_id, capabilities)`。能力至少包括：

- `knowledge.submit_public`
- `knowledge.review_public`
- `knowledge.manage_taxonomy`
- `knowledge.upload_quota_exempt`

当前种子用户拥有全部能力。未来微信登录注册只负责把新账号映射到相同的 `ActorContext`；普通新用户默认没有上述管理能力，并受每天 2 个文件的上传限制。

每日配额按 `Asia/Shanghai` 自然日计算，时间戳仍以 UTC 持久化。同步格式校验失败不计数；一旦文件被系统接受并进入异步处理，即使后续内容无关或处理失败，也计入当日配额。幂等重试不重复计数。

## 5. 来源、权限与版本真相

公共和私人知识使用统一结构，通过 scope、owner 和 capability 区分，不建立两套互不兼容的知识模型。

```text
KnowledgeSource
  |
  +--> SourceVersion
          |
          +--> ParsedSection
                  |
                  +--> ConceptRelation
                          |
                          +--> KnowledgeConcept
                                  |
                                  +--> ConceptRoleMapping
```

建议核心字段：

- `KnowledgeSource`: creator、owner、scope、当前版本引用；
- `SourceVersion`: 文件摘要、OSS object key、处理状态、发布状态；
- `ParsedSection`: Markdown 标题路径、顺序、正文引用和内容版本；
- `KnowledgeConcept`: 稳定 ID、主题、scope、owner、状态和版本；
- `ConceptRelation`: 来源章节与知识点之间的相同、互补、冲突或无关关系；
- `ConceptRoleMapping`: 知识点与稳定岗位之间的 `CORE`、`RELATED` 或 `OPTIONAL` 关系。

任何数据库或向量查询必须先应用：

```text
scope = PUBLIC
OR
(scope = PRIVATE AND owner_user_id = current_actor)
```

## 6. 上传与存储

同步 API 只做确定性校验，不在 HTTP 请求中调用 LLM：

- actor 和公共上传 capability；
- `.md` 文件名；
- 文件严格小于 `500 * 1024` bytes；
- UTF-8、非空、无 NUL 或明显二进制内容；
- 基础 Markdown 可解析；
- 不接受原始 HTML、图片或附件内容；
- scope 枚举；
- SHA-256 和幂等输入摘要。

小文件通过 FastAPI 有上限地读取并写入 OSS。PostgreSQL 只保存元数据、对象引用和状态，不保存完整 Markdown。测试使用与真实端口一致的确定性 fake storage。

保留策略：

- `ACTIVE` 来源保留原始 Markdown，支持重新解析、重新 Embedding 和来源追踪；
- 临时处理失败保留对象以便重试；
- 永久失败或内容无关的对象在 7 天后清理，但保留安全元数据和状态；
- 同一用户、相同 scope 和相同 SHA-256 不重复处理；
- 普通用户最多保留 100 个有效来源，原始文件总预算约 50 MiB。

## 7. 处理与发布状态

技术处理和产品发布使用独立状态，避免把“需要人做决定”当成失败。

```text
processing_status:
QUEUED -> PARSING -> ANALYZING -> ASSOCIATING -> SUCCEEDED
                                              \-> FAILED

publication_status:
DRAFT -> REVIEW_REQUIRED -> ACTIVE -> ARCHIVED
   \-----------------------> REJECTED
```

产品状态映射：

- `QUEUED`、`PARSING`、`ANALYZING`、`ASSOCIATING`：处理中；
- `REVIEW_REQUIRED`：待确认；
- `ACTIVE`：私人知识处理完成，或公共知识已发布；
- `REJECTED`：内容不适合进入知识库；
- `FAILED`：技术处理失败，可按策略重试。

## 8. 主题、岗位和知识点

初始只建立六个主题，不预置业务知识点：

1. Agent 系统
2. RAG
3. Prompt 与上下文
4. 模型应用
5. 评测与可靠性
6. 工程化

所有具体知识点来自当前用户上传的 Markdown。

默认目标画像的 `target_role` 需要映射到稳定 `role_profile`。知识点与岗位使用关系表作为业务真相，向量相似度只用于提出候选关系。一个知识点可以映射多个岗位，并记录相关级别、来源、审核状态和版本。

模拟面试阶段将先按 actor 可见范围和 ACTIVE 岗位映射过滤，再进行向量召回，并保存实际使用的知识点、内容、映射和模型版本快照。

## 9. 受控 Agentic RAG

MVP 使用受控工作流，不允许 LLM 直接发布或任意修改知识库：

```text
读取指定 SourceVersion
  -> 确定性解析标题与章节
  -> 提取知识点候选
  -> 在可见范围内检索已有知识点
  -> 判断相同、互补、冲突或无关
  -> 提议关联或新知识点
  -> 服务端权限与 schema 校验
  -> 自动接受或进入 REVIEW_REQUIRED
```

Agent 只能操作稳定 ID，不能绕过 scope、owner、状态机、费用预算或人工审核。上传 Markdown 始终被视为不可信数据，不能通过 Prompt Injection 控制工具、权限、发布或删除操作。

首版检索采用：

- 唯一名称和别名匹配；
- pgvector 精确相似度召回；
- 结构化 LLM 关系判断。

Rerank、HNSW、IVFFlat、复杂混合权重和多 Agent 在评测或数据规模证明需要前不实现。

## 10. 新知识点与人工审核

找不到可靠已有知识点时，LLM 可以提出新知识点，但不能直接发布公共知识点。

- 无关内容标记为排除；
- 私人新知识点在高置信度且经过校准后可以自动激活，否则由 owner 确认；
- 公共新知识点必须由 `knowledge.review_public` reviewer 确认；
- 当前阶段的 reviewer 是当前种子用户本人，但提交和审核 capability 保持分离。

审核动作包括：

- 接受推荐关联；
- 选择其他知识点；
- 批准创建新知识点；
- 标记与岗位无关；
- 保留为冲突内容；
- 拒绝章节。

上传页为 reviewer 增加条件可见的“公共知识审核”和后续“RAG 质量”入口，不引入新的 Web 管理端技术栈。

## 11. 最小质量闭环

MVP 不建设完整 Observability 平台，但不能省略判断系统是否改善所需的数据。

关联 change 从第一天保存：

- run、job、source/version、section 和 candidate ID；
- Prompt、LLM、Embedding 和规则版本；
- 候选分数、关系提议和安全理由摘要；
- token、费用、耗时、重试和终态；
- 人工最终决定。

最小 Eval 覆盖相同、改写、互补、冲突、无关、新知识点、跨岗位不相关和公共/私人隔离。人工修改或拒绝的决策自动成为 badcase 和后续回归样本。

公共已有知识点的自动发布需要先经历离线评测和全部人工审核的 shadow 阶段。只有 confidence 分桶的实际审核成功率经过足够样本校准后，才可启用高置信度自动发布；质量下降时退回 `REVIEW_REQUIRED`。

后续管理员可视化页面展示自动关联准确率、人工修改率、未匹配率、处理成功率、confidence 校准、模型/Prompt 版本对比、成本、延迟和 badcase。

## 12. Change 路线

本 MVP 按以下独立 changes 交付，每个 change 原则上不超过 6 个纵向 tasks：

1. `deliver-home-knowledge-overview`
2. `ingest-markdown-knowledge-sources`
3. `establish-role-knowledge-topics`
4. `parse-markdown-knowledge-sources`
5. `associate-or-propose-knowledge-concepts`
6. `review-and-publish-public-knowledge`
7. `observe-rag-quality`
8. `serve-role-aware-home-topics`

知识卡片生成、学习进度、知识详情搜索、模拟面试召回和面试快照在本路线之后另行拆分。

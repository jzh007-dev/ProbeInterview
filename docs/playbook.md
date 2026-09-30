# ProbeInterview 开发流程（从头开始版）

> **已被取代（2026-10-01）**：阶段 1–2（架构基线、OpenSpec 拆分）已完成并冻结；
> 阶段 3 的逐 change 流程由 `docs/workflow.md` 取代。本文件仅作历史参考。

## 总览

| 阶段 | 做什么 | 会话数 | 产出 | 需要你做的决定 |
|---|---|---|---|---|
| 1. 架构基线 | 把你的设计整理成 agent 能读的文档 | 1 | architecture.md、ADR、ui-baseline.md、config.yaml、AGENTS.md | 逐条决定：未定的技术选型、设计与需求的冲突 |
| 2. 拆分 change | 把一个大 change 拆成 foundation 加若干功能 change | 1 | 若干 change、roadmap.md | 确认拆分方案 |
| 3. 逐个实现 | 按 roadmap 的顺序，每个 change 走一遍同样的流程 | 每个 change 1 个 | 代码，以及归档后的 spec | 设计讨论；是否批准偏离原计划 |

## 保留什么、丢弃什么

- **保留**：
  - OpenSpec 里的需求内容：proposal.md、specs/
  - 你的设计：docs/design/visuals/
- **丢弃**：
  - 旧分支 `codex/deliver-probeinterview-mvp` 的代码。那是 agent 自己选的 Node/TS 栈。阶段 2 只从它的测试里提取边界用例，等 setup-foundation 完成后，由你亲手删除这个分支。
  - 原 design.md 里被你的设计取代的部分。

## 文档各管什么

| 文档 | 回答什么 | 什么时候改 |
|---|---|---|
| `docs/architecture.md` | 系统整体长什么样：组件、边界、数据流、部署、横切关注点 | ADR 有变化时同步更新，始终反映当前状态 |
| `docs/adr/*.md` | 某个决定为什么这么选、放弃了哪些方案 | 只追加，不修改；推翻时写一篇新 ADR，把旧的标为 Superseded |
| `docs/design/ui-baseline.md` | UI 方向、设计 token、导航、通用组件 | UI 基线变化时更新 |
| `openspec/config.yaml` | 给 OpenSpec 用的结论摘要和准入规则 | 跟着 architecture.md 一起更新 |
| `AGENTS.md` / `CLAUDE.md` | 每次会话都会自动加载的项目规则 | 规则变化时更新 |
| `openspec/changes/<name>/` | 单个功能的需求、设计、任务 | 每个 change 一次 |
| `docs/roadmap.md` | change 的顺序、依赖、状态 | 每个 change 归档时更新 |

---

## 阶段 1：架构基线

```
工作目录：/Users/baobao/Documents/program/ProbeInterview（main 分支）。本次只写文档，不写业务代码。

背景：
- 需求在 OpenSpec change deliver-probeinterview-mvp 里（proposal.md、specs/、design.md、tasks.md）。需求内容保留。design.md 只有逻辑架构，技术栈写的是"尚未选定"。
- 我自己做的技术设计和 UI 设计在 docs/design/visuals/（HTML 文件和 README.md）。它是技术基线和 UI 基线的唯一依据。
- 旧分支 codex/deliver-probeinterview-mvp（worktree 在 .worktrees/deliver-probeinterview-mvp）里的 Node/TypeScript 代码，是之前的 agent 自己选的栈，我不要。它不能作为任何决策的依据。本次不要读它，也不要动它。

步骤：
0. 在 main 上提交 docs/design/ 和 docs/playbook.md。message："docs: add design visuals and playbook"。

1. 阅读：
   - docs/design/visuals/ 下的全部文件
   - openspec/changes/deliver-probeinterview-mvp/ 下的 proposal.md、design.md、specs/

2. 先不写文件。输出以下三张表，然后停下，等我逐条决定。

   表 A｜已确定的决策
   - 列：主题 | 结论 | 出处（文件名 + 区块标题）
   - 只收录 visuals 里明确写定的内容

   表 B｜未确定的决策
   - 收录两类：
     · visuals 里标了"尚待确认""pending""still require confirmation"的项
     · 落地必须做、但设计里没提到的项。例如：Python 包管理与目录结构、ORM 与迁移工具、测试框架、小程序语言（JS 还是 TS）与 UI 组件方案、本地开发环境、CI、日志与配置管理
   - 每项给出 2–3 个选项，写明各自的取舍，并标明它会卡住哪块功能
   - 只列选项，不替我选

   表 C｜设计与需求的冲突
   - 收录 visuals 和 proposal / specs / design.md 对不上的地方。例如：visuals 里有 pgvector、Embedding、Rerank、多知识库 RAG，而 design.md 的 Non-Goals 写着"不实现向量语义检索"
   - 每条附上两边的原文，并说明：如果以设计为准，需要改哪几条 spec

3. 我决定之后，写以下文件：

   a. docs/architecture.md：给 agent 读的总架构文档，共 7 节。
      1. 系统上下文：用户、小程序、后端、外部服务之间的关系
      2. 容器与部署：每个运行单元的职责、技术栈、通信方式，以及部署拓扑
      3. 后端模块划分：各领域模块的职责、边界、依赖方向，以及哪些模块之间禁止直接调用
      4. 核心数据流：一场面试从配置、出题、语音回答、转写、评分到生成短板复盘的完整时序
      5. 横切关注点：身份与 owner 隔离、版本与不可变快照、Trace、LLM 输出的结构化校验、隐私数据删除
      6. 质量属性与取舍：成本、可用性、延迟、可追溯性各自的目标，以及刻意放弃了什么
      7. 演进点：以后可能拆分或替换的位置，以及什么情况下触发
      写作要求：
      - 图用 Mermaid
      - 每一节都链接对应的 ADR
      - 未决定的项标为 Open
      - 和 visuals 不一致的地方，以我在表 C 里的决定为准
      - 只写结论，理由放进 ADR

   b. docs/adr/NNNN-<kebab-title>.md：表 A 的每一项、表 B 中已经决定的每一项，各写一篇 ADR。
      - 格式：标题、状态（Accepted / Proposed）、日期、背景、决策、备选方案、后果
      - 另写 docs/adr/README.md 作为索引

   c. docs/design/ui-baseline.md：从 UI 相关的 visuals 里提取，给 agent 用的 UI 基线。
      - 内容：设计方向；设计 token（颜色、字体、圆角、阴影、间距、模糊）；目标视口；导航结构；通用组件；每个页面对应哪个 visual 文件
      - 所有数值都从 HTML/CSS 里取，不许编

   d. docs/adr/pending-spec-updates.md：记录表 C 中我决定要改的需求条目。这一步只记录，不改 OpenSpec 文件。

   e. openspec/config.yaml，写入以下四部分：
      - context：技术栈、目录结构、构建与测试命令、编码约定，以及 architecture.md、ADR 索引、ui-baseline.md 的路径。只写结论，不超过 150 行。
      - rules.design：
        · 写明本功能用到的具体选型，禁止出现"待定""尚未选定"
        · 引用相关 ADR
        · 改动技术基线时，必须新增或替换 ADR
        · 有 UI 的功能：列出涉及的页面和状态（包括空态、错误态、加载态），并引用 ui-baseline.md 和对应的 visual
      - rules.tasks：
        · 按功能纵向切：每个任务交付一段从接口到存储都能端到端测试的行为，不按层横向切
        · 每个任务写明验证方式
      - operations.apply.guidance：
        · 只使用 architecture.md 和 ADR 中已确定的语言、框架、数据库、云服务和主要依赖
        · 需要引入任何未列出的技术时，先停下来问我，不得自行选择

   f. 仓库根目录的 AGENTS.md：每次会话都会自动加载的项目规则，包括：
      - 开始任何工作之前，先读 docs/architecture.md、docs/adr/README.md、docs/design/ui-baseline.md
      - OpenSpec 是需求和功能设计的唯一真相源。代码必须和 spec 保持一致；需要改需求或设计时，先停下来问我
      - 只使用 architecture.md 和 ADR 中已确定的技术。需要任何新的语言、框架、数据库、云服务或主要依赖时，先停下来问我
      - 遇到新的架构决策：先和我讨论，再写新 ADR，然后同步更新 architecture.md 和 config.yaml 的 context
      - 构建和测试命令（现在还没有代码，先写"待 setup-foundation 建立"）
      另外创建 CLAUDE.md，内容只有一行 `@AGENTS.md`，让 Claude Code 读取同一份规则。

   g. 修改 docs/design/visuals/README.md：把末尾"尚未同步 OpenSpec"那一段，改成指向上面这些文件。

4. 运行 `openspec context --json`，确认 config 能正常解析，然后提交。

最后告诉我：写了哪些文件；还剩哪些 Open 项；每个 Open 项会卡住哪个功能。
```

## 阶段 2：拆分 change

```
工作目录：/Users/baobao/Documents/program/ProbeInterview（main 分支）。本次不写业务代码。

先读：openspec/config.yaml、docs/architecture.md、docs/adr/README.md、docs/adr/pending-spec-updates.md。

背景：
- openspec/changes/deliver-probeinterview-mvp 这一个 change 装了整个 MVP。
- 旧分支 codex/deliver-probeinterview-mvp 用了我不要的栈，实现了 tasks 的第 1–2 节。代码作废，但它的测试和修复提交里有值得保留的边界情况。
- 对旧分支只读：不修改、不合并、不删除。

目标：拆成 setup-foundation 加若干功能 change。全部基于 architecture.md 和 ADR 里的技术栈重新实现。

步骤：
1. 盘点基线：统计 7 个 spec 文件里 `### Requirement:` 和 `#### Scenario:` 的数量，作为后面对账的基线。

2. 从旧分支提取边界用例：
   - 读 `git log main..codex/deliver-probeinterview-mvp` 的提交，以及该分支上所有测试文件
   - 提取和编程语言无关的行为。例如：owner 越权访问、不可变快照、JD 图片保护、Trace 事件顺序、幂等删除
   - 输出一张表：行为 | 来源（提交或测试文件）| 现有 spec 里是否已有对应的 Scenario
   - 没有对应 Scenario 的行为，建议补成新的 Scenario

3. 先不动文件，输出拆分方案，然后停下等我确认。

   a. change 列表：每个 change 写名称、一句话范围、依赖哪些 change、对应原 tasks 的哪几节。参考拆法如下，可以调整，但要说明理由：
      - setup-foundation：原第 1–2 节，重做。定位为 walking skeleton：用一条最薄的链路，把 architecture.md 里的每个运行单元都串起来跑通一次
      - add-core-content-import：第 3 节
      - add-personal-learning-library：第 4 节
      - add-interview-configuration：第 5 节
      - add-ai-application-interview：第 6–7 节
      - add-interview-assessment：第 8 节
      - add-review-loop：第 9 节
      - add-offline-evaluation：第 10 节
      - 第 11 节：请建议是并入最后一个 change，还是单独做成一个 change

   b. Requirement 归属表：每条 Requirement 只能归到一个 change，包括第 2 步建议新增的 Scenario。

   c. 待改需求的落点：pending-spec-updates.md 里的每一条，落到哪个 change、具体怎么改。

   d. 原 design.md 的 12 条 Decision 怎么处理：
      - 已经写进 ADR 或 architecture.md 的：只引用，不复制
      - 只属于某个功能的：搬进那个功能 change 的 design.md

4. 我确认后执行：
   a. 把 deliver-probeinterview-mvp 目录改名为 setup-foundation，只保留属于它的内容。tasks 全部改回未勾选，并按 ADR 的技术栈重写。
   b. 其余每个 change：先用 `openspec new change <name>` 创建，再补齐 proposal / specs / design / tasks，遵守 config.yaml 里的 rules。spec 原文照搬；只有 pending-spec-updates.md 里我确认过的修改可以改动原文。
   c. 写 docs/roadmap.md：Mermaid 依赖图、执行顺序、每个 change 的状态。

5. 验证：
   - 对账：Requirement / Scenario 总数 = 基线 + 新增 − 我决定删除的，逐项核对
   - 每个 change 都通过 `openspec validate <name>`
   - 所有 change 里都搜不到"待定""尚未选定"
   - 所有 change 里不出现 ADR 以外的技术栈

6. 每个 change 单独一个 commit。

最后告诉我：最终的 change 列表和执行顺序、对账结果、所有偏离已确认方案的地方。
```

## 阶段 3：逐个实现（每个 change 用一次，先做 setup-foundation）

```
实现 OpenSpec change `<change-name>`。

分工：OpenSpec 管"做什么"和本功能的设计，是唯一的真相源；superpowers 只管"怎么执行"。不使用 openspec-apply-change。

1. 准入检查：阅读 openspec/config.yaml、docs/architecture.md、docs/adr/README.md、docs/design/ui-baseline.md、docs/roadmap.md，以及这个 change 的全部 artifacts。逐项确认：
   - 它依赖的 change 都已经归档
   - design.md 满足 config.yaml 里的 rules.design
   - 没有会阻塞这个 change 的 Open 项
   任意一项不满足：列出缺什么，然后停下。

2. 补设计（需要时才做）：
   - 用 superpowers 的 brainstorming 和我讨论
   - 结论只写回这个 change 的 design.md（用 openspec-update-change）
   - 如果涉及新的架构决策：写新 ADR，并同步更新 architecture.md 和 config.yaml 的 context
   - 不要在 docs/superpowers/ 或其他位置另写设计文档

3. 写计划：
   - 用 superpowers 的 writing-plans，以 tasks.md 为骨架，计划的每一步都标上对应的任务编号（例如 3.2）
   - 不加 tasks.md 以外的范围
   - 发现 tasks 有遗漏：先改 tasks.md，再改计划

4. 实现：
   - 用 using-git-worktrees 开分支，分支名等于 change 名
   - 用 test-driven-development 配合 subagent-driven-development 执行
   - 只用 architecture.md 和 ADR 里已确定的技术。要引入任何未列出的语言、框架、数据库、云服务或主要依赖，先停下来问我
   - 每完成一个任务，在 tasks.md 里勾选并提交一次

5. 偏离原计划时：发现需求或设计要变，先停下，用 openspec-update-change 改 spec 或 design，告诉我改了什么，然后再继续。代码和 spec 任何时候都不能不一致。

6. 收尾：
   - 用 verification-before-completion 跑完整检查，并列表核对：Scenario | 测试文件:用例名。只要有 Scenario 没有测试覆盖，就停下来报告
   - 用 openspec-archive-change 归档，确认 openspec/specs/ 下生成了对应的主 spec
   - 更新 docs/roadmap.md 里这个 change 的状态
   - 用 finishing-a-development-branch 合回 main

如果这个 change 是 setup-foundation，还要额外做：
   - 目标是 walking skeleton：用一条最薄的链路，把 architecture.md 里的每个运行单元都串起来跑通一次
   - 把构建、测试、本地启动的命令写进 AGENTS.md 和 config.yaml 的 context
   - 完成后提醒我：旧分支 codex/deliver-probeinterview-mvp 和 .worktrees/deliver-probeinterview-mvp 可以删了。由我自己来删
```

---

## 遇到变化怎么办（不需要改 prompt）

| 情况 | 怎么做 |
|---|---|
| 需要新的技术决策 | 阶段 3 第 2 步：和 agent 讨论，然后写 ADR，再同步 architecture.md 和 context |
| 需求变了 | 用 openspec-update-change 修改对应的 change；已经归档的，新开一个 change |
| 新增一个功能 | 用 openspec-propose 新建 change，加进 roadmap.md，然后走阶段 3 |
| 某个 Open 项到了必须决定的时候 | 阶段 3 第 1 步的准入检查会拦下来，那时再决定，然后写 ADR |

## 以后开新项目

顺序和这次一样，只是每一步都提前做：

1. **需求**：用 openspec-explore 讨论，产出 PRD 和功能路线图。这一步不开实现用的 change。
2. **架构**：做法同阶段 1。如果还没有 visuals，就在会话里讨论出来，产出 architecture.md、ADR 和 UI 基线。
3. **拆 change**：同阶段 2，不过这次每个 change 从一开始就是单独建的。
4. **实现**：同阶段 3，先做 setup-foundation。

# 面试回路 spike

> 做完后移入 `docs/features/done/`。归档 = git 历史里的 feature 文件 + 测试名。
> **本文件立项的是一个 throwaway spike：代码不进 main，验收条目 = 结论（"我学到了什么"），不是测试。**

## 为什么

消除 `docs/requirements/simulated-interview.md` §5 里风险最高的一条——**结构化出题（受控知识点 ID + Schema 校验）能否成立**，即"不是自由聊天机器人"这条产品原则有没有技术支撑；顺带拿到百炼连通、五维粗评分、成本延迟的第一手数据。

切片沿用 BACKLOG `## Next` 已有条目（百炼连通 → 结构化出题 → 一轮受控追问 → 粗评分输出），不重定；§4 的四个未决项一个都不依赖（见 §决策）。

## 范围

- **做**：
  - `spikes/interview-loop/` 三个文件 + 一个 README：`run.py`（入口与三步编排）、`schemas.py`（出题 / 下一动作 / 评分三张 Pydantic schema）、`fixtures.py`（硬编码 3–5 个假知识点 ID、一份假 JD、两三段假回答文本）
  - 裸调百炼（DashScope）三步链路：结构化出题 → 一轮受控追问（下一动作被约束在 继续追问 / 切换知识点 / 结束 三者之一）→ 五维粗评分（未加权 + 证据引用）
  - 同一输入跑 N 次（建议 5 次）：打印每次 Schema 校验结果、虚构 ID 次数、维度分方差、耗时与 token/费用
- **不做**（每条带理由，防 scope 蔓延）：
  - **页面 / 小程序 UI**——验证的是模型能力不是交互；四个页面属于 spike 通过后的正式交付单元
  - **数据库 / 迁移 / 任何持久化**——结论是知识不是数据，spike 不产生需要保存的东西
  - **鉴权 / ActorContext / capability**——没有 API 就没有调用方；ADR 0004 那套是正式单元的事
  - **复盘、知识卡片、短板闭环**——本身就是 §4 的未决耦合项，spike 不碰
  - **报告 UI 与加权总分**——五维权重（15/25/20/25/15）是 §4 未决的产品决策，spike 加权就等于替你拍板
  - **语音转写（ASR）**——§5 里独立的 L3 候选，成本 / 延迟 / 音频即时删除要单独验证；本 spike 全部用文字回答替代，**spike 结论不含 ASR**
  - **简历 PDF 解析、JD 多图 OCR**——同为 §5 独立 L3 候选；JD 与简历背景用硬编码文本 fixture
  - **端口 / 适配器正式装配、平台内容包、稳定知识点 ID 体系**——§4.1 未决；spike 裸调 SDK，不建 taxonomy
  - **完整 15 分钟整场流程、配置快照、时间预算控制**——那是 requirements §6 的完整切片，spike 通过后的第一个正式交付单元

## 落点（D0）

| 动作 | 文件 | 参照实现 / 不变量 |
|---|---|---|
| 新建 | `spikes/interview-loop/run.py` | 入口 + 三步编排 + N 次跑批汇总 |
| 新建 | `spikes/interview-loop/schemas.py` | 出题 / 下一动作 / 评分三张 Pydantic schema；校验失败原样记录为结论输入 |
| 新建 | `spikes/interview-loop/fixtures.py` | 硬编码假知识点 ID（3–5 个）、假 JD、假回答文本 |
| 新建 | `spikes/interview-loop/README.md` | 怎么跑、需要什么环境变量、结论往哪写 |

只新建 `spikes/interview-loop/` 这一个目录；不修改 `apps/`、`infra/` 下任何文件，不 import 产品代码。

**不变量**——改了会坏的东西：

- `spikes/` 永不合入 main：只在一次性分支 `spike/interview-loop` 上提交；结论落盘后整个目录废弃
- API key 只从环境变量读（`PROBEINTERVIEW_*` 惯例，如 `PROBEINTERVIEW_BAILIAN_API_KEY`），不写死、不进 git、不打进日志
- spike 代码同样保持 `scripts/verify` 绿（format/lint/mypy 按仓库现有范围），不绿不提交
- fixture 知识点 ID 与五维维度名都是 throwaway fixture，**不构成** §4.1 的 taxonomy 决策，也不构成五维权重决策

**只读参考**（不修改，实现前必须看）：

- `docs/requirements/simulated-interview.md` §2.2（状态机三动作与五条不变量）、§5（本 spike 对应的能力条目）
- `docs/design/visuals/interview-agent-state-machine.html`
- `git show codex/deliver-probeinterview-mvp:openspec/changes/deliver-probeinterview-mvp/specs/ai-application-interview/spec.md`（证据驱动追问与三动作的行为定义）
- `git show codex/deliver-probeinterview-mvp:openspec/changes/deliver-probeinterview-mvp/specs/interview-assessment/spec.md`（五维名称、评分必须引用回答原文的要求）
- `docs/recipes.md` §0（外部服务模式与 `PROBEINTERVIEW_*` 配置惯例；spike 不走端口装配，只参考 env 命名）

## 验收（= 结论，不是测试）

每条到期必须有一个答案，形式是"学到了什么"（数值 / 比例 / 判断），不是"哪个函数过了"：

- [ ] **连通**：百炼从本仓可达、受控输出约束生效，拿到单次调用的延迟与费用量级
- [ ] **受控出题**：给定 fixture ID 清单，产出能否稳定通过 Pydantic 校验，N 次运行中虚构清单外 ID 的比例有数
- [ ] **受控追问**："下一动作"能否被约束在三动作之一，追问（如选）能否引用回答原文片段
- [ ] **评分引用证据**：五维（未加权）每一维能否给出可定位到回答原文的引用，空泛率人工抽样有数
- [ ] **自洽偏差初值**：同一输入重复 N 次的题目数与五个维度分方差量级（"单一 Agent 自洽偏差"风险的第一个数）
- [ ] **成本/延迟合计**：一轮"出题 → 追问 → 评分"的 token 与耗时合计，对照 15/30/45 分钟预算给出可行性数量级

模板的五类失败路径：并发竞争 / 越权 / 脱敏 / 补偿不适用（无 API、无 DB、无用户）；适用的一条是**超时 / 外部服务失败**——LLM 调用失败与校验失败原样记录为结论输入，不手写重试循环（SDK 默认重试除外）。

## 时间盒

2 天（含写结论的时间）。到期当日最后 1 小时固定用于写结论，无论跑没跑完。到期没结论也要写结论——"测不出"是合格结论（例：5 次运行虚构率 40%，受控出题在当前模型上不成立；或：2 天没跑通连通，卡点是 X）。

## 交付单元

- [x] ① 立项文档 · 落点：`docs/features/interview-loop-spike.md` · 验收：文档自检（结论条目 ≤6 且每条一行、"不做"长于"做"、§4 四项逐一有绕开说明）· 验证：`scripts/verify`
- [ ] ② spike 执行与结论写回 · 落点：`spikes/interview-loop/`（throwaway 分支 `spike/interview-loop`）· 验收条目：§验收 6 条 · 验证：跑批原始输出 + 人工抽样记录

## 结论写回

- **位置**：`BACKLOG.md` `## Next` 的"面试回路 spike"条目，原位打勾并在条目后追加结论行；若结论影响后续排期，同步修改 `## 未来` 里"模拟面试执行"的措辞。
- **格式**（一行）：

```text
- [x] **面试回路 spike**（YYYY-MM-DD 完成）→ 结论：<成立 | 有条件成立 | 不成立>：<一句话事实>（数据：docs/features/done/interview-loop-spike.md）
```

- **规则**：结论只写可执行事实（数值 / 比例 / 判断），不写建议措辞；若结论波及 §4 未决项，单列一行指向 §4 对应小节，不替 §4 拍板。

## 当前中间态

- **已落地**：本立项文档（单元①）。
- **未落地 / 已知会红**：spike 代码与结论（单元②）全部未开始；`spikes/` 目录尚不存在（本单元明确不建）。
- **下一步从哪开始**：单元②——从 §落点 建三个文件 + README，先跑通"结构化出题"一步，再串追问与评分。

## 决策

- fixture 知识点 ID 硬编码在 `fixtures.py`——被否掉的替代方案是等 §4.1 拍板再跑：受控出题测的是"给定任意受控清单能否绑定且不虚构"，清单本身是什么不影响结论。
- 评分只出五个未加权维度分、不算总分——被否掉的替代方案是按旧稿权重 15/25/20/25/15 加总：权重是 §4 未决产品决策，spike 加权等于替你拍板。
- 文字回答替代录音——被否掉的替代方案是把 ASR 拉进来：ASR 的成本 / 延迟 / 音频删除是独立 L3，混进来会让 2 天时间盒和结论都失焦。
- 裸调 SDK、不走产品端口——被否掉的替代方案是复用 `platform/foundation` 的装配：throwaway 代码耦合产品端口会让"丢弃"变贵；适配器设计留给 spike 通过后的正式单元。

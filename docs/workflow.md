# 开发工作流（D0–D6）

替代原 OpenSpec 流程。原则：**规划一页纸，验收变测试名，判卷交给机器。**

## 流水线

| 阶段 | 产物 | 放在哪 | 何时执行 |
|---|---|---|---|
| D0 范围 | feature 一页纸：为什么 / 范围 / 非目标 | `docs/features/<name>.md` | 动笔前，15 分钟 |
| D1 接口设计 | §接口 端点表 → Pydantic contracts | feature 文件 + `contracts.py` | 写实现之前；契约先于代码 |
| D2 单测 | 行为命名用例，每条 §验收 对应一个测试名 | `tests/unit` | 随实现，pre-commit 判卷 |
| D3 集成 | 真实 PG/Redis 行为、并发、迁移 | `tests/integration` | `scripts/verify --full` |
| D4 拓扑 | 整链路 Compose 断言 | `scripts/test-compose-topology` | 合并前 / CI |
| D5 真机 β | automator 能表达的 → beta smoke；其余 → §真机验收清单 | feature 文件 + `scripts/test-beta-smoke` | 功能"完成"后、发布前 |
| D6 部署验证 | 部署清单 + 回滚 | `docs/ops.md` | 每次上线 |

## 完成的定义（合并门槛）

1. `scripts/verify --full` 全绿；
2. feature 文件 §验收 每条都有对应测试（测试名即凭证）；
3. §真机验收清单 勾完（有 UI 的 feature）；
4. diff 经过人工 review 或 `/code-review`。

D6 是部署的门，不是合并的门。

## 规模分级（一页纸不够时怎么办）

| 级别 | 进入信号 | 做法 |
|---|---|---|
| **L1 默认** | 单模块、≤1 张新表、验收 ≤10 条 | 一页纸 feature，直接实现 |
| **L2 跨模块 / 新数据真相** | 涉及 ≥2 个模块、新表或新端口、验收 >10 条、需要异步/补偿流程 | feature 文件允许增加"设计"小节（上限 2 页，只写结构、数据模型、时序、失败路径，不复述架构文档）；涉及技术栈/模块边界/数据归属的决策**先写 ADR**；范围过大时在 BACKLOG 拆成 2–4 个子 feature 串行实现，父 feature 文件只留总览和链接 |
| **L3 技术不确定** | 依赖未验证的外部能力（LLM 生成质量、语音转写、评分可信度） | 先做时间盒 spike（throwaway，不进 main），结论写回 BACKLOG，再按 L1/L2 立项 |

判断顺序：先看是不是 L3（风险），再看是不是 L2（规模），默认 L1。禁止把 L2 写成一页纸硬塞——验收清单超过 10 条还没拆，就是信号。

## 规则

- **需求来源**：只从 `BACKLOG.md` 领活。一次会话只做一个 feature。
- **β case 规则**：能用 `miniprogram-automator` 表达的用例必须自动化进 smoke，不许留人工；人工清单只收真机微信运行时、真实设备存储/网络、真实 OSS 三类。人工清单保持每个 feature ≤5 条。
- **提交**：每个逻辑单元一提交，提交前 `scripts/verify` 必须绿（pre-commit hook 强制）。禁止"攒一批"提交。
- **偏离设计**：直接改 feature 文件相应小节并继续，不需要停下来等人批准；但涉及技术栈、模块边界、数据真相归属的，必须先写 ADR。
- **测试分层**：unit 测不变量与纯逻辑（秒级）；integration 测真实 PG/Redis/迁移/并发；jest 测小程序 model/service/组件逻辑；smoke 只测"活着的链路"，不测业务细节。
- **测试命名**：`test_<行为>_when_<条件>`，对应 feature 验收条目，让测试名可当作需求清单读。

## 规划文件的位置与流向

做一个新需求的完整路径：

```
① 排期入册     BACKLOG.md                          （加一行到 Next 或 Later）
② 立项一页纸   docs/features/<kebab-name>.md       （cp docs/features/_template.md，
                                                    填：为什么/范围/接口表/验收/真机/决策）
③ 架构级决策   docs/adr/NNNN-xxx.md                （仅当改技术栈/模块边界/数据归属；
                                                    同步 docs/architecture.md）
④ 会话实现     prompt 指向 feature 文件 + 验收条目范围，完成定义见上文
⑤ 完成归档     移入 docs/features/done/            （git 历史 + 测试名即完整档案）
```

| 文件 | 管什么 | 何时写/改 |
|---|---|---|
| `BACKLOG.md` | 做什么、什么顺序 | 立项时加行，做完划掉 |
| `docs/features/_template.md` | 新 feature 文件的模板 | 模板本身演进时才改 |
| `docs/features/<name>.md` | 单个功能的范围、契约、验收、真机清单 | 立项时建，偏离设计时随手改 |
| `docs/features/done/` | 完成功能的归档 | 功能合并后移入 |
| `docs/architecture.md` + `docs/adr/` | 项目级结构与技术决策（ADR 只追加） | 架构决策落地时 |
| `docs/recipes.md` | 怎么写：接口/表/页面的标准做法 | 出现新模式时补一条 |
| `docs/workflow.md` | 本文件：过程、门槛与文件流向 | 流程变化时 |
| `docs/ops.md` | 部署与上线验证 | 拓扑变化时 |
| `docs/development.md` | 本地启动与手工命令 | 命令变化时 |
| `openspec/` | **冻结的历史归档**，不再更新 | 永不 |

与旧 OpenSpec 工件的对应关系（仅供翻阅 `openspec/` 归档时对照）：

| 旧工件 | 新去处 |
|---|---|
| `proposal.md` | feature 文件 §为什么 + §范围 |
| `design.md` | §接口表 + §验收失败路径 + §决策（超 2 页 = L2，拆阶段） |
| `tasks.md` | 取消——分解是实现内部事务，判卷归 `scripts/verify` |
| `specs/` delta | 取消——测试名即规格，CI 保证不漂移 |
| 归档仪式 | 移入 `docs/features/done/` |

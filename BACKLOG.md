# Backlog

按优先级排序，做完划掉。一次会话只领一项；状态不在这里管理，在 git 和测试里。
（本文件取代 `docs/mvp-roadmap.md` 的排序职能。）

## Next

- [ ] **完成微信登录与 onboarding**（进行中，1.1–1.2 已完成待提交）→ `docs/features/wechat-onboarding.md`
- [ ] **面试回路 spike**（时间盒 2 天，throwaway 不进 main）：百炼连通 → 结构化出题（Pydantic 校验）→ 一轮受控追问 → 粗评分输出。验证产品最大技术风险，结论写回 BACKLOG。
- [ ] 上线准备：PostgreSQL 备份 cron + 恢复演练 + `/health/ready` 告警（见 `docs/ops.md`，首个真实发布的前置条件）

## Later（知识管线，顺序保持，单 change 语义改为单 feature 文件）

- [ ] 知识解析：markdown → 标题层级/章节，状态机与重试
- [ ] 岗位主题结构：六个主题、岗位归一化、知识点岗位映射
- [ ] 知识关联：受控 Agent 用别名 + pgvector + 结构化 LLM 关联或提议知识点
- [ ] 公共知识审核与发布：reviewer capability、冲突确认、ACTIVE 发布
- [ ] RAG 质量观测：confidence 校准、badcase、版本对比、费用延迟
- [ ] 首页真实数据：用 target role + 可见 scope 替换首页 fake 主题

## 未来（未拆分，先讨论再建 feature 文件）

- 面试配置与不可变输入快照；模拟面试执行（选题/追问/转写确认）；证据评估与报告；回放追溯；复盘闭环；离线评估与质量监控

## 完成

- [x] monorepo 骨架、类型化配置、API/Worker/PG/Redis/Caddy 运行单元
- [x] request/trace/job 上下文传播
- [x] 当前用户概览、owner 隔离、五 tab 骨架
- [x] 首页知识概览（视觉稿实现）
- [x] markdown 知识来源上传（OSS、幂等、配额、列表）

（历史细节见 `openspec/` 冻结归档，不再作为开发依据。）

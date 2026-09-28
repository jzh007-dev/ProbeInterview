# Spec Delta

## Purpose

定义 foundation probe 后续工作流依赖的 PostgreSQL/pgvector schema、迁移与 actor scope 行为，使任务和固定测试向量在进入异步执行前就能证明可恢复、可约束且跨 owner 隔离。

## ADDED Requirements

### Requirement: Foundation schema 可以从空库迁移并验证向量能力
系统 SHALL 通过显式迁移启用 pgvector 并建立业务无关的 probe job 与固定测试向量 schema，且 SHALL 使 schema 约束和向量读写可以自动验证。

#### Scenario: 空库升级到当前 schema
- **WHEN** 开发者对空 PostgreSQL 数据库执行 migration upgrade
- **THEN** pgvector 扩展、foundation probe job 表、foundation probe vector 表和约束被创建到当前版本

#### Scenario: 执行允许的降级
- **WHEN** 开发者在隔离测试数据库执行本 change 声明支持的 migration downgrade
- **THEN** migration 按设计回退且不会留下本 change 的不一致 schema

#### Scenario: 固定测试向量写入与查询
- **WHEN** 集成测试写入 foundation 固定维度测试向量并执行距离查询
- **THEN** PostgreSQL + pgvector 返回满足 schema 约束的可预测结果

### Requirement: Foundation 数据按 actor 隔离
系统 SHALL 为 foundation probe 和测试向量保存 owner，并 MUST 在查询任务、状态和向量之前限制为公共范围或当前 actor 的范围。

#### Scenario: owner 查询自己的 probe
- **WHEN** actor 查询属于自己的 probe
- **THEN** 系统返回该 probe 的当前状态

#### Scenario: actor 查询其他 owner 的 probe
- **WHEN** actor 查询属于其他 owner 的 probe
- **THEN** 系统拒绝访问且不透露目标是否存在

#### Scenario: 向量 smoke query 执行
- **WHEN** Worker 为 probe 写入并查询固定测试向量
- **THEN** 查询只允许使用当前 actor 的有效测试向量且不会返回其他 owner 的记录

### Requirement: Actor provider 不改变应用层身份契约
系统 SHALL 使应用层只依赖 `ActorContext(actor_id, capabilities)`，并 MUST 只在非生产环境允许 local actor provider。

#### Scenario: 非生产环境建立 actor context
- **WHEN** development 或 test 请求通过允许的 local actor provider
- **THEN** 应用层获得稳定 actor ID 与 capabilities，repository 通过显式 actor scope 执行查询

#### Scenario: production 尝试使用 local actor
- **WHEN** production 启动或请求路径尝试启用 local actor provider
- **THEN** 系统拒绝该配置或 provider，且不会建立调试 actor context

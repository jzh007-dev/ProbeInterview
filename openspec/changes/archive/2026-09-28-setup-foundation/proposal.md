# Proposal

## Why

ProbeInterview 需要先有可复现安装、可静态验证且按环境安全启动的工程骨架，后续运行拓扑、持久化和 probe changes 才能在稳定基线上独立实施。本 change 是原 `setup-foundation` 拆分后的第一段，只保留已完成的工程骨架与配置工作。

## What Changes

- 建立 `apps/backend`、`apps/miniprogram`、`infra/compose` 和 `scripts` 的 monorepo 与 module-first modular-monolith 骨架。
- 固定 Python 3.12 + uv、FastAPI/Pydantic 2、TypeScript + TDesign 及现有验证工具的可复现依赖。
- 建立 development、test、production 的 Pydantic Settings 配置 schema、无密钥示例配置和启动校验。
- 在 production 拒绝 local actor、fake adapter fallback 和 foundation probe 配置。
- 记录并验证当前已存在的安装、backend import、配置单元测试和小程序类型检查入口。
- 将 Docker Compose/API、持久化/actor、probe 客户端闭环及完整验证分别交由后续 changes，不在本 change 继续实施。

## Capabilities

### New Capabilities

- `platform-foundation`: 定义可复现工程骨架、锁定依赖和按环境安全校验配置的基础行为。

### Modified Capabilities

无。当前项目没有已归档的 durable capability specs。

## Impact

- 已完成的原任务 1.1、1.2 保持完成状态；本 change 拆分后为 2/2 tasks 完成。
- 影响工程目录、Python/TypeScript 依赖与锁文件、backend/miniprogram 基础入口、运行配置和开发文档。
- 本 change 无前置 change；完成并归档后解锁 `establish-runtime-api-foundation`。
- 原 2.1 的未提交 Docker/Compose/Caddy 改动不属于本 change，归属 `establish-runtime-api-foundation`。
- 不新增任何知识库、卡片、面试或用户产品能力，也不连接真实 OSS 或百炼业务接口。

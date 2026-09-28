# Tasks

## 1. 建立可复现工程骨架

- [x] 1.1 创建 `apps/backend`、`apps/miniprogram`、`infra/compose` 和 `scripts` 目录，按业务模块内部再分层建立 modular-monolith 骨架，配置 Python 3.12 + uv、TypeScript + TDesign 和依赖锁定；以全新环境安装、backend import 和小程序类型检查验证骨架可复现
- [x] 1.2 使用 Pydantic Settings 建立 development、test、production 配置 schema、无密钥示例配置和启动校验，记录本地启动命令；以配置单元测试验证缺少必填项时明确失败、production 禁止 local actor、fake production fallback 和 foundation probe

# Tasks

依赖：`setup-foundation` 已完成并归档。原 `setup-foundation` 任务 2.1–2.2 映射到本 change；当前未提交的 Docker/Compose/Caddy 改动归属 1.1，恢复实施时必须原样接续。

## 1. 交付运行拓扑与 API 基础

- [x] 1.1 配置 Caddy、FastAPI、Celery Worker、PostgreSQL + pgvector 和 Redis 的 Docker Compose 服务、健康检查及隔离测试 profile，提供 Caddy 反向代理、production 自动 TLS/HTTPS 跳转配置和本地测试配置；以 Compose 校验、代理请求及所有基础服务健康验证运行拓扑
- [x] 1.2 实现 `/health/live`、`/health/ready`、直接类型化成功响应、RFC 9457 `application/problem+json` 错误、`X-Request-ID` 中间件和带 request/trace/job ID 的结构化安全日志；以 API 测试验证依赖故障、字段错误、未处理异常、敏感信息脱敏和 request ID 传播

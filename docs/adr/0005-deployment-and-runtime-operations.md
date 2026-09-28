# ADR 0005: Deployment and runtime operations

## Status

Accepted

## Date

2026-09-28

## Context

ProbeInterview 的 MVP 需要控制成本，并让一个开发者能够在本地和单台服务器上复现完整运行环境。当前没有高可用、跨地域或独立扩缩容要求，但微信小程序访问生产 API 需要稳定的 HTTPS 入口。

配置、日志和隐私若不在 foundation 统一，后续知识正文、Prompt、模型响应和上传文件信息可能被无意写入普通日志。

## Decision

MVP 部署在单台阿里云 ECS，并使用 Docker Compose 编排：

- Caddy gateway；
- FastAPI API；
- Celery Worker；
- PostgreSQL + pgvector；
- Redis。

API 与 Worker 使用同一后端镜像和代码包，通过不同启动命令运行。Compose 使用健康检查和应用级重试判断依赖可用，不能仅依赖容器启动顺序。持久数据使用明确命名的卷；测试 profile 使用隔离且可清理的数据卷。

Caddy 是外部 HTTP 入口，负责反向代理、TLS 证书申请与续期以及 HTTP 到 HTTPS 跳转。应用服务不直接暴露到公网。未来若迁移到负载均衡或托管网关，可替换 Caddy，但不得改变内部 API 契约。

配置使用 Pydantic Settings 定义类型化 schema，并按 development、test 和 production profile 校验。密钥、数据库口令和供应商凭证只通过环境或部署时的 secret injection 提供，不提交到仓库或写入镜像。本地与自动测试默认不需要真实云凭证。

服务输出结构化 JSON 日志。Request ID 贯穿 HTTP，Trace ID 用于跨运行单元关联，Job ID 用于后台任务定位。正常日志默认不得包含：

- 上传文件正文或解析后的私人知识；
- HTTP 请求正文；
- 完整 Prompt、模型响应或语音转写；
- 密钥、令牌、连接串或签名 URL；
- 返回给客户端的内部异常堆栈。

`setup-foundation` 只建立健康检查、日志字段、配置校验和单机运行方式，不交付高可用、自动扩缩容、完整监控平台或灾难恢复系统。

## Alternatives

### Nginx gateway

Nginx 成熟且团队普及度高，但单机 MVP 仍需额外配置和维护证书自动化。当前没有依赖 Nginx 特有能力的需求。

### Kubernetes

Kubernetes 能提供调度、扩缩容和服务治理，但会显著增加 MVP 的部署与故障排查成本。

### Managed database and queue from the beginning

托管服务能提高可用性并减少维护，但当前目标是最低成本的单机闭环。数据库或队列迁移到托管服务时，应用协议不应改变。

### Plain text logs

本地阅读简单，但不利于按 request、trace 和 job 关联查询，也更难统一脱敏。

## Consequences

- 单 ECS 故障会导致完整服务暂时不可用，这是 MVP 明确接受的取舍。
- Caddy、API、Worker、PostgreSQL 和 Redis 都必须进入本地及端到端验证拓扑。
- production 必须配置域名、持久卷、备份和真实 secret；具体备份与告警实施可在上线前单独补充。
- 日志排障优先依赖结构化标识和安全摘要，需要查看私人原文时必须走受控数据访问流程。
- 达到可用性、容量或团队独立部署阈值后，应以新 ADR 重新评估单机 Compose。


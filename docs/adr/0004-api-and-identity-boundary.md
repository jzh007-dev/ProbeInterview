# ADR 0004: API and identity boundary

## Status

Accepted

## Date

2026-09-28

## Context

微信小程序需要调用同步查询和异步命令。后续功能必须共享稳定的错误、追踪、幂等和身份约定，否则每个 change 会形成不同协议。

正式微信登录尚不属于 `setup-foundation`，但如果 foundation 使用全局固定用户，owner 隔离和公共知识发布权限将无法得到真实验证。管理者同时也是普通用户，只因处于白名单而获得发布公共知识的能力，因此应用层不应建立一套独立管理者身份模型。

## Decision

所有版本化业务 API 位于 `/api/v1`。

成功响应直接返回其类型化资源，不增加通用 `data/meta` 包装。列表、分页或异步状态所需的元数据属于具体响应 schema。Request ID 通过 `X-Request-ID` 响应头返回。

错误响应使用 RFC 9457 Problem Details，并使用 `application/problem+json`。除标准字段外，系统可以使用稳定的业务错误码和字段级验证错误扩展，但不得把内部异常、堆栈、SQL 或供应商原始错误暴露给客户端。

异步创建命令返回 HTTP `202 Accepted`，响应体返回任务资源，`Location` 指向状态查询地址。客户端通过轮询读取 `QUEUED`、`RUNNING`、`SUCCEEDED` 或 `FAILED` 等有限状态。

会产生持久化副作用且可能被客户端重试的命令接受 `Idempotency-Key`。服务端以 actor、命令类型、幂等键和规范化输入摘要共同判定重复请求：

- 相同输入返回既有资源或任务；
- 相同键但输入不同返回 `409 Conflict`。

应用层只依赖 `ActorContext(actor_id, capabilities)`，不读取微信登录细节或任意调试 header。Development/test 可以使用仅在非生产环境启用的 local actor provider；production 启动时必须拒绝该 provider。正式微信身份交换由单独 change 实现，并映射到同一个 `ActorContext`。

白名单用户仍使用普通用户入口。身份适配器根据白名单为其添加公共知识发布能力；知识业务根据 capability 和目标范围授权，而不是判断独立“管理员账号类型”。

所有 owner-scoped repository 查询必须显式接受 actor scope，并在读取记录或向量前应用个人/公共范围条件。对不可见资源返回与不存在一致的外部结果，不泄露资源是否存在。

## Alternatives

### Universal `data/meta` and `error/meta` envelopes

统一包装看起来一致，但会增加所有成功 schema 和生成客户端的层级；HTTP 状态、响应头和 Problem Details 已能表达通用协议。

### Implement WeChat login inside setup

可以更早验证真实身份交换，但会把微信外部依赖、会话管理和账户生命周期加入 foundation，破坏其最小闭环。

### Fixed global development user

实现最快，但无法证明跨 owner 隔离，并容易被后续代码当成生产假设。

### Separate administrator identity model

不符合当前“管理者也是普通用户”的产品决定，也会产生两套入口和重复授权逻辑。

## Consequences

- `setup-foundation` 当前设计中的 `data/meta` 和 `error/meta` 假设必须在后续同步时改为本 ADR 的协议。
- OpenAPI schema 可以直接表达成功资源和标准错误，客户端仍需统一处理 `X-Request-ID` 与 Problem Details。
- local actor 和诊断 probe 必须在生产配置中默认禁用。
- 后续微信登录 change 只替换身份 provider，不应改变应用服务和 repository 的 actor contract。
- 公共知识发布权限可通过白名单演进，不需要单独管理后台才能开始。


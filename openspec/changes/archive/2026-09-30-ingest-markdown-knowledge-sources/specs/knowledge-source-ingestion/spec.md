# Spec Delta

## Purpose

定义当前用户安全上传、持久化并管理 Markdown 知识来源的行为契约，为后续解析、知识关联和发布流程提供可追溯的原始资料与版本真相。

## ADDED Requirements

### Requirement: 当前用户可以提交一个有效的 Markdown 知识来源
系统 SHALL 提供 `POST /api/v1/me/knowledge-sources`，接受一个文件、一个可选的 `PRIVATE` 或 `PUBLIC` scope、一个可选的 `original_filename` 表单字段以及 `Idempotency-Key`。scope 未提供时 SHALL 默认为 `PRIVATE`。当 `original_filename` 存在时，系统 SHALL 将其作为用户选择的原文件名；否则 SHALL 使用 multipart 文件 part 的文件名，以保持普通 HTTP 客户端兼容。系统 SHALL 对最终采用的文件名执行 basename 规范化、安全长度和不区分 ASCII 大小写的 `.md` 后缀校验，不得信任其中的路径。文件内容 SHALL 为非空、无 NUL 字节的 UTF-8，且文件大小 MUST 严格小于 `500 * 1024` bytes。系统 SHALL 有上限地读取请求内容，并 MUST NOT 在本次能力中解析 Markdown 结构、提取知识点或调用模型。

#### Scenario: 上传有效的私人 Markdown
- **WHEN** 已认证用户以新的 `Idempotency-Key` 上传一个有效 Markdown 文件且未提供 scope
- **THEN** 系统按 `PRIVATE` 接受文件，返回 `202` 类型化资源和该资源的 `Location`，且资源处理状态为 `PENDING_EXTRACTION`

#### Scenario: 保留微信选择时的原文件名
- **WHEN** 微信小程序选择一个 Markdown 文件、上传传输层将 multipart 文件 part 名改写为临时哈希名，并同时提交选择时的 `original_filename`
- **THEN** 系统校验并持久化 `original_filename` 的安全 basename，上传结果和后续列表展示该原文件名而不是临时哈希名

#### Scenario: 拒绝达到大小上限的文件
- **WHEN** 用户上传的文件大小等于或大于 `500 * 1024` bytes
- **THEN** 系统拒绝请求并返回 RFC 9457 Problem Details，且不创建来源记录、不占用配额也不保留对象

#### Scenario: 拒绝非 Markdown 文件名
- **WHEN** 最终采用的原文件名不以 `.md` 结尾
- **THEN** 系统拒绝请求并返回字段级可识别的 RFC 9457 Problem Details，且不创建来源记录或存储对象

#### Scenario: 拒绝无效文本内容
- **WHEN** 用户上传空文件、非 UTF-8 内容或包含 NUL 字节的内容
- **THEN** 系统拒绝请求并返回 RFC 9457 Problem Details，且不创建来源记录、不占用配额也不保留对象

#### Scenario: 拒绝未知 scope
- **WHEN** 用户提交 `PRIVATE` 和 `PUBLIC` 之外的 scope
- **THEN** 系统拒绝请求并返回字段级可识别的 RFC 9457 Problem Details

### Requirement: 接受的来源以数据库元数据和对象存储原文形成持久化真相
系统 SHALL 将接受的 Markdown 原始字节存入配置的对象存储，并 SHALL 在 PostgreSQL 中持久化来源及其当前版本的 owner、creator、scope、原始文件名、媒体类型、字节数、SHA-256、供应商无关的对象 key、上传时间和处理状态。数据库 MUST NOT 保存完整 Markdown 内容、永久公开 URL、访问凭证或供应商私有响应。只有对象写入和相应数据库记录均成功时，上传 SHALL 被视为已成功存储并计入配额；任一步骤失败时系统 SHALL 返回 RFC 9457 Problem Details，并 SHALL 避免留下可被列为有效来源的不完整状态。

#### Scenario: 成功保存来源和版本
- **WHEN** 有效上传的对象写入和数据库提交均成功
- **THEN** 系统持久化一个 owner-scoped 来源及其当前版本，保存内容摘要和对象 key，并将处理状态设为 `PENDING_EXTRACTION`

#### Scenario: 对象存储写入失败
- **WHEN** 对象存储未能保存有效上传
- **THEN** 系统返回稳定业务错误的 RFC 9457 Problem Details，不创建有效来源且不占用当日配额

#### Scenario: 对象写入后数据库提交失败
- **WHEN** 对象已写入但对应数据库事务无法提交
- **THEN** 系统不返回成功、不产生可见来源或配额消耗，并触发对该未引用对象的补偿清理

### Requirement: 每个用户的上传配额由数据库策略约束
系统 SHALL 从当前 actor 的数据库策略读取每日成功存储上限和有效来源总上限。默认策略 SHALL 为每个 `Asia/Shanghai` 自然日最多成功存储 2 个文件、最多保留 100 个有效来源；时间戳 SHALL 以 UTC 持久化。同步校验失败、存储失败和幂等重试 MUST NOT 消耗每日配额；成功存储并进入 `PENDING_EXTRACTION` 的来源 SHALL 消耗一次配额。并发请求 MUST NOT 使任一上限被突破。

#### Scenario: 在每日限额内上传
- **WHEN** 用户当日成功存储数量低于其数据库策略上限且有效来源数量低于总上限
- **THEN** 一个新的有效来源可被成功存储并使当日已用数量增加 1

#### Scenario: 达到每日限额
- **WHEN** 用户在当前 `Asia/Shanghai` 自然日已达到其数据库策略的成功存储上限后提交新的非重复有效文件
- **THEN** 系统返回包含稳定配额错误码和当前配额上下文的 RFC 9457 Problem Details，且不存储新对象或来源

#### Scenario: 达到有效来源总上限
- **WHEN** 用户已有的有效来源数量达到其数据库策略的总上限后提交新的非重复有效文件
- **THEN** 系统返回包含稳定来源上限错误码的 RFC 9457 Problem Details，且不存储新对象或来源

#### Scenario: 跨越上海自然日
- **WHEN** UTC 时间跨越对应的 `Asia/Shanghai` 新自然日且用户提交新文件
- **THEN** 系统按新的上海自然日重新计算每日已用数量，同时保留有效来源总上限约束

#### Scenario: 并发请求争用最后一个名额
- **WHEN** 同一用户的多个新上传并发争用剩余的一个每日或总量名额
- **THEN** 至多一个新来源成功存储，其他请求收到配额 Problem Details，持久化计数不超过策略上限

### Requirement: 重试和重复内容不会创建或计数第二份来源
系统 SHALL 以 actor、上传命令、`Idempotency-Key` 和规范化输入摘要识别实际创建来源的命令重试，并 SHALL 以 owner、scope 和内容 SHA-256 识别现有有效来源。已绑定到来源创建命令的相同幂等键和相同规范化输入 SHALL 返回原结果；该幂等键配合不同输入 MUST 返回冲突。相同 owner、scope 和 SHA-256 的新命令 SHALL 复用既有有效来源，不创建新版本、不重写对象且不再次消耗配额；由于该路径没有新副作用，其新幂等键无需绑定到既有来源。相同内容使用不同 scope SHALL 视为不同来源。

#### Scenario: 相同幂等请求重试
- **WHEN** 用户以相同 `Idempotency-Key` 和相同文件及 scope 重试已成功接受的上传
- **THEN** 系统返回同一来源结果，不创建第二条来源、版本或对象，也不再次消耗配额

#### Scenario: 幂等键被用于不同输入
- **WHEN** 用户以已绑定到来源创建命令的 `Idempotency-Key` 提交不同文件内容或不同 scope
- **THEN** 系统返回 `409` RFC 9457 Problem Details，且不改变原来源

#### Scenario: 新命令提交相同内容
- **WHEN** 同一 owner 以新的 `Idempotency-Key` 提交与既有有效来源相同 scope 和 SHA-256 的内容
- **THEN** 系统返回既有来源，不创建新版本或对象，也不消耗新的每日配额

#### Scenario: 相同内容使用不同 scope
- **WHEN** 同一 owner 以新的 `Idempotency-Key` 提交相同 SHA-256 但不同 scope 的内容且具备所需能力
- **THEN** 系统将其作为新的来源按正常配额规则处理

### Requirement: 公共来源提交需要显式能力
系统 MUST 在写入对象或数据库前检查 `PUBLIC` 上传者是否拥有 `knowledge.submit_public` capability。缺少该 capability 的用户 MUST NOT 创建 `PUBLIC` 来源。`PUBLIC` 在本次能力中 SHALL 仅表达未来公开发布意图，不使记录或原始文件对其他用户可见。

#### Scenario: 有能力的用户提交公共来源
- **WHEN** 当前 actor 拥有 `knowledge.submit_public` 且提交有效的 `PUBLIC` Markdown
- **THEN** 系统按正常配额和持久化规则接受来源，并将其 scope 保存为 `PUBLIC`

#### Scenario: 无能力的用户提交公共来源
- **WHEN** 当前 actor 不拥有 `knowledge.submit_public` 且提交 `PUBLIC` Markdown
- **THEN** 系统返回 `403` RFC 9457 Problem Details，且不写入对象、不创建来源也不消耗配额

#### Scenario: 其他用户不能读取公共意图来源
- **WHEN** 一个来源的 scope 为 `PUBLIC` 但其 owner 不是当前 actor
- **THEN** 本次能力的列表和上传结果均不向当前 actor 暴露该来源或其原始文件

### Requirement: 当前用户可以读取自己的上传记录和配额上下文
系统 SHALL 提供 `GET /api/v1/me/knowledge-sources`，直接返回类型化资源，其中包含当前 actor 的配额上限、当前 `Asia/Shanghai` 自然日已用数量、有效来源数量以及来源集合。每条来源 SHALL 只暴露展示所需的稳定 id、原始文件名、scope、处理状态和上传时间，MUST NOT 暴露对象 key、SHA-256、永久访问 URL、供应商信息或其他 actor 的记录。来源集合 SHALL 按上传时间倒序排列，并以稳定 id 作为并列时间的确定性次排序。

#### Scenario: 按 owner 和时间列出记录
- **WHEN** 当前 actor 拥有多条不同时间上传的 `PRIVATE` 和 `PUBLIC` 来源并请求列表
- **THEN** 响应只包含该 actor 的来源，按上传时间从新到旧排列，并包含当前配额上下文

#### Scenario: 不泄露其他用户记录
- **WHEN** 其他 actor 拥有更新的私人或公共意图来源
- **THEN** 当前 actor 的列表、有效来源数量和每日已用数量均不包含其他 actor 的数据

#### Scenario: 没有上传记录
- **WHEN** 当前 actor 尚无有效来源并请求列表
- **THEN** 系统返回 `200`、空来源集合和该 actor 的数据库策略及零使用量

### Requirement: 上传与管理页面呈现真实来源状态
微信小程序上传 tab SHALL 按 `docs/design/visuals/home-overview.html` 的“上传与管理”方向只提供“知识资料”，并 SHALL 支持选择单个 Markdown 文件、选择 `private` 或 `public` 可见范围、默认 `private`、提交上传和查看最近上传。页面 SHALL 区分初始加载、空记录、已选择文件、上传中、成功刷新、错误和配额耗尽状态，不得展示“私人题库”、伪造成功解析结果或伪造知识节点数量。

#### Scenario: 加载和展示空记录
- **WHEN** 用户进入上传 tab 且列表请求正在进行或成功返回空集合
- **THEN** 页面先显示明确加载状态，再显示可上传 Markdown 的空记录状态和真实配额信息

#### Scenario: 选择文件和可见范围
- **WHEN** 用户选择一个 Markdown 文件并打开上传表单
- **THEN** 页面展示文件名和大小，默认选中 `private`，并允许用户显式选择 `public`

#### Scenario: 上传进行中
- **WHEN** 用户提交有效文件且上传请求尚未完成
- **THEN** 页面防止重复提交并展示明确的上传中状态

#### Scenario: 上传成功后刷新
- **WHEN** 上传 API 成功返回 `PENDING_EXTRACTION` 来源
- **THEN** 页面刷新真实列表和配额，并在最近上传首部展示该文件

#### Scenario: 展示处理中记录和 scope 标签
- **WHEN** 最近上传包含 `PENDING_EXTRACTION` 来源
- **THEN** 每条记录展示原始文件名、“正在提取知识点”和与 scope 对应的 `public` 或 `private` 标签，不展示成功状态或知识节点数量

#### Scenario: 展示上传或列表错误
- **WHEN** 文件校验、授权、配额、存储或列表请求失败
- **THEN** 页面展示可理解且可重试或可纠正的错误状态，不把失败记录渲染为成功上传

#### Scenario: 配额耗尽
- **WHEN** 列表或上传错误表明当前用户已用尽当日配额或达到有效来源上限
- **THEN** 页面展示对应配额说明并禁用新的提交动作，同时继续展示已有 owner-scoped 记录

# Proposal

## Why

ProbeInterview 的首页仍是空页面壳，无法验收已经确认的首页知识发现视觉，也没有消费未来登录流程缓存的当前用户昵称。知识上传与 RAG 仍需多个后续 change，因此先交付一个边界明确的首页视觉切片，让缓存身份展示数据、动态时间问候和显式 fake 训练数据可以在不提前建立知识领域模型的情况下共同验收。

## What Changes

- 按 `docs/design/visuals/home-knowledge-categories.html` 实现微信小程序首页，包括问候、本周覆盖、待复盘、继续学习和六个主题分类。
- 新增客户端当前用户展示缓存边界：首页优先读取未来登录流程写入的昵称；在当前尚未实现登录的 development/test 环境中，缓存缺失或损坏时仅回退调用一次现有 `/api/v1/me/overview` 并刷新缓存，不新增或修改后端 API。
- 根据设备本地时间动态展示日期和“早上好 / 下午好 / 晚上好”，并在页面每次重新显示时刷新。
- 本周覆盖、待复盘、继续学习和主题分类使用页面内统一导入的确定性 fake fixture，不伪装成真实知识库响应。
- “继续学习”使用三张 fake 卡片和微信原生滑动组件，滑动时同步更新卡片、指示点和进度，不保存学习进度。
- 覆盖缓存命中、回退加载、成功、错误和重试状态；加载或失败时不得展示硬编码用户昵称。
- 保留搜索、继续学习和主题选择的命名交互，其中主题选择只更新本地选中状态和摘要；搜索与继续学习不导航、不发起知识 API 请求且不产生持久化副作用。
- 继续使用微信原生五 tab 导航，并验收当前页面自动使用配置的选中颜色和选中图标；不在首页内部复制视觉稿导航。
- 明确排除 Markdown 上传、知识来源、知识点、岗位映射、RAG、学习进度、复盘统计和真实主题数据；这些由后续 changes 交付。

## Capabilities

### New Capabilities

- `home-knowledge-overview`: 当前用户在微信小程序首页通过客户端缓存查看昵称、动态时间问候、可滑动 fake 学习卡片与确定性知识训练概览，并执行无副作用预留交互的端到端行为。

### Modified Capabilities

无。

## Impact

- Mini program：替换 `pages/index` 空页面壳，新增当前用户展示缓存、首页组件、typed fake fixture、时间格式化、原生 swiper、状态管理和自动化测试。
- Existing API：只在 development/test 缓存缺失或损坏时只读回退复用 `/api/v1/me/overview`；当前 backend 继续使用 local actor，不改变 `my-profile-overview` 契约、数据库或后端实现，也不把缓存当作鉴权凭证。
- Visuals：以 `docs/design/visuals/home-knowledge-categories.html` 为主要参考，并保持现有原生五 tab 导航及其自动选中状态。
- Dependencies：继续使用原生微信小程序 TypeScript、TDesign、现有 API client 和测试依赖，不新增语言、框架、云服务或主要依赖。

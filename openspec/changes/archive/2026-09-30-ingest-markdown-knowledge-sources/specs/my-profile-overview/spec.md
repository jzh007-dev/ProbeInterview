# Spec Delta

## MODIFIED Requirements

### Requirement: 五个 tab 和未来动作保持可扩展边界
微信小程序 SHALL 按“首页、复盘、模拟、上传、我的”的顺序提供五个 tab 页面。“我的” SHALL 展示个人概览；“上传” SHALL 由 `knowledge-source-ingestion` 能力提供 Markdown 知识资料上传与管理页面；首页、复盘和模拟 tab 在本次 change 中 SHALL 保持各自现有实现状态，不因本 change 扩展业务。个人页上的设置、已有简历和历史栏目 SHALL 暴露稳定的命名动作，但 MUST NOT 在本次 change 中执行页面跳转、预览、上传、更换、下载或配置写入；简历上传入口 SHALL 留给后续模拟面试能力。

#### Scenario: 从其他 tab 进入“我的”
- **WHEN** 用户从首页、复盘、模拟或上传 tab 点击“我的”
- **THEN** 小程序切换到“我的”tab 并加载个人概览页面

#### Scenario: 进入上传 tab
- **WHEN** 用户点击上传 tab
- **THEN** 小程序展示由 `knowledge-source-ingestion` 定义的上传与管理页面，并保持五个 tab 可继续切换

#### Scenario: 进入未实现业务 tab
- **WHEN** 用户点击首页、复盘或模拟 tab
- **THEN** 小程序保持该 tab 的既有页面行为，不由本 change 添加上传或知识来源管理行为

#### Scenario: 触发预留栏目动作
- **WHEN** 用户点击设置、已有当前简历、历史成绩、面试语言、隐私与数据或关于栏目
- **THEN** 页面识别对应的稳定命名动作，但不导航、不修改数据库且不启动文件操作

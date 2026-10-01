# 部署与上线验证（D6）

MVP 拓扑：单台阿里云 ECS + Docker Compose，Caddy 是唯一发布端口（80/443，自动 TLS），
见 `compose.production.yaml` 与 ADR 0005。

## 上线前硬门槛

- [ ] **PostgreSQL 备份已配置并演练过恢复一次**（单机无 HA，无备份 = 生产数据裸奔）。最低方案：宿主机 cron `docker exec <pg> pg_dump` 到数据盘 + 异机拷贝。
- [ ] 全部 secret 通过部署环境注入，未出现在任何文件或命令历史：`PROBEINTERVIEW_DOMAIN`、`PROBEINTERVIEW_DATABASE_URL`、`PROBEINTERVIEW_CELERY_BROKER_URL`、`PROBEINTERVIEW_POSTGRES_PASSWORD`、`PROBEINTERVIEW_WECHAT_APP_ID`、`PROBEINTERVIEW_WECHAT_APP_SECRET`、`PROBEINTERVIEW_OSS_*`、`PROBEINTERVIEW_BAILIAN_API_KEY`（缺一 compose 会因 `:?` 断言启动失败，这是预期的防护）。
- [ ] `scripts/verify --full` 与 `scripts/test-compose-topology` 在发布 commit 上全绿。

## 部署步骤（每次发布按序执行）

```bash
# 1. 构建 + 启动（initializer 只做迁移；生产禁用 demo seed）
docker compose \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  -f infra/compose/compose.production.yaml \
  up --build --detach --wait

# 2. 确认迁移完成（initializer 退出码 0）
docker compose --project-directory infra/compose \
  -f infra/compose/compose.yaml -f infra/compose/compose.production.yaml \
  ps database-initializer

# 3. 健康检查
curl --fail https://<域名>/health/ready   # 200 且 dependencies 全 available

# 4. 日志确认
docker compose --project-directory infra/compose \
  -f infra/compose/compose.yaml -f infra/compose/compose.production.yaml \
  logs api --tail 100                      # 无 internal_error；响应含 X-Request-ID
```

## 上线后冒烟

- `PROBEINTERVIEW_BETA_BASE_URL=https://<域名> scripts/test-beta-smoke`（只读）。
- smoke 通过 fake 适配器的确定性登录码换取 Bearer 会话（seeded demo 身份），
  仅适用于 `wechat + fake` 环境；生产运行 `real` 适配器时该步骤不可用，
  冒烟以第 3 步 health 检查为准。

## 回滚

- 镜像回退：tag 上一可用镜像 → 重新 `up --detach --wait` → 重跑健康检查与冒烟。
- 迁移只前滚不回滚：新代码配套的迁移必须向后兼容一版（先加列后删列），保证旧镜像能跑在新 schema 上。

## 已接受的取舍（ADR 0005）

单 ECS 无高可用；Redis 非业务真相可随时清空重建；pgvector 数据可由原始来源重建。
告警最低方案：crontab 探测 `/health/ready` 非连续 200 时通知（企业微信/邮件任选其一）。

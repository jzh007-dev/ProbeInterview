# Tasks

## 1. 回退并延期 Trace Foundation

- [x] 1.1 通过正常 Git revert 撤销 `2406bdc`、`5063e97`、`64eadd6`、`56cd1ef` 和 `dc08702`，保留 main 已有的 `X-Request-ID`、Problem Details 与结构化日志，并确保 backend、架构文档和项目配置相对 main 无运行差异且不包含 OpenTelemetry/OTLP 依赖或代码；以 `git diff --exit-code main -- apps/backend docs openspec/config.yaml scripts`、`scripts/check-skeleton`、`cd apps/backend && uv run pytest tests/unit && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy`、`cd apps/miniprogram && npm run typecheck` 和 `openspec validate establish-trace-context-propagation --strict` 全部成功作为完成证据

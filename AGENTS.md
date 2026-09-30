# ProbeInterview Agent Rules

## Workflow

- Work comes from `BACKLOG.md`. One feature per session. Before coding, read that feature's file under `docs/features/` (create it from `docs/features/_template.md` if it does not exist).
- Follow `docs/workflow.md` (D0–D6). Follow `docs/recipes.md` for standard implementation patterns; do not invent new structure.
- Completion = every acceptance bullet has a test and `scripts/verify --full` is green. Commit per logical unit; never commit with a red `scripts/verify` (the pre-commit hook enforces this).
- Scope deviations: edit the feature file directly and continue. Only decisions that change stack, module boundaries or data ownership require an ADR first.
- Deferred RAG choices (chunking, embedding dimensions, index types, retrieval weights, rerank thresholds) still require an explicit confirmed design before implementation.

## Verification

- `scripts/verify` — fast gate (format, lint, mypy, backend unit, miniprogram jest + typecheck). Runs on every commit.
- `scripts/verify --full` — adds PostgreSQL integration tests in an isolated Docker container. Run before merge; CI runs it on every push/PR.
- `scripts/test-compose-topology` — Compose topology assertions (CI).
- `scripts/test-beta-smoke` — read-only check against a running gateway (`PROBEINTERVIEW_BETA_BASE_URL` to override).
- Local startup: `docs/development.md`. Deploy and post-deploy verification: `docs/ops.md`.

## Architecture constraints (hard)

- Monorepo, module-first modular monolith (ADR 0001): backend Python 3.12 + uv + FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic; native WeChat mini program in TypeScript + TDesign.
- PostgreSQL is the source of truth; pgvector data is derived/rebuildable; Redis is not product state. Celery messages carry stable IDs, never private content or full mutable payloads.
- Domain/application code must not import vendor SDKs or another module's repository/ORM model. External services are accessed through ports and infrastructure adapters.
- Actor and public/owner scope filters must be applied before database or vector retrieval.
- Success APIs return typed resources; errors use RFC 9457 Problem Details; async creation returns 202 + Location with Idempotency-Key where retryable.
- Logs must not contain private source text, request bodies, complete prompts/model responses, secrets or tokens.
- Never introduce a new language, framework, database, cloud service or major dependency without an accepted ADR. Discuss with the user first.

## Sources of truth

- `docs/architecture.md` + `docs/adr/` — project-level structure and decisions. ADRs are append-only; superseding requires a new ADR and syncing `docs/architecture.md`.
- `docs/features/<name>.md` — per-feature scope, contracts and acceptance. Keep it consistent with code as you work; it is the only planning artifact for the feature.
- `openspec/` is a frozen archive of the previous process. Do not implement from it or update it; `deliver-probeinterview-mvp` and the old `codex/deliver-probeinterview-mvp` branch are rejected references.
- For UI work, check the relevant visual under `docs/design/visuals/`.

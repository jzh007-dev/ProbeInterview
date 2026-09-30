# ProbeInterview Agent Rules

## Read before working

Before planning or changing this project, read:

1. `docs/architecture.md`
2. `docs/adr/README.md` and the ADRs relevant to the task
3. `openspec/config.yaml`
4. The complete artifacts for the active OpenSpec change
5. For UI work, `docs/design/visuals/README.md` and the relevant visual HTML

## Sources of truth

- OpenSpec is the source of truth for feature scope, requirements, design and tasks.
- `docs/architecture.md` and accepted ADRs are the source of truth for project-level technical decisions.
- Code and tests must remain consistent with the active change. If implementation reveals a required requirement or design change, stop and obtain explicit user confirmation before editing planning artifacts.
- User silence is not confirmation.

`deliver-probeinterview-mvp` is reference-only and no longer an active implementation baseline. It may overlap or conflict with newer changes. Do not reuse its rejected Node/TypeScript backend implementation or infer requirements from that code.

## Architecture constraints

- Use the Monorepo and module-first modular monolith structure defined by ADR 0001.
- Backend code uses Python 3.12, uv, FastAPI, Pydantic 2, SQLAlchemy 2 and Alembic.
- The native WeChat mini program uses TypeScript and TDesign.
- PostgreSQL is the source of truth; pgvector data is derived and Redis is not product state.
- Celery messages carry stable IDs, not private content or complete mutable payloads.
- Domain/application code must not import vendor SDKs or another module's repository/ORM model.
- External services are accessed through ports and infrastructure adapters.
- Actor and public/owner scope filters must be applied before database or vector retrieval.
- Success APIs return typed resources. Errors use RFC 9457 Problem Details.
- Logs must not contain private source text, request bodies, complete prompts/model responses, secrets or tokens.

Do not introduce a new language, framework, database, cloud service or major dependency unless an accepted ADR explicitly allows it. Discuss the decision with the user first, then add or supersede an ADR and synchronize `docs/architecture.md` and `openspec/config.yaml`.

## Change and task discipline

- Work only inside the active change's proposal, specs, design and tasks.
- Tasks must be delivered as testable vertical behavior, not as disconnected controller/service/repository batches.
- Every requirement scenario must have automated coverage before a change is considered complete.
- Do not implement deferred RAG choices such as chunking, embedding dimensions, index types, hybrid retrieval weights or rerank thresholds without a confirmed design in the consuming change.

## Commands

Available setup and focused-check commands:

- backend install: `cd apps/backend && uv sync --frozen --all-groups`;
- mini-program install: `cd apps/miniprogram && npm ci`;
- clean-room skeleton check: `scripts/check-skeleton`;
- backend unit tests: `cd apps/backend && uv run pytest tests/unit`;
- backend format/lint/type checks: `cd apps/backend && uv run ruff format --check migrations src tests && uv run ruff check migrations src tests && uv run mypy`;
- mini-program type check: `cd apps/miniprogram && npm run typecheck`;
- Compose topology check: `scripts/test-compose-topology`;
- running-development beta smoke: `scripts/test-beta-smoke`;
- local API and Worker startup: see `docs/development.md`.

Docker Compose startup and shutdown are documented in `docs/development.md`.
Database migration and the canonical full `scripts/verify` entry do not exist
until later changes implement them. Do not invent substitutes in project
guidance. Keep this section and `openspec/config.yaml` synchronized with
verified commands.

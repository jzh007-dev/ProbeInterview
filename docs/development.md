# Local development

## Prerequisites

- Python 3.12.13 managed by uv 0.11 or newer
- Node.js 26.3.1 and npm 11.16.0
- Docker with Docker Compose

## Install locked dependencies

```bash
cd apps/backend
uv sync --frozen --all-groups

cd ../miniprogram
npm ci
```

## Configure local processes

The checked-in example uses the local actor and deterministic fake adapters. It
contains no cloud credentials.

```bash
cd apps/backend
cp .env.example .env
```

Start PostgreSQL and Redis for host-run backend processes:

```bash
docker compose \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  up --detach --wait postgres redis
```

Before starting the API or Worker, run the one-shot database initializer:

```bash
cd apps/backend
uv run python -m probeinterview.entrypoints.database_initializer
```

The initializer upgrades the configured database to the Alembic head revision.
With the development example's
`PROBEINTERVIEW_DEMO_PROFILE_SEED_ENABLED=true`, it then idempotently creates
the local actor's user, WeChat-shaped identity, and two target profiles. It
does not create a `user_resume` row because no file has been uploaded.

API process:

```bash
cd apps/backend
uv run uvicorn probeinterview.entrypoints.api:create_app --factory --reload
```

Worker process:

```bash
cd apps/backend
uv run python -m probeinterview.entrypoints.worker
```

The API and worker validate configuration before starting. The worker requires
the Redis broker URL from `.env`.

With the host API running, retrieve the persisted local actor's overview:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8000/api/v1/me/overview
```

The development response has the explicit default target profile,
`current_resume: null`, and `recent_scores: []`. File storage, resume upload,
replacement, preview, and download belong to the later simulation feature and
are intentionally unavailable in this change.

## Run the local Compose topology

From the repository root, start the one-shot database initializer plus Caddy,
the API, the Worker, PostgreSQL + pgvector, and Redis:

```bash
docker compose \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  up --build --detach --wait
```

The local gateway listens on `http://127.0.0.1:8080` by default. Override it
with `PROBEINTERVIEW_HTTP_PORT`.

The API and Worker wait for the initializer to exit successfully. Retrieve the
same seeded overview through the gateway:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8080/api/v1/me/overview
```

Runtime health endpoints are available through the gateway:

- `/health/live` reports API process liveness without checking external
  vendors.
- `/health/ready` reports readiness only when PostgreSQL and the task broker
  are available.

API responses include `X-Request-ID`. Errors use RFC 9457
`application/problem+json`; normal logs are structured JSON and omit request
bodies, credentials and complete exception details.

Stop the local topology without deleting its development data:

```bash
docker compose \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  down
```

Run the isolated topology check, which uses a unique Compose project and port
and removes its containers and volumes on exit:

```bash
scripts/test-compose-topology
```

Production uses `compose.production.yaml` with the base file. Before running
it, inject `PROBEINTERVIEW_DOMAIN`, `PROBEINTERVIEW_DATABASE_URL`,
`PROBEINTERVIEW_CELERY_BROKER_URL`, `PROBEINTERVIEW_POSTGRES_PASSWORD`, the
`PROBEINTERVIEW_OSS_*` settings and `PROBEINTERVIEW_BAILIAN_API_KEY` through the
deployment environment or secret management. The production override makes
Caddy the only published service and enables its automatic TLS and HTTP to
HTTPS handling. It explicitly disables the local actor and demo profile seed;
the initializer performs migrations only.

## Focused checks

```bash
scripts/check-skeleton
scripts/test-profile-postgres
scripts/test-compose-topology

cd apps/backend
uv run pytest tests/unit
uv run ruff format --check migrations src tests
uv run ruff check migrations src tests
uv run mypy

cd ../miniprogram
npm test
npm run typecheck
```

This change does not provide a canonical `scripts/verify` entry. Use the
documented focused commands above rather than inventing a replacement.

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

## Run the local Compose topology

From the repository root, start Caddy, the API, the Worker, PostgreSQL +
pgvector and Redis:

```bash
docker compose \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  up --build --detach --wait
```

The local gateway listens on `http://127.0.0.1:8080` by default. Override it
with `PROBEINTERVIEW_HTTP_PORT`.

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
HTTPS handling.

## Focused checks

```bash
scripts/check-skeleton
scripts/test-compose-topology

cd apps/backend
uv run pytest tests/unit
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy

cd ../miniprogram
npm run typecheck
```

The canonical full `scripts/verify` entry is added by task 4.1. Until then, use
the focused commands above rather than inventing a replacement full suite.

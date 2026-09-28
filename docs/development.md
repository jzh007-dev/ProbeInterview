# Local development

## Prerequisites

- Python 3.12.13 managed by uv 0.11 or newer
- Node.js 26.3.1 and npm 11.16.0
- Docker with Docker Compose for the runtime topology added by task 2.1

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
the Redis broker URL from `.env`; the complete local database, broker, gateway,
and worker topology is established by task 2.1.

## Focused checks

```bash
scripts/check-skeleton

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

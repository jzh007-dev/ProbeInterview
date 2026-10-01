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

The checked-in example uses WeChat authentication with the deterministic fake
adapter and fake cloud adapters. It contains no cloud credentials.

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
the demo user, its WeChat identity bound to the configured
`PROBEINTERVIEW_WECHAT_APP_ID`, two target profiles, default knowledge upload
policy, and `knowledge.submit_public` capability. It does not create a
`user_resume` or knowledge source row because no file has been uploaded.

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

Business APIs require a bearer session. With the deterministic fake WeChat
adapter, exchange the seeded demo identity's login code (its openid) for a
session and reuse the token in the examples below:

```bash
TOKEN=$(curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"code": "oProbeInterviewDemoOpenId01"}' \
  http://127.0.0.1:8000/api/v1/auth/wechat/exchanges \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')
```

Any unknown code instead returns `registration_required`, which mirrors the
mini program's first-login registration flow; the fake adapter also maps
`invalid-code`, `used-code`, `timeout-code`, and `unavailable-code` to its
rejected and unavailable paths.

With the host API running, retrieve the persisted demo actor's overview:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer ${TOKEN}" \
  http://127.0.0.1:8000/api/v1/me/overview
```

The development response has the explicit default target profile,
`current_resume: null`, and `recent_scores: []`. File storage, resume upload,
replacement, preview, and download belong to the later simulation feature and
are intentionally unavailable in this change.

The same seeded actor has `knowledge.submit_public` and a default knowledge
upload policy of two successfully stored files per Shanghai calendar day and
100 effective sources. From the repository root, upload one Markdown file
through the deterministic fake object storage:

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Idempotency-Key: local-knowledge-1' \
  -F 'scope=PRIVATE' \
  -F 'file=@docs/architecture.md;type=text/markdown' \
  http://127.0.0.1:8000/api/v1/me/knowledge-sources
```

Repeating the same command returns the same source without storing or counting
a second copy. List only the current actor's stored records and quota:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer ${TOKEN}" \
  http://127.0.0.1:8000/api/v1/me/knowledge-sources
```

These endpoints store the original bytes and return
`PENDING_EXTRACTION`; they do not parse Markdown or enqueue a Celery task.

## Optional Alibaba OSS smoke test

Normal development, unit tests and Compose use
`PROBEINTERVIEW_OBJECT_STORAGE_ADAPTER=fake`. To verify the real adapter
against the already provisioned private test bucket, copy
`infra/compose/.env.oss.example` to the ignored
`infra/compose/.env.oss` file and fill the RAM access key values:

```text
PROBEINTERVIEW_OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
PROBEINTERVIEW_OSS_BUCKET=probeinterview-test-kb-bucket
PROBEINTERVIEW_OSS_ACCESS_KEY_ID=<RAM access key id>
PROBEINTERVIEW_OSS_ACCESS_KEY_SECRET=<RAM access key secret>
```

Do not commit those values or put them in command history. The ignored file is
consumed only when the explicit OSS Compose override is selected:

```bash
docker compose \
  --env-file infra/compose/.env.oss \
  --project-directory infra/compose \
  -f infra/compose/compose.yaml \
  -f infra/compose/compose.oss.yaml \
  up --build --detach --wait
```

Confirm the running API reports the `oss` adapter without printing credentials,
then run the opt-in write/delete smoke test with the same variables loaded:

```bash
cd apps/backend
uv run pytest -m oss_smoke
```

The smoke test writes one uniquely named object below
`knowledge-sources/` and deletes it before returning. If the process is
interrupted after the write, remove only that unique smoke object through the
existing bucket administration workflow. This project does not create,
configure, or change the bucket or its RAM authorization.

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

The API and Worker wait for the initializer to exit successfully. Exchange a
session for the seeded demo identity through the gateway and retrieve the same
overview:

```bash
TOKEN=$(curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"code": "oProbeInterviewDemoOpenId01"}' \
  http://127.0.0.1:8080/api/v1/auth/wechat/exchanges \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl --fail --silent --show-error \
  -H "Authorization: Bearer ${TOKEN}" \
  http://127.0.0.1:8080/api/v1/me/overview
```

The fake-backed knowledge-source examples above also work through the gateway
by replacing port `8000` with `8080`.

After rebuilding the local topology, run the beta smoke against the same
gateway used by the WeChat developer tools:

```bash
scripts/test-beta-smoke
```

This read-only acceptance check rejects custom-component WXSS selectors that
the WeChat compiler does not allow, runs the upload-page client/component tests
and TypeScript check, exchanges a bearer session for the seeded demo identity,
and verifies that the running API exposes the knowledge-source route and
returns a safe typed owner collection. It does not upload or change the demo
actor's quota. It requires the gateway to run the `wechat` authentication mode
with the `fake` WeChat adapter (the development default); gateways using the
real adapter cannot serve the deterministic login code. The isolated
`scripts/test-compose-topology` command covers the protected mount point,
upload, idempotent replay and listing without polluting development data.
Override the gateway only when intentionally testing another environment:

```bash
PROBEINTERVIEW_BETA_BASE_URL=https://beta.example.invalid \
  scripts/test-beta-smoke
```

If the WeChat developer tools fail to start the mini program with
`module 'fixtures/home-knowledge.js' is not defined`, the tool's
"filter unused files" option has dropped a runtime module: keep
`ignoreDevUnusedFiles` / `ignoreUploadUnusedFiles` disabled (as checked in
`project.config.json`), then clear the tool cache and recompile. The home tab
intentionally ships the fixture content until real topic data lands.

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
HTTPS handling. It explicitly disables the demo profile seed; the initializer
performs migrations only.

## Focused checks

```bash
scripts/check-skeleton
scripts/test-profile-postgres
scripts/test-knowledge-source-postgres
scripts/test-compose-topology
scripts/test-beta-smoke

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

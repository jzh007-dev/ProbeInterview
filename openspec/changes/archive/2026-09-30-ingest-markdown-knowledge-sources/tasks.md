# Tasks

## 1. Persist upload identity, policy, and source truth

- [x] 1.1 Add the `knowledge.source` module skeleton and an Alembic revision for `user_capabilities`, `knowledge_upload_policies`, `knowledge_sources`, and `knowledge_source_versions`, including policy backfill, constraints/indexes, identity capability loading, and idempotent development seed data; add PostgreSQL migration/seed tests for clean upgrade/downgrade, two-user isolation prerequisites, default 2/day and 100-effective policies, and `knowledge.submit_public`, then verify with a focused `scripts/test-knowledge-source-postgres` command and `cd apps/backend && uv run pytest tests/unit/test_actor_context.py`.

## 2. Accept and persist a private Markdown source

- [x] 2.1 Add locked multipart/storage dependencies, the provider-neutral `ObjectStorage` port and deterministic fake, bounded `.md`/size/UTF-8/nonempty/NUL validation, WeChat-compatible optional `original_filename` handling with multipart-name fallback, `UPLOADING` reservation and compensation flow, and `POST /api/v1/me/knowledge-sources` returning typed `202 + Location` with a stored `PRIVATE` version in `PENDING_EXTRACTION`; cover the exact `500 * 1024` boundary, invalid extension/text/scope/original filename, original-name override and fallback, storage failure, finalization failure, secret-field exclusion, and absence of parsing/Celery calls, then verify with `cd apps/backend && uv run pytest tests/unit/knowledge_source tests/integration/knowledge_source -k 'private_upload or validation or compensation or original_filename'`.

## 3. Close quota, idempotency, and duplicate races

- [x] 3.1 Implement database-policy admission using the `Asia/Shanghai` quota day, `UPLOADING` reservations, effective-source cap, actor/key/request-digest replay and conflict, and owner/scope/SHA-256 duplicate reuse; add PostgreSQL concurrency tests proving two requests cannot exceed the last daily or total slot and tests proving invalid/failed/replayed/duplicate uploads do not consume another success, then verify with `scripts/test-knowledge-source-postgres` and `cd apps/backend && uv run pytest tests/unit/knowledge_source -k 'quota or idempotency or duplicate'`.

## 4. Authorize public intent and expose the owner collection

- [x] 4.1 Enforce `knowledge.submit_public` before mutation and implement `GET /api/v1/me/knowledge-sources` with owner-only counts/items, `stored_at DESC, id DESC` ordering, quota context, and safe typed fields; cover allowed/forbidden `PUBLIC`, same-content different-scope behavior, empty list, two-actor non-disclosure including `PUBLIC` intent, stable ordering, and RFC 9457 status/code mapping, document reproducible local `curl` upload/list examples in `docs/development.md`, then verify with `cd apps/backend && uv run pytest tests/unit/knowledge_source tests/integration/knowledge_source -k 'public or list or owner'` and execute the documented fake-backed examples.

## 5. Wire and verify the real Alibaba OSS adapter

- [x] 5.1 Implement the Alibaba OSS infrastructure adapter and typed adapter selection using the existing endpoint/bucket/access-key settings, private deterministic single-prefix `knowledge-sources/{version_id}.md` object keys, checksum/content-type metadata, safe exception mapping, delete compensation, and production no-fake/no-fallback validation; add shared fake/OSS contract tests with an opt-in smoke marker that writes and deletes a unique object in `probeinterview-test-kb-bucket`, document configuration and cleanup without exposing secrets or provisioning the bucket, update the lockfile, then verify with `cd apps/backend && uv sync --frozen --all-groups`, `cd apps/backend && uv run pytest tests/unit/knowledge_source -k storage`, and—only when OSS environment variables are intentionally loaded—`cd apps/backend && uv run pytest -m oss_smoke`.

## 6. Deliver the native upload and management page

- [x] 6.1 Replace `pages/upload` with the TDesign-aligned knowledge-material flow from `docs/design/visuals/home-overview.html`: collection loading/empty/error states, one Markdown selection, visible filename/size, transmission of the selected original filename despite WeChat temporary upload paths, default `private` scope selector, upload lock, success refresh, quota-disabled state, reverse-ordered owner records, “正在提取知识点”, and `public`/`private` tags, with no private-question-bank card, fake completion, node count, or direct OSS credential use; add mini-program model/client/component/navigation/compiler-contract tests for every state, original-filename mapping and Problem Details mapping, then verify with `cd apps/miniprogram && npm test && npm run typecheck`, `cd apps/backend && uv run ruff format --check migrations src tests && uv run ruff check migrations src tests && uv run mypy`, `scripts/test-compose-topology`, and the read-only `scripts/test-beta-smoke`.

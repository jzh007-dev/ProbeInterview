# Proposal

## Why

The upload tab is still an inert placeholder, so users cannot contribute the Markdown
sources that every later knowledge parsing, association, review, and retrieval change
depends on. This change establishes the smallest durable source-ingestion loop: validate and
store a source, persist its owner and intended visibility, and show the owner that the source
is waiting for future knowledge extraction.

## What Changes

- Replace the upload-tab placeholder with a native mini-program upload and management page
  for Markdown knowledge sources only; private-question-bank upload remains out of scope.
- Add an authenticated, idempotent upload API that accepts one UTF-8 `.md` file strictly
  smaller than `500 * 1024` bytes, a `PRIVATE` or `PUBLIC` scope defaulting to `PRIVATE`,
  and optional original-filename metadata for clients whose multipart transport rewrites
  the file part name.
- Store accepted source bytes in Alibaba Cloud OSS through an `ObjectStorage` port and persist
  provider-neutral source/version metadata, checksums, owner scope, and
  `PENDING_EXTRACTION` processing state in PostgreSQL.
- Add per-user database-backed upload policy with a default limit of two successfully stored
  files per `Asia/Shanghai` calendar day and at most 100 effective sources.
- Require `knowledge.submit_public` for `PUBLIC` submissions while keeping every upload
  record owner-only in this change; `PUBLIC` expresses future publication intent, not current
  visibility.
- Return the current actor's records in reverse upload order with quota context, and render
  processing records as “正在提取知识点” with `public`/`private` labels.
- Make duplicate content and retry behavior deterministic: an idempotent retry does not
  create or count another source, and the same owner/scope/SHA-256 reuses the existing
  effective source.
- Keep Markdown parsing, Celery processing, node counts, publication/review, deletion,
  replacement, scope changes, cloud resource provisioning, and non-Markdown formats out of
  scope.

## Capabilities

### New Capabilities

- `knowledge-source-ingestion`: Authenticated Markdown validation, OSS-backed source/version
  persistence, per-user quota enforcement, public/private submission authorization,
  owner-only listing, and the upload-management page behavior.

### Modified Capabilities

- `my-profile-overview`: Revise the five-tab placeholder requirement so the upload tab may be
  implemented by the new knowledge-source ingestion capability while the unrelated review
  and simulation tabs remain placeholders.

## Impact

- Backend: introduces the `knowledge-source` module, Alembic tables for source/version and
  upload policy state, identity capability persistence/resolution, multipart API contracts,
  an OSS infrastructure adapter, and owner-scoped repositories.
- API: adds current-actor upload and list resources under `/api/v1/me/knowledge-sources`,
  reusing `Idempotency-Key`, typed success resources, RFC 9457 Problem Details, and a
  backward-compatible `original_filename` multipart field used by the native mini program.
- Mini program: replaces `pages/upload` placeholder content with file selection, scope
  selection, upload progress/result states, quota feedback, and the owner upload list while
  preserving native tab navigation.
- Dependencies/configuration: adds the locked multipart parser and Alibaba Cloud OSS Python
  SDK required by the real infrastructure adapter; development/test retain the deterministic
  fake adapter required by ADR 0006, and production cannot fall back to it.
- External systems: consumes an existing OSS bucket through configuration. Creating ECS,
  VPC, RAM roles, buckets, Terraform/ROS resources, or other cloud infrastructure belongs to
  a later change.

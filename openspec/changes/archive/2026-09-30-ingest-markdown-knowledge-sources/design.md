# Design

## Context

See [proposal.md](proposal.md) for motivation and the two delta specs for observable
behavior. The current upload tab is a native mini-program placeholder, `ActorContext`
already isolates the current local actor, PostgreSQL/Alembic are available, and foundation
settings already select `fake` or `oss` object storage. There is not yet an `ObjectStorage`
port implementation, persisted capability set, knowledge-source schema, multipart
dependency, or OSS SDK.

This change follows the module-first modular monolith and dependency rules in
[ADR 0001](../../../docs/adr/0001-project-structure-and-technology-stack.md), PostgreSQL source of
truth in [ADR 0002](../../../docs/adr/0002-data-and-vector-storage.md), API/identity rules in
[ADR 0004](../../../docs/adr/0004-api-and-identity-boundary.md), and adapter verification strategy
in [ADR 0006](../../../docs/adr/0006-external-adapters-and-verification-strategy.md). It does not
enqueue a Celery job: [ADR 0003](../../../docs/adr/0003-asynchronous-job-architecture.md) applies
when the later parsing change introduces asynchronous work.

## Goals / Non-Goals

**Goals:**

- Add one closed vertical path from bounded Markdown selection through owner-scoped
  metadata, object storage, quota accounting, and upload-list presentation.
- Keep the application/domain layers independent of Alibaba OSS and keep persisted source
  references portable across storage providers.
- Make authorization, idempotency, duplicate-content reuse, and quota concurrency explicit
  enough to test against PostgreSQL.
- Leave a durable `PENDING_EXTRACTION` handoff point for the later parsing change.

**Non-Goals:**

- No Markdown AST parsing, raw HTML policy, knowledge-node extraction, Celery task, retry
  scheduler, publication/review workflow, or node count.
- No source delete, replacement, scope edit, download, object preview, presigned URL, or
  multi-version UI.
- No OSS bucket/RAM/network provisioning and no ECS, Lambda, VPC, Terraform, ROS, or other
  runtime-platform choice.
- No private-question-bank upload and no non-Markdown extension mechanism in this change.

## Decisions

### 1. Add a bounded `knowledge_source` module and extend identity through its contract

Backend code lives under a new `probeinterview.knowledge.source` module with domain values,
application use cases, API contracts/router, repository implementations, and storage
adapters. It accepts `ActorContext` from `identity/access`; it does not import identity ORM
models or repositories. The identity module owns persisted capabilities and resolves them
into `ActorContext.capabilities`.

The application layer depends on:

- a knowledge-source repository/unit-of-work port;
- a clock that can produce UTC time and the corresponding `Asia/Shanghai` quota day;
- an `ObjectStorage` port supporting bounded byte upload and best-effort object deletion.

The Alibaba SDK is imported only by the OSS infrastructure adapter. The deterministic fake
implements the same port for unit, integration, and Compose end-to-end tests.

**Alternative considered:** Put uploads in the existing profile module. A knowledge source
has its own ownership, scope, versions, processing lifecycle, and future consumers, so
profile would become an unrelated data owner and later modules would need to reach through
it.

### 2. Use four tables; source/version rows are the business record

The Alembic revision adds the following tables. UUID primary keys and timestamps follow
existing project conventions; all timestamps are UTC.

| Table | Key fields and constraints |
| --- | --- |
| `user_capabilities` | `user_id`, `capability`; composite primary key; FK to `users`; identity-owned |
| `knowledge_upload_policies` | `user_id` PK/FK, `daily_success_limit` default 2, `effective_source_limit` default 100, `quota_timezone` fixed to `Asia/Shanghai`, timestamps; positive-value checks |
| `knowledge_sources` | `id`, `owner_user_id`, `creator_user_id`, `scope`, `ingestion_status` (`UPLOADING`, `STORED`, `FAILED`), `content_sha256`, `quota_day`, `idempotency_key`, `request_digest`, nullable `current_version_id`, `created_at`, nullable `stored_at`, `updated_at`, nullable safe `failure_code` |
| `knowledge_source_versions` | `id`, `source_id`, `version_number`, `original_filename`, normalized `media_type`, `byte_size`, `content_sha256`, provider-neutral `object_key`, `storage_status` (`UPLOADING`, `STORED`, `FAILED`), nullable `processing_status` (`PENDING_EXTRACTION` after storage), timestamps |

Constraints/indexes include:

- unique `(owner_user_id, idempotency_key)` so a key is bound to one actual source-creation
  command for that actor;
- partial unique `(owner_user_id, scope, content_sha256)` for `UPLOADING` or `STORED`
  sources, closing the concurrent duplicate race;
- unique `(source_id, version_number)`; this change only creates version 1;
- indexes for `(owner_user_id, stored_at DESC, id DESC)`, quota-day counts, and source/version
  joins;
- `current_version_id` must reference a version belonging to the same source, enforced by a
  composite database constraint rather than application convention alone.

An upload that finds the same owner/scope/SHA-256 before creating a row returns that source.
Because this path has no new side effect, its fresh idempotency key is not materialized.
Keys bound to actual source creation retain the ADR 0004 rule: the same digest replays the
result and a different digest returns conflict. This avoids a separate
`knowledge_upload_commands` operational ledger while preserving durable source truth.

Every user must have a `knowledge_upload_policies` row. The migration backfills existing
users with defaults; user-provisioning code must create the policy in the same transaction.
Missing policy is treated as an integrity/configuration error, not as an untracked in-memory
default. The development seed grants its existing actor `knowledge.submit_public`
idempotently. Production capabilities remain explicit data, not an environment toggle.

**Alternative considered:** A `knowledge_upload_commands` table. It would give a normalized
receipt for every no-op duplicate request, but this change has no independent command
lifecycle, queue, or user-visible command resource. Adding it now would duplicate source
state and expand retention/cleanup policy. If a later multi-step workflow needs command
history, it can introduce that table with its own requirements.

**Alternative considered:** Store quota counters directly on the user. Derived counts from
stored/reserved source rows are auditable, cannot drift from source truth, and allow policy
limits to change without repairing a counter.

### 3. Reserve quota in PostgreSQL before external I/O

Validation and SHA-256 calculation happen before any database or OSS mutation. For a new
source, the application performs:

1. Start a transaction and lock the actor's `knowledge_upload_policies` row.
2. Check an existing idempotency binding, then owner/scope/SHA-256 duplicate.
3. Count the actor's `STORED` daily/effective sources for returned usage and count both
   `UPLOADING` and `STORED` rows for admission. This treats an in-flight row as a temporary
   reservation so concurrent requests cannot oversubscribe the last slot.
4. Insert source/version rows as `UPLOADING` with a deterministic object key, then commit.
5. Write bytes through `ObjectStorage`.
6. In a new transaction, transition both rows to `STORED`, set
   `processing_status=PENDING_EXTRACTION`, set `current_version_id` and `stored_at`, and
   return quota computed from `STORED` rows.

On a storage error, the application marks the reservation `FAILED`; failed rows are not
effective, not listed, and do not consume returned quota. If final database commit fails
after OSS write, it attempts object deletion and marks the reservation failed when possible.
The deterministic key and the persisted `UPLOADING` reservation make a retry with the same
idempotency key recoverable without creating a second object or source.

The reservation phase uses database uniqueness plus policy-row locking, not a process-local
mutex, so it remains correct with multiple API processes. A short-lived concurrent request
can be rejected while the last slot is reserved and later fails; the client may retry with
the same key.

**Alternative considered:** Hold a database transaction open during the OSS request. It
reduces one intermediate state but holds locks across network latency and still cannot make
PostgreSQL and OSS atomic if the process dies.

### 4. Validate bytes deterministically without parsing Markdown

`POST /api/v1/me/knowledge-sources` is multipart with `file`, optional `scope`, and optional
`original_filename`; the `Idempotency-Key` header is required. Native WeChat
`wx.uploadFile` supplies a temporary multipart filename, so the mini program sends the
selected file's name through `original_filename`. Browser and curl clients remain
compatible: when the field is absent, the API uses the multipart file part name. The
boundary reads at most `500 * 1024` bytes by requesting one extra byte and rejects the
request as soon as the upper bound is reached. It then:

- chooses `original_filename` when present, otherwise the multipart part name, then
  normalizes it to its basename, enforces a safe length, and checks `.md`
  case-insensitively;
- rejects zero bytes, invalid UTF-8, and any NUL byte;
- computes SHA-256 over the exact original bytes;
- normalizes persisted media type to `text/markdown; charset=utf-8` instead of trusting a
  client MIME label;
- validates scope before capability, quota, database, or OSS mutation.

No Markdown parser is invoked, so syntactically unusual but valid UTF-8 `.md` is accepted.
The later parsing change owns Markdown grammar, HTML/attachment policy, and processing
failures.

`python-multipart` is added as the locked FastAPI multipart dependency. Request and error
logs may contain request id, actor id, source/version id, byte count, scope, status, duration,
and safe error code; they must not contain file bytes, decoded text, full request bodies,
credentials, or OSS authorization material.

**Alternative considered:** Parse Markdown during upload. That would silently pull parsing
policy and failure states from the deferred `parse-markdown-knowledge-sources` change into
this one.

### 5. Expose one owner-scoped collection API

Both operations require an `ActorContext`:

```text
POST /api/v1/me/knowledge-sources
  multipart: file, scope=PRIVATE|PUBLIC (default PRIVATE), original_filename (optional)
  header: Idempotency-Key
  -> 202 + Location: /api/v1/me/knowledge-sources
  -> KnowledgeSourceUploadResource { source, quota }

GET /api/v1/me/knowledge-sources
  -> 200
  -> KnowledgeSourceCollectionResource { quota, items }
```

`source`/`items[]` expose only `id`, `original_filename`, `scope`,
`processing_status`, and `uploaded_at`. `quota` exposes `timezone`, `daily_limit`,
`daily_used`, `effective_source_limit`, and `effective_source_count`. The collection query
applies `owner_user_id = actor.actor_id` before selecting or counting and orders
`stored_at DESC, id DESC`. It only returns `STORED` rows with
`PENDING_EXTRACTION`.

Stable Problem Details codes distinguish invalid file (`400` or `413`), missing
authentication (`401`), missing public-submit capability (`403`), idempotency conflict or
effective-source limit (`409`), daily quota (`429`), and unavailable storage (`503`).
Problem responses never include an OSS exception or object key.

`PUBLIC` does not add a public read predicate in this change. It is a submission intent
checked against `knowledge.submit_public`; both list and counts remain owner-only.

**Alternative considered:** Add detail/download endpoints. The page only needs the
collection and the upload response, while exposing original bytes or storage locations
would add authorization and retention surface without a current user journey.

### 6. Use a real private OSS adapter plus the deterministic fake

The `ObjectStorage` port accepts a provider-neutral object key, exact bytes, normalized
content type, and checksum metadata, and returns no public URL. The OSS adapter uses the
accepted Alibaba Cloud OSS SDK and existing typed settings:

- `PROBEINTERVIEW_OSS_ENDPOINT`;
- `PROBEINTERVIEW_OSS_BUCKET`;
- `PROBEINTERVIEW_OSS_ACCESS_KEY_ID`;
- `PROBEINTERVIEW_OSS_ACCESS_KEY_SECRET`.

The intended manually provisioned test bucket is `probeinterview-test-kb-bucket` in
Shanghai. Bucket creation, ACL/RAM policy, lifecycle rules, and infrastructure-as-code are
not performed by this change. The adapter assumes a private existing bucket and uses the
single-prefix key `knowledge-sources/{version_id}.md`. The version UUID is globally unique;
environment, owner, source, and version relationships remain authoritative PostgreSQL
metadata instead of being duplicated into virtual OSS directory levels. The database stores
only the provider-neutral object key, never endpoint, bucket name, URL, or credentials.

Development may explicitly select `object_storage_adapter=oss` for a manual real-bucket
smoke test. Automated tests and the default local Compose path use the deterministic fake.
Production keeps ADR 0006 startup validation and cannot select or fall back to fake; invalid
or missing OSS configuration fails before serving requests.

Contract tests run the same put/delete/checksum cases against fake and an opt-in OSS suite.
The normal verification path does not require network access or local cloud credentials.

**Alternative considered:** Call OSS HTTP APIs directly. The official SDK owns request
signing, canonicalization, retries, and service error decoding; hand-written signed HTTP
would be security-sensitive infrastructure code with no product benefit.

### 7. Replace only the upload page shell and model every visible state

The affected mini-program route is `pages/upload`, following the upload card/list direction
in `docs/design/visuals/home-overview.html` while removing the illustrated private-question-
bank card and all fake completed/node-count records.

The page state model is:

- `loading`: collection skeleton or progress, with no hard-coded record flash;
- `empty`: upload affordance, Markdown/size guidance, and real zero-count quota;
- `selecting`: selected filename/size and scope selector, default `private`;
- `uploading`: submit disabled and one in-flight request with a generated idempotency key;
- `success-refresh`: preserve returned item immediately, then refresh collection/quota;
- `error`: retain a correctable selection when safe and map Problem Details codes to
  actionable copy;
- `quota-exhausted`: existing records remain visible and new submit is disabled.

Each item shows filename, “正在提取知识点”, upload time, and a lowercase `public` or `private`
tag. There is no success/node-count branch until a later parsing change introduces those
states. The API client uses the existing base URL and actor behavior; it does not read OSS
credentials or upload directly to a public OSS URL. It sends the selected file's `name` as
`original_filename` because the WeChat upload transport may expose only a temporary hashed
multipart filename to the server.

**Alternative considered:** Upload directly from the mini program to OSS. That would require
temporary credential/presigned-policy issuance, move validation and quota admission across
two systems, and broaden this MVP beyond the existing authenticated API boundary.

### 8. Verify scenarios at the boundary where they can fail

- Domain/application unit tests cover byte validation, scope authorization, Shanghai-day
  calculation, idempotent replay/conflict, duplicate reuse, storage failure compensation,
  and safe Problem Details mapping.
- PostgreSQL integration tests migrate from an empty database and prove policy backfill,
  capability resolution, partial uniqueness, owner isolation, ordering, and two concurrent
  uploads contending for the last quota slot.
- API tests exercise real multipart requests for size boundaries, invalid UTF-8/NUL,
  `PRIVATE` default, `PUBLIC` authorization, original-filename override/fallback and path
  normalization, typed `202`/`200` resources, headers, and secret field exclusion.
- Storage contract tests exercise deterministic fake behavior by default and provide an
  explicitly configured OSS smoke path that writes and deletes a uniquely prefixed object.
- Mini-program tests cover loading, empty, selection/default scope, uploading lock, refresh,
  scope labels, quota disabled state, original-filename transmission, and error rendering.

## Risks / Trade-offs

- [PostgreSQL and OSS cannot share one atomic transaction] → Persist a deterministic
  reservation before upload, use idempotent object keys, compensate failed finalization, and
  make same-key retry recover the reservation.
- [A process can die with an `UPLOADING` reservation or orphan object] → Keep it invisible
  and uncounted as successful, recover it on the same-key retry, log safe identifiers for
  diagnosis, and leave scheduled stale-reservation/orphan cleanup to a later operational
  change rather than adding an undeclared worker here.
- [Temporary reservations can reject a concurrent request that would fit after failure] →
  Prefer never exceeding quota; return a stable retryable quota response and release failed
  reservations promptly.
- [No command table means a no-op content duplicate does not retain its fresh idempotency
  key] → Duplicate identity is already stable by owner/scope/SHA-256; only keys that create
  a source are durably bound. Introduce a generic command ledger later only if independent
  command history becomes a requirement.
- [Manual OSS configuration can drift] → Fail startup for invalid production settings,
  keep an opt-in real-adapter smoke test, and defer bucket/IAM provisioning to the dedicated
  cloud change.
- [The page can remain in processing indefinitely] → Deliberately label it “正在提取知识点”
  and do not imply completion; the parsing change will own state progression.

## Migration Plan

1. Add and lock `python-multipart` plus the Alibaba OSS SDK; implement the storage port,
   deterministic fake, real adapter, and typed startup selection without changing the
   default automated-test adapter.
2. Apply one Alembic revision creating the four tables, constraints, indexes, and policy
   rows for existing users. Update the development seed to grant
   `knowledge.submit_public`; verify repeated seeding is idempotent.
3. Deploy backend upload/list behavior and verify fake-backed integration first. In an
   environment intentionally using real OSS, configure the existing private bucket and run
   the unique-prefix write/delete smoke test before enabling the page.
4. Deploy the mini-program upload page after the API is available. Older mini-program
   versions continue to show the inert shell, so no backward API compatibility shim is
   required.

Application rollback may stop routing the new endpoints and restore the upload shell while
leaving tables and objects intact. Database downgrade is safe only before stored sources
exist, or after exporting the object keys and deliberately cleaning corresponding OSS
objects; otherwise prefer a forward fix so durable source references are not discarded.

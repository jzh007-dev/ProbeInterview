# Design

## Context

See `proposal.md` for motivation and `specs/my-profile-overview/spec.md` for observable behavior.

The repository currently provides typed runtime settings, FastAPI request/error foundations, PostgreSQL readiness checks, a development-only `local_actor_enabled` flag, and one placeholder mini-program page. It does not yet provide `ActorContext`, SQLAlchemy session/model infrastructure, Alembic files, business tables, database initialization, user-facing APIs, or mini-program request/state tests.

This change follows the module-first monolith and technology choices in `docs/architecture.md`, ADR 0001, and ADR 0004. It uses the source/object-reference boundary from ADR 0002, deployment/configuration boundaries from ADR 0005, and external-adapter boundary from ADR 0006. No vendor SDK, new database, file store, language, framework, or production dependency is introduced.

## Goals / Non-Goals

**Goals:**

- Establish the smallest reusable identity and persistence path needed by a real owner-scoped page.
- Keep account/identity data separate from candidate target and resume data without allowing cross-module ORM imports.
- Make local Compose startup migrate and seed the database deterministically, while keeping production free of demo data.
- Return one explicit default target profile and an optional current resume display record through a stable typed resource.
- Define a storage-provider-neutral current-resume metadata format without requiring an object-storage resource in this change.
- Implement the referenced “我的” composition with testable loading, success, no-resume, empty-history, and error states.
- Preserve named UI action seams and five tab routes without implementing their future behavior.

**Non-Goals:**

- Authentication tokens, WeChat code exchange, registration, sessions, refresh, logout, or account lifecycle.
- Target-profile creation, editing, deletion, selection, or switching.
- Resume upload, replacement command, preview/download, OSS or local-file adapter implementation, content storage, parsing, version history, or cleanup.
- Interview history persistence, score aggregation, charting, or settings persistence.
- Pixel-identical recreation of the standalone HTML renderer; the mini program reuses its hierarchy, spacing, color, and card direction within native/TDesign constraints.

## Decisions

### 1. Split identity/access from candidate profile

Backend code will add two module boundaries:

- `identity/access` owns `ActorContext`, actor resolution, `users`, and `wechat_identities`. It exposes an application-level current-user query contract containing only account display fields.
- `candidate/profile` owns `candidate_profiles`, `user_resume`, the owner-scoped overview query, response composition, and the `/api/v1/me/overview` route.

The profile application service receives `ActorContext`, calls the identity application contract for display data, and reads profile-owned data through a profile repository. Neither module imports the other module's ORM model or repository. Shared engine/session construction and transaction lifecycle live under platform persistence infrastructure.

The later simulation/interview upload workflow will call a candidate/profile application contract to replace the user's current resume only after its chosen storage adapter has durably accepted the file. The interview module does not own or directly mutate the profile ORM model.

This follows ADR 0001 and ADR 0004 while avoiding both a global horizontal “user repository” and a single identity module that accumulates candidate-specific concepts.

**Alternative considered:** Put all four tables and the endpoint in identity/access. This is initially shorter, but target roles and resumes are interview-preparation state rather than identity and would make later upload/interview changes depend on an oversized identity module.

### 2. Resolve local actors from typed process configuration, never request headers

Add `local_actor_id: UUID | None` to typed settings. When `local_actor_enabled` is true in development/test, startup requires this ID and registers a local provider that returns `ActorContext(actor_id, capabilities=frozenset())`. When no provider resolves an actor, the API dependency returns a stable `401` Problem Details response.

The existing production validation continues to reject `local_actor_enabled=true`; the provider factory also refuses to construct a local provider for production as defense in depth. Tests select different actors by constructing separate app instances with different settings, not by sending arbitrary identity headers.

**Alternative considered:** An `X-Actor-ID` debug header. ADR 0004 explicitly excludes arbitrary debug headers, and such a header could leak into production assumptions.

### 3. Add a PostgreSQL-first schema with explicit current/default constraints

The first Alembic revision creates:

| Table | Important fields and constraints |
|---|---|
| `users` | UUID primary key, `nickname`, `avatar_url`, created/updated timestamps |
| `wechat_identities` | UUID primary key, `user_id` foreign key, `app_id`, `openid`, nullable `unionid`, unique `(app_id, openid)`; no `session_key` column |
| `candidate_profiles` | UUID primary key, `user_id` foreign key, `target_role`, non-negative `relevant_experience_months`, `is_default`, timestamps; partial unique index allowing at most one default per user |
| `user_resume` | UUID primary key, unique `user_id` foreign key, `original_file_name`, `media_type`, non-negative `size_bytes`, 64-character `content_sha256`, unique non-blank `storage_object_key`, positive `revision`, `uploaded_at`, `updated_at` |

UUIDs are generated by the application so stable IDs can cross process and test boundaries without database-specific ID allocation. Foreign keys use restrictive deletion in this change because account deletion behavior is not defined. The overview query requires an explicit default profile; absence maps to `409 profile_overview_incomplete` rather than guessing from insertion order.

`user_resume` stores metadata only and exists only after a future upload workflow has successfully committed a real stored object. `storage_object_key` is a logical, provider-neutral locator such as `resumes/<user-id>/<resume-id>/<revision>.pdf`; the configured storage adapter maps it to OSS or another backend. The database stores neither PDF bytes, a permanent public URL, provider name, credentials, nor signed access parameters.

The later simulation/interview upload change will create or update the single current row, increment `revision`, and arrange deletion of the superseded object after the new database state commits. At interview start, the interview module must copy an immutable resume snapshot or immutable content reference into its configuration snapshot; it must not rely only on the mutable current-resume row.

**Alternative considered:** Store `professional_title`, years, and a resume URL directly on `users`. That cannot represent multiple interview targets, mixes account and candidate state, makes the single-current-resume invariant implicit, and leaks storage/access concerns into the account record.

**Alternative considered:** Create resume version/history rows now. No current behavior consumes them, and real retention/delete rules require the future upload and interview-snapshot design.

**Alternative considered:** Persist an OSS URL or provider-specific bucket/key pair. The project has no OSS resource yet, permanent URLs are unsuitable for private files, and provider-specific columns would violate the adapter boundary.

### 4. Use explicit database initialization plus idempotent development seed

Alembic configuration and metadata wiring live in `apps/backend`. A database-initialization entrypoint runs `upgrade head`, then conditionally executes an idempotent development seed when `demo_profile_seed_enabled=true`.

The seed uses deterministic UUIDs and upserts one display user, one WeChat identity with WeChat-shaped `app_id`/`openid`/optional `unionid`, and multiple target profiles with exactly one default. It intentionally creates no `user_resume` row because no upload or file storage has occurred. It contains no token or `session_key`. A second actor and an optional resume row with a test-only logical object key are created only in automated test fixtures.

The local Compose topology adds a one-shot database initializer and makes API/Worker startup depend on its successful completion. Production sets demo seeding false; typed validation rejects enabling demo seed in production. Direct host development documents the equivalent migration and seed commands before starting the API.

**Alternative considered:** Seed inside the migration. This would put development-only product data into every environment and make rollback/data ownership unclear.

**Alternative considered:** Seed on every API request or API lifespan. That creates process races with the Worker and hides migration failures behind application startup.

### 5. Compose the overview through owner-scoped repositories

Repository methods accept `actor_id` explicitly and include it in every identity/profile/resume predicate. The profile application service performs:

1. Resolve `ActorContext`.
2. Read current-user display data through the identity query contract scoped to `actor_id`.
3. Read the default candidate profile scoped to the same `actor_id`.
4. Read the optional current resume scoped to the same `actor_id`.
5. Return a typed resource with `recent_scores=[]`.

The API resource shape is:

```json
{
  "id": "uuid",
  "nickname": "Bao",
  "avatar_url": "https://...",
  "default_target_profile": {
    "id": "uuid",
    "target_role": "AI 全栈开发",
    "relevant_experience_months": 84
  },
  "current_resume": null,
  "recent_scores": []
}
```

For a non-seed fixture that has a current resume, the nested resource contains `id`, `original_file_name`, `media_type`, `size_bytes`, `revision`, `uploaded_at`, and `updated_at`. It never exposes `storage_object_key`, `content_sha256`, a URL, or provider information. `current_resume` may be `null`; `default_target_profile` is required. Identity mapping fields are never exposed by this endpoint. Existing request-ID middleware and RFC 9457 handling remain the transport foundation.

**Alternative considered:** One cross-module SQL join over all ORM models. It is shorter for one endpoint but violates the module boundary and makes future identity-provider replacement harder.

### 6. Model the mini-program page as a finite view state

The mini program adds a typed API client and a page state union:

- `loading`
- `success` with resume
- `success` without resume
- `error`

Empty history is derived only from `recent_scores.length === 0`; it is not treated as an error. `onLoad`/`onShow` loads the overview, and the retry handler repeats the request. Experience formatting converts months without inventing precision: whole multiples of 12 display as years; other values display as years plus months or months only.

The profile page follows the “我的” section of `docs/design/visuals/home-overview.html`: page heading, profile card, current-resume panel, history card, setting rows, soft card surfaces, rounded spacing, and bottom tab navigation. The historical trend line shown in the visual reference is replaced by an empty-state message until real score records exist.

Avatar rendering uses the API URL with initials derived from `nickname` as a load-failure fallback. User/profile/resume values are never hardcoded in WXML or page data.

For the development seed, the resume panel shows “尚未上传，将在模拟面试时添加” and does not present upload, replacement, preview, or download controls. Tests may render a non-null resume response to prove the populated read-only state without implying that a real file is available in this change.

Automated mini-program component/page tests cover loading, populated success, no resume, empty history, request error/retry, and reserved actions. Type checking remains required.

**Alternative considered:** Initialize page data with the seeded “Bao” values and replace them after the request. This causes false content flashes and defeats the real-data acceptance goal.

### 7. Use native five-tab routing and inert named action handlers

`app.json` declares five tab pages in this order: 首页、复盘、模拟、上传、我的. The first four pages contain only a title/empty placeholder; “我的” owns the profile page. Native tab routing is preferred over a custom navigation component because it already provides correct switching semantics and keeps this change small. Visual tuning uses supported tab colors/icons without reproducing the visual's raised center button.

Reserved page actions are represented by a typed constant set:

- `open-settings`
- `preview-current-resume`
- `open-score-history`
- `configure-interview-language`
- `open-privacy-data`
- `open-about`

`preview-current-resume` is only rendered when `current_resume` is non-null. Handlers recognize these names but do not call `wx.navigateTo`, `wx.switchTab`, preview/upload/download APIs, or mutation endpoints. A no-resume page has no resume action; uploading and replacing are owned by the later simulation/interview change. Tests assert those side effects do not occur.

**Alternative considered:** Implement destination placeholder pages for every row. The request only needs future seams, and additional routes would imply behavior outside this change.

### 8. Verify the vertical slice at three levels

- Backend unit tests cover settings, provider construction, 401/409 mappings, response schemas, and application orchestration.
- PostgreSQL integration tests apply Alembic from an empty database, verify storage-neutral resume constraints and idempotent no-resume seeding, and query two actors to prove repository-level owner isolation.
- The isolated Compose check verifies initializer completion, healthy services, and a real gateway call returning the seeded `/api/v1/me/overview` data with `current_resume: null`.
- Mini-program tests cover page states, value rendering, retry, empty history, tab configuration, and no-op reserved actions; `npm run typecheck` remains required.

The focused PostgreSQL tests use the existing Compose PostgreSQL image and locked backend environment rather than SQLite, because partial indexes, UUIDs, migrations, and owner predicates must be exercised against the production database family.

## Risks / Trade-offs

- [The schema is introduced before any file-storage adapter exists] → Create no seed resume row and treat a row as valid only after a future upload transaction has durably stored the object; exercise non-null rows only as metadata fixtures.
- [A mutable current-resume row cannot preserve what an earlier interview used] → Require the later interview workflow to copy an immutable resume snapshot or immutable content reference into its configuration snapshot before the current row can be replaced.
- [Exactly one default profile is not fully enforceable as “at least one” by a partial unique index] → Enforce “at most one” in PostgreSQL and map a missing default to explicit `409` behavior; future profile commands must maintain the invariant transactionally.
- [Local actor configuration can point at a missing user] → Fail the overview as a not-found/invalid local setup error without falling back to another actor; make the deterministic seed command part of documented local startup.
- [Automatic Compose initialization changes service ordering] → Use a one-shot initializer with health/dependency checks and keep migration/seed commands independently runnable for diagnosis.
- [Native tab bar cannot exactly match the visual's raised simulation control] → Prefer correct low-cost navigation for this slice; a future global navigation design can replace it without changing profile/API contracts.
- [A remote avatar may fail under mini-program domain restrictions] → Provide an initials fallback and document local developer-tool network configuration; do not broaden this change into media hosting.

## Migration Plan

1. Add SQLAlchemy engine/session support and Alembic configuration without changing existing tables.
2. Apply the initial revision to an empty or existing foundation database; it only creates new tables and indexes.
3. Run the idempotent development seed where explicitly enabled; it creates no resume row.
4. Start API/Worker only after database initialization succeeds, then expose the new route and mini-program page.
5. Verify downgrade in an isolated database. Rollback removes only the four new tables and related indexes; because this is the first owner-data slice, no legacy data conversion is required.

Production deployment may run the same migration initializer with demo seeding disabled. Rollback of application code requires downgrading the revision only if the new tables must be removed; otherwise they can remain unused until a forward fix.

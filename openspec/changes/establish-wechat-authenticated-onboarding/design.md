# Design

## Context

See `proposal.md` for motivation and the four delta specs for observable behavior.

The current backend already has the `identity/access` and `candidate/profile`
module boundaries, PostgreSQL models for users, WeChat identity mappings,
capabilities and target profiles, plus owner-scoped profile and knowledge-source
queries. Authentication is still a process-configured local actor:
`current_actor` does not parse Bearer tokens, every business route declares its
own dependency, and the API entrypoint mounts business routers directly.
`users.avatar_url` is currently required and stores a URL, while object storage
is implemented inside `knowledge/source` and supports only put/delete.

The mini program currently has separate services that call `wx.request` and
`wx.uploadFile` directly. Its version-1 current-user cache contains only a user
ID, nickname and optional avatar URL; there is no auth-token store or login
coordinator. The home page requests `/api/v1/me/overview` when that cache is
missing, and the profile page assumes a non-null default target profile.

This change follows the modular-monolith and stack boundaries in
`docs/architecture.md` and ADR 0001, the PostgreSQL/object-reference truth
boundary in ADR 0002, the API and `ActorContext` rules in ADR 0004, typed
configuration and secret/logging rules in ADR 0005, and the application
port/infrastructure adapter and deterministic-fake strategy in ADR 0006. It
does not change the background-job architecture in ADR 0003.

## Goals / Non-Goals

**Goals:**

- Replace ordinary local-actor access with a production-capable WeChat
  authentication path while preserving the existing
  `ActorContext(actor_id, capabilities)` application contract.
- Make authentication protection structural: business routers are protected by
  their mount point, not by every handler remembering to parse credentials.
- Create users, WeChat bindings, optional private avatars and sessions as one
  recoverable registration operation with deterministic concurrent behavior.
- Keep session, capability and owner-scope truth in PostgreSQL and keep all
  provider credentials and transient WeChat values outside client and durable
  product state.
- Establish one mini-program boundary for auth state, display state, JSON
  requests, multipart uploads and 401 invalidation.
- Let a new user remain without a target profile, then create or update it from
  the authenticated “我的” page and reflect it on home without an overview
  fallback request.

**Non-Goals:**

- UnionID account merging, phone-number binding, account recovery, logout,
  account deletion, session/device listing or remote revocation UI.
- Refresh tokens, JWTs, Redis-backed authentication, sliding expiration or
  automatic request replay.
- Nickname or avatar editing after registration.
- Resume upload, interview history, real home learning data or changes to
  knowledge-source product rules beyond adopting the shared auth/transport
  boundaries.
- A new cloud service, database, framework, image-processing library or
  authentication SDK.

## Decisions

### 1. Select exactly one authentication mode and one WeChat adapter

Typed settings will replace the boolean local-actor switch with:

- `authentication_mode: "wechat" | "local_test"`
- `wechat_adapter: "real" | "fake"`
- `wechat_app_id`
- server-only `wechat_app_secret`
- `local_actor_id`, valid only for `local_test`

Development and normal automated tests default to `wechat + fake`. Production
requires `wechat + real`, a non-blank AppID/AppSecret and the existing real OSS
adapter; startup rejects `local_test`, fake WeChat, fake object storage, missing
secrets or conflicting provider fields. `local_test` is accepted only in the
test environment and constructs the existing persisted actor explicitly. It is
never consulted as a fallback after a missing or invalid Bearer token.

The real code2Session client uses `httpx` behind an identity application port.
`httpx` is already locked and used by backend tests; this change promotes it to
a direct runtime dependency so application code does not depend on a transitive
HTTP package. The adapter applies a bounded connect/read timeout, maps WeChat
error codes into stable internal results and never returns `session_key` across
the port. The port result is only configured `app_id`, returned `openid` and
nullable `unionid`. The deterministic fake maps named test codes to known
identities, invalid/used-code failures, timeout and unavailable outcomes.

**Alternative considered:** retain `local_actor_enabled` alongside Bearer auth.
That permits ambiguous simultaneous providers and preserves the unsafe missing
token fallback this change is intended to remove.

**Alternative considered:** call WeChat with a vendor SDK from the application
service. That violates ADR 0006 and makes deterministic failure tests depend on
vendor response structures.

### 2. Use a discriminated exchange response and two registration transports

The public authentication router exposes:

- `POST /api/v1/auth/wechat/exchanges` with JSON `{ "code": "..." }`
- `POST /api/v1/auth/wechat/registrations` with JSON registration token and
  nickname for the default-avatar path
- `POST /api/v1/auth/wechat/avatar-registrations` with multipart registration
  token, nickname and avatar file for the custom-avatar path

Exchange returns one of two typed `200` resources:

```json
{
  "status": "authenticated",
  "access_token": "<opaque>",
  "token_type": "Bearer",
  "expires_at": "2026-10-30T08:00:00Z",
  "current_user": {
    "id": "uuid",
    "nickname": "Bao",
    "avatar_url": null,
    "avatar_url_expires_at": null,
    "default_target_profile": null
  }
}
```

```json
{
  "status": "registration_required",
  "registration_token": "<opaque>",
  "expires_at": "2026-09-30T08:10:00Z"
}
```

Both registration routes invoke one application command and return the same
authenticated resource. Two routes are necessary because `wx.uploadFile`
requires a file while the default-avatar flow should remain a normal JSON
request and create no placeholder upload.

An unknown identity receives a 256-bit random, URL-safe registration token with
a 10-minute lifetime. Only its SHA-256 digest and the provider-neutral identity
result are persisted. No user, binding or auth session exists until registration
succeeds. Invalid, expired or irreconcilably consumed credentials return
`401 registration_token_invalid`.

Invalid/expired/used WeChat codes map to
`400 wechat_code_exchange_failed`; timeout or provider unavailability maps to
`503 wechat_service_unavailable`. Responses and logs contain neither the raw
provider message nor identity/session secrets.

**Alternative considered:** create a provisional user immediately after
code2Session. That produces half-onboarded accounts when nickname or avatar
submission fails and makes cleanup part of normal login.

**Alternative considered:** one multipart registration endpoint with an
optional empty file. `wx.uploadFile` cannot represent the no-file path cleanly
and would encourage fake placeholder files for the default avatar.

### 3. Persist digest-only registration and session state

The next Alembic revision performs these changes:

| Database change | Important fields and constraints |
|---|---|
| `users` | replace required `avatar_url` with nullable, unique, non-blank `avatar_object_key`; existing demo URLs migrate to `null` |
| `wechat_registration_attempts` | UUID ID, unique 64-character token digest, `app_id`, `openid`, nullable `unionid`, creation/expiry/consumption timestamps and nullable resolved user ID; no code or `session_key` |
| `auth_sessions` | UUID ID, user ID FK, unique 64-character token digest, issued/expires timestamps and nullable revoked timestamp |

`wechat_identities` keeps its existing unique `(app_id, openid)` constraint.
`unionid` remains informational and has no uniqueness or merge behavior.
`candidate_profiles` keeps the partial unique index that allows at most one
default per user. New users receive no candidate-profile row.

Session and registration tokens are 32 cryptographically random bytes encoded
with URL-safe base64. SHA-256 is sufficient for lookup persistence because the
input has 256 bits of server-generated entropy; a slow password hash would add
request cost without improving resistance to feasible guessing. Plaintext exists
only in the response-building call stack and is never logged. Session expiry is
exactly 30 days from issuance in UTC. Each successful login or registration
creates a separate row, so devices remain independent.

The session repository resolves a digest only when `revoked_at IS NULL` and
`expires_at > now`. It then loads capabilities from `user_capabilities` during
the same authentication operation and constructs a fresh `ActorContext`.
Neither the token nor the client cache contains capability claims.

**Alternative considered:** signed JWT access tokens. JWTs would duplicate
capability state, complicate immediate capability changes and still require
server persistence for revocation.

**Alternative considered:** store auth sessions in Redis. ADR 0003 limits Redis
to queue infrastructure and PostgreSQL is the product-state truth.

### 4. Serialize registration by provider identity and compensate external writes

Registration begins by locking the registration-attempt row and acquiring a
PostgreSQL transaction-scoped advisory lock derived from `(app_id, openid)`.
Inside that transaction the repository rechecks `wechat_identities` before any
user creation:

1. If a binding already exists, registration converges to that user and creates
   a new session without changing the winning nickname or avatar.
2. Otherwise it validates the still-live registration attempt and allocates the
   user, identity and session IDs.
3. For a custom avatar, only the lock winner writes
   `avatars/<user-id>/<avatar-id>.<ext>` to private object storage.
4. The transaction creates the user, binding and session, marks the attempt
   consumed/resolved and commits.
5. If object storage fails, the transaction rolls back. If the object write
   succeeds but database commit fails, the application attempts idempotent
   deletion of that unreferenced object before returning a safe failure.

Holding the identity lock across one bounded avatar write is accepted for this
low-volume onboarding path because it gives one clear winner and prevents
duplicate objects. The upload is limited to 5 MiB, so the lock is not held for
an unbounded stream. A future high-volume registration system could replace
this with a durable reservation/outbox workflow without changing the API.

The unique `(app_id, openid)` constraint remains the final integrity guard.
Concurrent requests using the same or different live registration tokens
therefore converge to one user. A consumed attempt may only converge when its
stored resolved user still matches the existing binding; otherwise it is
rejected.

Nicknames are trimmed, must contain 1–100 Unicode characters and reject NUL and
C0/C1 control characters. They are not silently replaced by a generated value.
Avatar files must be non-empty JPEG, PNG or WebP, no larger than 5 MiB, with an
allowed declared media type matching a small magic-byte check. No image
decoding/transcoding dependency is introduced.

**Alternative considered:** upload before acquiring an identity winner. That
allows concurrent requests to create duplicate objects and makes cleanup the
normal path.

**Alternative considered:** rely only on catching the unique-constraint error.
It protects rows but does not prevent duplicate uploads or define which
registration data wins.

### 5. Extract one shared private-object-storage port and add signed reads

The provider-neutral `ObjectStorage` port moves from `knowledge/source` into the
platform/foundation application boundary. The fake and OSS adapters move to the
matching platform infrastructure boundary. The existing knowledge-source
service depends on the shared port without changing its product behavior.

The port supports:

- `put(...)`
- idempotent `delete(object_key)`
- `sign_get_url(object_key, expires_in)`

OSS remains private. Avatar display URLs are signed for 10 minutes. Database
resources return only `avatar_url` and `avatar_url_expires_at`, never the object
key. The fake returns deterministic expiring values suitable for contract tests.
Signed URLs, access credentials and provider exception text are excluded from
normal logs.

The mini-program current-user cache stores either `avatar: null` or
`{ url, expiresAt }`; it never stores an object key. An expired cached avatar is
treated as absent and renders the built-in default. The “我的” overview request
can return a newly signed URL, while home does not make a request merely to
refresh an avatar.

**Alternative considered:** preserve `users.avatar_url`. A signed URL expires
and a permanent public URL violates the private-object and provider-neutral
requirements, so neither is durable account state.

### 6. Mount all business routes beneath one protected FastAPI router

The API entrypoint creates three explicit route groups:

- health routes mounted directly on the app;
- public authentication bootstrap routes;
- a `protected_v1_router` with prefix `/api/v1` and a global authentication
  dependency.

Profile, target-profile and knowledge-source routers use paths relative to the
protected prefix and are included only under `protected_v1_router`. The global
dependency parses exactly one `Authorization: Bearer <token>` header in WeChat
mode, or resolves the explicit persisted actor in `local_test` mode. On success
it stores the resulting `ActorContext` in `request.state`.

The existing `current_actor` dependency becomes a state accessor; it never
parses headers or chooses providers. Business handlers may request the actor
through this accessor for type-safe application calls, but omitting it cannot
make the route public because the parent router already authenticated the
request. A route-inventory test asserts that the only unauthenticated paths are
the two health routes, the exchange route and the two registration routes.

Missing, malformed, unknown, expired and revoked session tokens all return the
same `401 authentication_required` Problem Details without revealing which
check failed. Authentication completes before profile, capability, quota,
knowledge-source or object-storage operations. Owner-scoped repositories
continue to receive only `ActorContext.actor_id`, and capability checks consume
the freshly loaded server-side set.

**Alternative considered:** keep `Depends(current_actor)` as the only guard on
every handler. A newly added route can then be accidentally public, and each
module remains responsible for authentication wiring.

**Alternative considered:** middleware that protects every path except string
allowlists. Router composition is visible in OpenAPI and tests, and avoids
middleware duplicating FastAPI dependency/error behavior.

### 7. Make nullable overview and target-profile upsert explicit

`GET /api/v1/me/overview` keeps its existing composition, but the identity
display contract returns nullable signed avatar fields and the candidate query
returns a nullable default profile. A missing profile is a successful resource,
not `ProfileOverviewIncomplete`; that exception and its `409` mapping are
removed.

`PUT /api/v1/me/default-target-profile` accepts only:

```json
{
  "target_role": "AI Platform Engineer",
  "relevant_experience_months": 36
}
```

`target_role` is trimmed, must contain 1–200 characters and rejects NUL/C0/C1
controls. Experience is an integer from 0 through 600 months. The response is
the typed target-profile resource, not a full overview.

The candidate/profile repository applies `actor_id` before every query and uses
a transaction-scoped advisory lock derived from that actor ID to serialize the
first default-profile creation. It rechecks the owner-scoped default row, then
updates it or creates one. The existing partial unique index is the final guard.
No user ID or profile ID is accepted from the client, so the command cannot
select another user's record.

**Alternative considered:** `POST` for create and `PATCH` for update. The client
would need to branch on nullable state and handle a race between read and write;
an idempotent owner-scoped `PUT` expresses the desired single default resource.

### 8. Separate mini-program auth, display and transport responsibilities

The mini program adds:

- auth store schema v1:
  `{ schemaVersion, accessToken, expiresAt }`;
- current-user display store schema v2:
  `{ schemaVersion, userId, nickname, avatar, defaultTargetProfile }`;
- a login coordinator;
- shared JSON request and multipart upload transports;
- one centralized authentication invalidator.

Both stores perform runtime shape validation before returning data. If either
required store is missing, corrupt, on an unsupported version or locally
expired, the coordinator clears both stores. Store writes after a successful
login/registration are ordered as a small commit: validate both response
objects, persist auth, persist current user, and clear both if either write
cannot be made durable. Display state is never consulted as authorization.

Protected transports default to requiring auth, read the token internally and
attach the Bearer header. Public bootstrap calls use explicit public transport
methods that never attach an old token. Existing profile and knowledge-source
services become typed API mappings over these transports; pages and services
never concatenate the `Authorization` header. Existing
`Idempotency-Key` and multipart form headers are merged without allowing a
caller to override Authorization.

The first protected `401` enters a single-flight invalidation operation:
clear both stores and in-memory page state, then
`wx.reLaunch({ url: "/pages/login/index" })`. Concurrent 401s await or observe
the same operation. The failed request is rejected once and is not replayed.
Local expiry is checked before sending a protected request and follows the same
path without network access. No path invokes `wx.login` except the explicit
login-button handler.

**Alternative considered:** one combined cache object. Separating the token
from display data makes it harder for UI code to treat display state as
authentication and makes complete user-data clearing an explicit invariant.

**Alternative considered:** let every service add headers. That recreates the
current duplication and guarantees that multipart and future services will
drift.

### 9. Add a dedicated login/onboarding route and finite UI states

`pages/login/index` is a non-tab page and the first launch route. On startup it
only validates local stores:

- valid auth and current-user caches switch to the home tab;
- absent/invalid/expired state remains on the login page;
- startup never calls `wx.login`.

The login page states are `idle`, `exchanging`,
`registration_required`, `registering` and `error`. The user taps “微信登录”
to call `wx.login` and exchange its code. For first registration, a nickname
form uses the WeChat nickname input capability and an optional
`button open-type="chooseAvatar"` supplies a temporary file path. The default
avatar is a deliberate no-file choice. Submission is disabled while registering
and the nickname/avatar inputs are not shown as editable after success.

The visual direction follows `docs/design/visuals/ui-direction.html`: native
controls, soft card surfaces and a clear primary login action. Required states
are idle, exchange loading, registration form with default avatar, selected
avatar, registration/upload loading, recoverable invalid input, provider
failure and success transition. Provider/storage details are never rendered.

Protected tab pages also run the same local auth guard when shown. Invalid state
relaunches login before rendering user content. After authenticated bootstrap,
the coordinator uses `wx.switchTab` to enter home and native five-tab
navigation remains unchanged.

### 10. Update home and profile as cache/overview consumers with explicit states

Home continues the hierarchy in
`docs/design/visuals/home-knowledge-categories.html` and retains its deterministic
learning fixture. Its identity states become only:

- authenticated success from valid current-user cache;
- login transition when the cache is absent/invalid.

The old overview loading/error/retry fallback is deleted. On every show, home
re-reads schema-v2 display state. A null target profile renders
“请在我的页面填写目标岗位” below “按主题学习”; tapping it calls
`wx.switchTab` for the existing profile tab. A non-null profile hides the
prompt. Neither branch requests overview.

The “我的” page continues the composition in
`docs/design/visuals/home-overview.html` and uses the protected overview API.
Its states are overview loading, success, default avatar, null target-profile
onboarding form, existing target-profile summary, editing, save loading, save
success, save error, no resume, empty history and non-auth error/retry. A 401 is
owned by the shared transport and does not render as an ordinary page error.
Nickname and avatar remain read-only.

On a successful target-profile PUT, the page updates its current response and
atomically replaces only `defaultTargetProfile` in current-user store v2. A
failed save preserves form input and the previous cache. Returning to home
therefore removes or updates the prompt without an overview call.

The upload tab retains its existing UI behavior but adopts the auth guard and
shared upload/request transports. Loading, success, empty, quota, non-auth
error and 401 login-transition states remain distinguishable, and a cleared
session removes all prior owner records from page state.

### 11. Standardize safe errors, logs and verification seams

Stable error mappings are:

| Condition | HTTP / code |
|---|---|
| invalid, expired or used WeChat code | `400 wechat_code_exchange_failed` |
| WeChat timeout/unavailable | `503 wechat_service_unavailable` |
| invalid/expired registration credential | `401 registration_token_invalid` |
| invalid nickname/avatar/target profile | `422 validation_error` with field violations |
| private object storage unavailable | `503 object_storage_unavailable` |
| any invalid business Bearer session | `401 authentication_required` |

Authentication, registration and adapter logging uses request ID, stable event
name, internal user/session IDs when available, safe outcome code and exception
type. It never logs request bodies, WeChat code, AppSecret, `session_key`,
registration/session token, signed URL, provider response or raw provider
exception. Tests inspect captured logs, Problem Details and schema columns for
these forbidden values.

Backend verification covers port/adapter contracts, token digest/expiry,
configuration rejection, migration constraints, concurrent registration,
storage compensation, route inventory, session/capability resolution,
owner isolation, nullable overview and target-profile concurrency. Mini-program
tests cover store validation, transport headers, public bootstrap exclusion,
single-flight 401 clearing, no replay/silent login, login/onboarding states,
default/custom avatar, home no-overview behavior, profile editing and cache
synchronization. PostgreSQL integration tests use the existing production
database family rather than SQLite.

## Risks / Trade-offs

- [Registration holds a database identity lock during one OSS write] → Bound
  avatar size and adapter timeouts, upload only after winner selection and keep
  the operation synchronous; revisit a durable reservation workflow only if
  observed registration volume requires it.
- [Object deletion compensation can itself fail] → Record a safe cleanup event
  with the object key excluded from ordinary logs and make deletion idempotent;
  the object remains unreferenced and cannot authenticate or appear in an API.
- [Existing demo avatar URLs cannot be converted into private object keys] →
  migrate them to `null` and use the built-in default; no production user
  account flow currently depends on those demo URLs.
- [A 30-day non-refreshing token eventually interrupts an active page] → use
  one predictable 401 invalidation path and require explicit login, matching the
  product decision instead of hiding expiry behind retries.
- [Signed avatar URLs can expire while cached] → store their expiry, render the
  built-in default after expiry and refresh only through a normal authenticated
  response, never a home-page identity fallback.
- [Advisory locks require PostgreSQL-specific integration tests] → PostgreSQL is
  already the accepted source of truth; exercise concurrency against the real
  database family and retain unique indexes as final guards.
- [Changing all business router paths to relative protected mounts can omit a
  route during refactoring] → use route-inventory/OpenAPI tests to assert the
  complete public allowlist and expected protected paths.
- [The login route becomes the launch page even for cached users] → local
  validation immediately switches authenticated users to home without network
  access or `wx.login`; this small transition centralizes startup gating.

## Migration Plan

1. Introduce typed authentication/WeChat settings and shared object-storage
   port/adapter wiring while preserving existing fake behavior in
   development/test.
2. Apply the Alembic revision that adds registration/session tables and
   `users.avatar_object_key`; migrate existing avatar URLs to `null`, update
   deterministic seed data and verify upgrade/downgrade in an isolated
   PostgreSQL database.
3. Deploy backend bootstrap/session services and protected-router composition
   together so no production business route is left on the old implicit actor
   path. Production configuration must already provide real WeChat and OSS
   secrets before startup.
4. Deploy the mini program with login route, schema-versioned stores and shared
   transports as one client release. Cache v1 is intentionally invalidated;
   users see the login page and explicitly authenticate once.
5. Enable the target-profile PUT and nullable overview in the same backend
   release as the profile/home client changes so null profiles are never
   interpreted through the old `409` behavior.
6. Run focused backend, migration, mini-program, Compose topology and
   running-development beta checks before production promotion. A production
   smoke verifies public health/bootstrap and authenticated overview/knowledge
   routes without logging credentials.

Rollback first restores the previous mini program. Backend rollback then
restores direct business-router mounting and the prior local test setup only in
non-production. If the database revision must be downgraded, session and
registration rows are discarded and custom avatar references are removed;
unreferenced private avatar objects are cleaned separately. Because the old
schema requires `users.avatar_url`, downgrade assigns the existing deterministic
default display URL only for development seed users and must not synthesize a
public URL for production accounts. A production rollback that would require
that lossy schema downgrade must instead keep the new columns/tables unused
until a forward fix is deployed.

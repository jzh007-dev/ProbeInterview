# Tasks

## 1. Persist real profile overview data

- [x] 1.1 Add shared SQLAlchemy 2 engine/session infrastructure, Alembic configuration, and an isolated PostgreSQL integration-test runner; verify a clean database can upgrade to head and downgrade to base with the focused runner.
- [x] 1.2 Implement the identity/access and candidate/profile ORM mappings plus the initial revision for `users`, `wechat_identities`, `candidate_profiles`, and `user_resume`; verify PostgreSQL integration tests cover foreign keys, `(app_id, openid)` uniqueness, non-negative numeric checks, one default profile per user, one current resume per user, the `original_file_name`/`media_type`/`size_bytes`/`content_sha256`/`storage_object_key`/`revision`/timestamps contract, and absence of PDF bytes, permanent URL, provider credentials, and `session_key` columns.
- [x] 1.3 Add typed `demo_profile_seed_enabled`/`local_actor_id` settings and an idempotent development seed containing one user, WeChat-shaped identity fields, and multiple target profiles with one default but no resume row; verify repeated seed execution produces the same rows, `user_resume` remains empty for the seed user, and production settings reject demo seeding.

## 2. Deliver the owner-scoped overview API

- [ ] 2.1 Implement `ActorContext`, the configuration-backed development/test local actor provider, and the current-actor FastAPI dependency; verify backend unit/API tests cover configured resolution, no actor header support, `401` Problem Details when unresolved, and production refusal.
- [ ] 2.2 Implement identity display and candidate overview application contracts, owner-scoped PostgreSQL repositories, typed response schemas, and `GET /api/v1/me/overview`; verify API tests cover the seed response with `current_resume: null`, a metadata-fixture response exposing only display-safe resume fields, `recent_scores: []`, explicit default-profile selection, no storage key/hash/URL leakage, and `409 profile_overview_incomplete` when no default exists.
- [ ] 2.3 Add PostgreSQL-backed two-actor API tests that use separate configured app instances against shared fixtures; verify each actor receives only its own user/profile/resume data and an actor without a resume cannot observe the other actor's resume.
- [ ] 2.4 Document the migration, no-resume seed, local actor, and `curl /api/v1/me/overview` workflow in `docs/development.md`, including that file storage/upload/preview belongs to the later simulation feature; verify every documented command runs as written against the development environment.

## 3. Deliver the “我的” page states

- [ ] 3.1 Add the locked mini-program test dependencies/scripts, typed overview API client, response types, experience formatter, and avatar-initial fallback; verify `npm test` covers request success/failure mapping, month formatting, and initials without hardcoded seed-user values.
- [ ] 3.2 Implement the “我的” page structure and styling from `docs/design/visuals/home-overview.html`; verify mini-program tests cover loading, metadata-fixture success, the seed user's “尚未上传，将在模拟面试时添加” state, empty history, error, and retry, and verify the rendered empty states contain no fake resume, score, link, or trend data.
- [ ] 3.3 Add stable inert actions for settings, existing-resume preview, score history, interview language, privacy/data, and about; verify mini-program tests show `preview-current-resume` only for a non-null resume and assert no navigation, preview, upload/download, database mutation, or other destination behavior.

## 4. Complete local navigation and runtime acceptance

- [ ] 4.1 Configure native tab routing in the order 首页、复盘、模拟、上传、我的, add the four empty page shells and tab assets, and keep “我的” as the only implemented business page; verify `app.json`/mini-program tests exercise switching to every tab and loading the profile page from another tab.
- [ ] 4.2 Add the one-shot database initializer to development/test Compose, disable demo seeding in production configuration, and make API/Worker depend on successful initialization; verify `scripts/test-compose-topology` checks the production service/config boundary, starts an isolated stack, and retrieves the seeded overview with `current_resume: null` through the gateway.
- [ ] 4.3 Run the complete change acceptance set: `scripts/check-skeleton`, backend unit tests, Ruff format/lint, mypy, the isolated PostgreSQL profile runner, mini-program `npm test` and `npm run typecheck`, and `scripts/test-compose-topology`; then open the local mini program and confirm the five tabs，以及“我的”页面的真实无简历、空历史和错误状态符合已确认的视觉方向。

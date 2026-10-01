# ProbeInterview Agent Rules

## Workflow

- Work comes from `BACKLOG.md`. **One delivery unit per session.** A delivery unit is one commit-sized, independently reviewable change (~≤500 lines of diff) — not a whole feature, and not a single acceptance bullet. Never run several units in one session: later units inherit the earlier unit's context, which is the most expensive thing we have measured.
- Before coding, read `docs/features/<name>.md` (create it from `docs/features/_template.md` if it does not exist). Its **§落点 (landing points)** lists the files to touch. **Read only those files; do not search the repository.** If you need a file outside that list, say why before reading it.
- If §落点 cannot be filled in, the scope is not ready. Stop and fill D0 instead.
- Bug fixes and any "where is this even implemented?" work use two phases (diagnosis, then implementation) — see `docs/workflow.md` §两阶段. Phase one produces a root cause plus a landing-point table and **stops** for approval; it does not start editing.
- When a unit is done: commit, then **stop**. Report `git diff --stat`, the acceptance items it covers, and the raw verification output; wait for review. Do not start the next unit.
- Update the feature file's §当前中间态 before the session ends. The next session reads that section; it must not re-derive state from `git log`.
- Follow `docs/workflow.md` (D0–D6). Follow `docs/recipes.md` for standard implementation patterns; do not invent new structure.
- Completion = every acceptance bullet has a test, `scripts/verify --full` is green, the raw output is shown, and `git status` is clean apart from expected untracked files.
- Scope deviations: edit the feature file directly and continue. Only decisions that change stack, module boundaries or data ownership require an ADR first.
- Deferred RAG choices (chunking, embedding dimensions, index types, retrieval weights, rerank thresholds) still require an explicit confirmed design before implementation.

## Status reporting

End every turn in exactly one of these states:

- `RUNNING` — work continues autonomously, no user action needed. Commentary only; never end a turn in this state.
- `COMPLETE` — the requested work plus every applicable verification and hand-off step is done.
- `NEEDS_DECISION` — a concrete choice or extra authority is required. Name the exact decision; never ask for a generic "continue".

## Stop signals

Hit any of these, stop and reassess instead of adding another branch:

- **The same class of problem shows up a second time** (another compatibility branch, another protocol hop, another special case). The second occurrence is a reset point, not an optimisation point: group the root causes and re-read the whole diff against the original requirement.
- The change grows beyond the files listed in §落点. Stop, update the feature file's §范围 / §落点, then continue.
- The work needs a new table, port, async flow or third-party dependency. Stop; that is L2 or needs an ADR.
- You are about to reach for `git stash`, a throwaway container, or a full test suite just to answer "was this already broken?". Answer it with one query, one minimal test, or `git show HEAD:<file>` instead.
- You catch yourself writing "looks fine", "it's just a small change", "I'll test it later", "good enough for now". Go run `scripts/verify`.

## Verification

Pick the depth by **change type** as well as by size (L1/L2/L3). The two axes are independent.

| Change type | At minimum |
|---|---|
| Docs / comments | format check + `git diff --check`; run any command example you changed |
| Code | `scripts/verify`; add `scripts/verify --full` at the merge gate |
| Config / migration / Compose / topology | the row above + `scripts/test-compose-topology` |
| Mini program page or component | the row above + `cd apps/miniprogram && npm test && npm run typecheck` |

- Always paste the **raw output** of the commands you ran. Never send the gate's output to `/dev/null`.
- A docs-only commit does not need `--full`: it costs minutes of Docker for no signal.
- `scripts/verify` — fast gate (format, lint, mypy, backend unit, mini program jest + typecheck). Runs on every commit; the pre-commit hook enforces it.
- `scripts/verify --full` — adds PostgreSQL integration tests in an isolated Docker container. Run before merge; CI runs it on every push/PR.
- `scripts/test-compose-topology` — Compose topology assertions (CI).
- `scripts/test-beta-smoke` — read-only check against a running gateway (`PROBEINTERVIEW_BETA_BASE_URL` to override).
- Local startup: `docs/development.md`. Deploy and post-deploy verification: `docs/ops.md`.

## Git

- One commit per delivery unit. `scripts/verify` must be green first (the pre-commit hook enforces this).
- **Never rewrite history**: no `amend`, no `rebase`, no force push, no `reset --hard`. Keep history revertible.
- Do not switch branches or worktrees on your own; explain why and ask first.

## Architecture constraints (hard)

- Monorepo, module-first modular monolith (ADR 0001): backend Python 3.12 + uv + FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic; native WeChat mini program in TypeScript + TDesign.
- PostgreSQL is the source of truth; pgvector data is derived/rebuildable; Redis is not product state. Celery messages carry stable IDs, never private content or full mutable payloads.
- Domain/application code must not import vendor SDKs or another module's repository/ORM model. External services are accessed through ports and infrastructure adapters.
- Actor and public/owner scope filters must be applied before database or vector retrieval.
- Success APIs return typed resources; errors use RFC 9457 Problem Details; async creation returns 202 + Location with Idempotency-Key where retryable.
- Logs must not contain private source text, request bodies, complete prompts/model responses, secrets or tokens. Check tracebacks, exception chaining, `__context__`, telemetry and artifacts — not just the primary output.
- **Never return unbounded data from an external or collection query.** Server-side filtering is mandatory; otherwise add explicit `max_depth`/`jq` truncation. Measured incident: one list endpoint returned a full collection and blew up the caller's context.
- Do not hand-roll retry loops. Use the existing retry library/decorator; if a hand-rolled retry is genuinely required, say why in the code.
- Never introduce a new language, framework, database, cloud service or major dependency without an accepted ADR. Discuss with the user first.

## Where to read before changing what

| Changing | Read first |
|---|---|
| Any implementation detail | `docs/recipes.md` (§0 landing-point index + the matching recipe) |
| Module boundaries, data ownership, stack | `docs/architecture.md` + `docs/adr/` |
| Auth, identity, sessions | ADR 0004 + `identity/access/` |
| Async, Celery, compensation | ADR 0003 |
| External adapters, verification strategy | ADR 0006 |
| Deploy, Compose, release | `docs/ops.md` |
| Local commands, env vars | `docs/development.md` |
| UI and visuals | the matching file under `docs/design/visuals/` |
| What this feature is, and how far it got | `docs/features/<name>.md` §落点 / §交付单元 / §当前中间态 |

## Sources of truth

- `docs/architecture.md` + `docs/adr/` — project-level structure and decisions. ADRs are append-only; superseding requires a new ADR and syncing `docs/architecture.md`.
- `docs/features/<name>.md` — per-feature scope, landing points, contracts, acceptance, delivery units and current state. Keep it consistent with code as you work; it is the only planning artifact for the feature.
- `openspec/` is a frozen archive of the previous process. Do not implement from it or update it; `deliver-probeinterview-mvp` and the old `codex/deliver-probeinterview-mvp` branch are rejected references.
- For UI work, check the relevant visual under `docs/design/visuals/`.
- When a rename or move invalidates references elsewhere (file paths, section headings, command names in `scripts/verify`, user-facing error strings in source): grep the whole repository and update every hit before committing.

# Design

## Context

See `proposal.md` for motivation and `specs/home-knowledge-overview/spec.md` for observable behavior.

The mini program already has native five-tab routing, a placeholder `pages/index` shell, a typed `fetchProfileOverview` client for `GET /api/v1/me/overview`, and `miniprogram-simulate` tests. It does not yet have login, session storage or a current-user client cache. The backend currently resolves development/test requests through the configuration-backed local actor and already returns that actor's nickname and default target profile; production rejects the local actor. This change does not add authentication, a new API or database state.

The UI direction comes from `docs/design/visuals/home-knowledge-categories.html`, with the softer card, gradient and spacing conventions also visible in `docs/design/visuals/home-overview.html`. These are visual references rather than independent requirements. The change follows `docs/architecture.md`, ADR 0001, ADR 0004 and ADR 0006; no knowledge module, cloud adapter or model call is introduced.

## Goals / Non-Goals

**Goals:**

- Replace the home tab shell with a native mini-program rendering of the confirmed knowledge overview hierarchy.
- Make the home page consume a typed current-user display cache that future login can populate, with an explicit development/test overview fallback while login is absent.
- Recompute the local date and time-appropriate greeting whenever the page becomes visible.
- Keep all training and knowledge values in one typed, deterministic fixture that later changes can replace section by section.
- Provide a three-card native swiper for fake continue-learning content.
- Make cache hit, fallback loading, success, error, retry, time boundaries, swiping, theme selection and reserved actions directly testable.
- Preserve native tab navigation, its selected state and the existing profile page behavior.

**Non-Goals:**

- Knowledge-source upload, storage, parsing, concepts, role mappings, RAG or review.
- OAuth, WeChat code exchange, tokens, sessions, logout or production authentication.
- A fake backend endpoint or database seed for home data.
- Real learning progress, weekly coverage, review counts, search or topic navigation.
- Empty-knowledge behavior; the deterministic fixture is always present after identity loading in this change.
- Pixel-identical reproduction of the standalone HTML renderer.

## Decisions

### 1. Implement the home composition as a dedicated native component

Add `components/home-knowledge-overview` and make `pages/index/index.wxml` render it. The component owns loading and interaction state, while the page remains a thin native tab route.

This matches the existing profile-overview composition and allows `miniprogram-simulate` to test lifecycle behavior without introducing a page-specific testing pattern.

**Alternative considered:** Put all state and markup directly in the page. This would work, but would diverge from the existing profile component pattern and make isolated rendering tests less reliable.

### 2. Add a current-user display cache with a development/test fallback

Add a `CurrentUserSnapshot` schema containing a cache schema version, user ID, nickname and optional avatar URL. A current-user store reads an in-memory snapshot first and then a versioned `wx` storage entry. It validates every stored value before returning it.

The home component asks this store for the current user:

1. A valid cache hit returns immediately without a request.
2. A missing or invalid cache invokes `fetchProfileOverview`, reads only safe display fields and writes the normalized snapshot.
3. A failed fallback produces the home error state; retry repeats the fallback.

This fallback is explicitly transitional. It works today because development/test uses the local actor provider. Production still rejects the local actor, so production requires the later login change to populate the same cache and attach authentication centrally to API requests. The cache is display state only and never proves identity or capability. The login/logout change will replace or clear it when the actor changes.

No backend change is necessary because the archived `my-profile-overview` capability already guarantees owner-scoped nickname access and stable error behavior in the current local environment.

**Alternative considered:** Call `/api/v1/me/overview` on every home display. This duplicates information future login already returns, adds unnecessary requests and couples the page to the profile aggregate.

**Alternative considered:** Require login before implementing the home page. Login is intentionally deferred; the validated fallback keeps the current local vertical slice usable without baking local actor logic into the component.

**Alternative considered:** Add a `/api/v1/home` endpoint returning nickname plus fake values. Fake product data must not cross the API boundary or imply a persisted home read model.

### 3. Centralize fake values in one typed fixture

Add a typed fixture module under the mini program containing:

- weekly coverage percentage and covered-topic count;
- pending-review count;
- three continue-learning cards, each with topic, title, summary and progress;
- the six topic categories, descriptions, icons, colors and counts;
- the initial selected topic ID.

The component imports this fixture into its initial data. WXML contains labels and bindings, not duplicated knowledge values.

Later `serve-role-aware-home-topics` can replace only the categories portion with a real API response while leaving unrelated fake sections explicit.

**Alternative considered:** Hardcode values directly in WXML and component data. That makes it difficult to prove which data is fake, encourages inconsistent copies and complicates later replacement.

### 4. Derive date and greeting from an injectable local clock

Add pure presentation helpers that accept a `Date` and return:

- `YYYY.MM.DD · 今日训练`;
- “早上好” from 05:00 through 11:59;
- “下午好” from 12:00 through 17:59;
- “晚上好” from 18:00 through 04:59.

The component computes these values on attachment and through `pageLifetimes.show`, so switching tabs or returning after midnight refreshes the header. Tests inject fixed dates rather than changing the system clock.

The device clock is presentation context, not trusted authorization or persisted business time.

**Alternative considered:** Calculate the greeting once when the component is created. A tab can remain alive across time boundaries, leaving stale date and greeting text.

### 5. Use a finite view state and local-only actions

The component state is:

- `loading`
- `success`
- `error`

It also stores `currentUser`, `dateLabel`, `greeting`, `currentLearningIndex`, `selectedTopicId`, `selectedTopicSummary`, `errorMessage` and `lastAction`. Stable actions are:

- `search-knowledge`
- `continue-learning`
- `select-topic`

Selecting a topic updates only component state. A native `swiper` change updates `currentLearningIndex`; WXML derives the card content, progress and active indicator from that index. Swiping does not write storage. Search and continue-learning update `lastAction` for testable seams but call no navigation, request, storage, upload or download API.

**Alternative considered:** Add placeholder destination pages. Those routes would imply behavior beyond this change and increase future migration work.

### 6. Translate the visual direction within native constraints

The affected page is `pages/index`. Its states are:

- loading: a soft card shown only while the cache fallback is pending;
- success: dynamic date and greeting, weekly summary, three-card continue-learning swiper and six-topic grid;
- error: understandable message plus retry action;
- empty: not applicable because success uses the deterministic fixture.

Styles use native WXSS, existing system fonts, soft gradients, rounded translucent surfaces and the current native tab bar. The page does not render the standalone visual's bottom navigation. `app.json` remains the navigation source of truth through `selectedColor` and each entry's `selectedIconPath`; WeChat marks the current route. TDesign remains available but no new dependency or custom navigation is required.

### 7. Verify behavior at the component and route boundaries

Automated mini-program tests will prove:

- a valid cache hit renders a non-Bao nickname without a request;
- missing or invalid cache shows fallback loading without flashing a hardcoded or stale nickname, and successful fallback refreshes the cache;
- all six fixture topics and all three continue-learning cards render;
- swiping changes the card, progress and unique active indicator without storing progress;
- fixed clock inputs cover 05:00, 12:00, 18:00 and midnight, and page show refreshes the header;
- request failure shows error and retry recovers;
- topic selection changes the unique selected state and summary;
- reserved actions have no navigation, storage, upload/download or extra request side effects;
- the home route is no longer treated as a placeholder shell while the remaining unimplemented tabs stay intact;
- native tab configuration supplies distinct normal/selected icons and the configured selected color for every route.

`npm test` and `npm run typecheck` are the focused verification commands.

## Risks / Trade-offs

- [Users may interpret fake training values as real progress] → Keep all values in an explicitly named fixture, avoid backend persistence, and limit the change description and tests to visual demonstration data.
- [A stale cache can display a previous user's nickname after future account switching] → Version and validate the snapshot; require the later login/logout change to replace or clear it before exposing account switching.
- [The transitional overview fallback has no production authentication today] → Limit the fallback assumption to the existing development/test local actor path; production remains blocked on the later login change rather than enabling local actor.
- [The fallback response contains fields the page does not use] → Normalize only safe display fields into the cache and accept the one-time local overhead until login populates the snapshot directly.
- [Standalone HTML dimensions do not map exactly to native components] → Preserve hierarchy, color direction, density and interaction emphasis rather than pixel equality.
- [The locally formatted date can differ around timezone boundaries] → Use the device's local date only as presentation context and keep knowledge values deterministic.
- [Swiper state can look like persisted learning progress] → Keep it local, make no progress API/storage call and reset according to normal component lifecycle.
- [Future real topic data may require different loading states] → Keep topic rendering driven by a typed array and isolate it from the identity request so a later change can replace its source without rewriting the page.

## Migration Plan

1. Add the versioned current-user cache, presentation-time helpers and typed fixture without changing the existing tab route.
2. Add the home component and replace the home page shell markup.
3. Add cache, clock, swiper, component and route tests, then run mini-program tests and type checking.
4. Rollback restores the prior page shell and removes the cache consumer, component and fixture; no backend or persisted data migration is involved.

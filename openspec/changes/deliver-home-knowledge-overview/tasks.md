# Tasks

## 1. Establish cached identity and the typed presentation model

- [x] 1.1 Add the versioned `CurrentUserSnapshot` cache/store, the deterministic three-card home fixture, topic-selection helpers and injectable local date/greeting formatter; verify mini-program unit tests cover a valid cache hit without a request, missing and invalid cache fallback/refresh, all six topics, all three learning cards, summary formatting, and the 05:00, 12:00, 18:00 and midnight boundaries on September 29, 2026 without placing knowledge values in WXML.

## 2. Deliver cached nickname, dynamic time and swipeable home states

- [x] 2.1 Implement the native `home-knowledge-overview` component and replace the home page shell with it; verify `miniprogram-simulate` tests cover immediate cached nickname rendering, fallback loading without a hardcoded or stale nickname, successful non-Bao overview fallback and cache refresh, request error/retry, and date/greeting refresh when the page becomes visible across a time boundary.
- [x] 2.2 Implement the visual hierarchy and WXSS direction from `docs/design/visuals/home-knowledge-categories.html`, including a native three-card swiper; verify the rendered component exposes the dynamic header, weekly summary, current learning card, synchronized progress and unique active indicator, selected topic summary and two-column six-topic grid while loading and error remain visually distinct.

## 3. Preserve local-only interaction boundaries

- [x] 3.1 Add stable search, continue-learning and topic-selection actions plus local swiper state; verify tests prove topic selection updates one local selected topic and its summary, swiping updates only the card/progress/indicator, and search or continue-learning causes no navigation, storage, upload/download, extra network request or persistent mutation.

## 4. Complete route and focused acceptance

- [x] 4.1 Update tab-route coverage so the home route renders the new component while review, simulation and upload remain page shells, profile remains functional, and every native tab declares distinct normal/selected icons plus the configured selected color; verify `cd apps/miniprogram && npm test && npm run typecheck` pass.

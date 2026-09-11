# Session state (live)

**Milestone:** M-10 Lecture Edit + Versions + 7-Dim Scoring
**Branch:** milestone/M-10-lecture-edit-scoring (forked from M-09 tip — M-09 PR #30
still OPEN/unmerged; flagged in PR description, retarget to staging once #30 merges)

**Done:**
- T-129 (fbba2bb, fe88afa) — edit/scoring data model.
- T-130 (099c62b, ee35ac7, 76147a1, 09351dc) — TipTap editor, save/autosave.
  Playwright @smoke authored, NOT run (Alpine/musl container, no glibc Chromium).
- T-131 (ed39a24) — voice dictation via faster-whisper (REST, not T-121's WS).
- T-132 (bebef3a) — image upload (lecture_image profile, bucket="images", new)
  + AI diagram suggestions (LLM over already-cited reference chunks + on-demand
  pdfplumber page render — NOT a new vision-ingestion pipeline; flagged as a
  scoped interpretation in the backlog notes). School-tenant only for
  suggestions; both tenants get image upload. 251 backend / 308 frontend tests.

**Current ticket:** T-133 (effort tracking) — next up
**Next:** ticket-loader T-133 → wire lecture_edit_sessions (already modeled in
T-129: active_ms, edits_count, char_delta, started_at, ended_at) → frontend
Page Visibility API pause/resume + 30s heartbeat → backend session start/
heartbeat/end endpoints → effort score = normalize(active_ms)×0.4 +
normalize(char_delta)×0.6 feeding T-134's scoring pipeline (not a standalone
teacher-facing metric per the ticket).

**Tooling (all working, don't redo workarounds):**
- Backend: `uv run ruff format|check|mypy|pytest` all work normally.
- Frontend: `pnpm typecheck`/`pnpm test` work directly; `pnpm lint` needs
  `NEXT_PUBLIC_APP_URL` env var passed via `docker exec -e NEXT_PUBLIC_APP_URL=
  http://localhost:3000 ...` (pre-existing container gap, unrelated to M-10).
- Playwright: browser won't launch (Alpine/musl). Don't retry — verify via
  Vitest/RTL instead, note the gap for CI.
- OpenAPI regen after every backend contract change: `docker exec
  iqbalai_v2-api-1 python -m app.openapi_export > frontend/openapi.json` then
  `node_modules/.bin/openapi-typescript ./openapi.json -o src/lib/api/schema.d.ts`
  from frontend/.

**Out of scope reminder:** M-11 (publish/quiz) and M-12 (viewer) — do not implement.
**Pre-existing untouched changes on disk (not mine, leave alone):** api/app/features/
student_onboarding/service.py, api/app/features/tos/service.py,
frontend/src/lib/__tests__/auth.test.ts, frontend/src/lib/auth.ts, ./Untitled,
infrastructure/authentik/apply_login_branding.py

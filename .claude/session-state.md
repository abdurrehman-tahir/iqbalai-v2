# Session state (live)

**Milestone:** M-10 Lecture Edit + Versions + 7-Dim Scoring
**Branch:** milestone/M-10-lecture-edit-scoring (forked from M-09 tip — M-09 PR #30
still OPEN/unmerged; flagged in PR description, retarget to staging once #30 merges)

**Done (SHAs in the M-10 backlog file, not repeated here):**
- T-129 data model. T-130 TipTap editor/save (Playwright @smoke authored,
  NOT runnable — Alpine/musl container, no glibc Chromium). T-131 voice
  dictation (REST, not T-121's WS). T-132 image upload + AI diagram
  suggestions (reused reference chunks, no new vision pipeline; school-only
  suggestions). T-133 effort tracking (Page Visibility pause/resume, refs
  not state, normalize() formula flagged as an assumption).
- T-134 (8569aaf) — 7-dim scoring: separate LLM call (task="scoring" ->
  SCORING_MODEL), chained Celery task off generation + every save, queue
  `default` (no `lecture_score` queue exists — ARCH §10.2 locks 4 names).
  voice_quality/ai_learning locked rules enforced in code, not trusted to
  the LLM. Reads teacher_ai_memory as Innovation Record stand-in (T-138 not
  built yet — empty context handled gracefully).
- T-135 (99d20e7) — originality check: embeds each version (BGE-M3, 1
  vector/version), compares vs global cross-school index (school) or own
  prior versions only (independent, reuses their personal Qdrant namespace).
  >0.85 similarity -> SchoolLecturePlagiarismFlag + new `system` notification
  namespace fan-out to all Platform Admins (identity never exposed). No
  publish action exists yet (M-11) so indexing runs on every save, not
  gated on PUBLISHED — flagged as an interpretation in the backlog notes.
  1080 total backend tests green.

**Current ticket:** T-136 (topic relevance percentage) — next up
**Next:** invoke ticket-loader for T-136.

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

# Session state (live)

**Milestone:** M-10 Lecture Edit + Versions + 7-Dim Scoring
**Branch:** milestone/M-10-lecture-edit-scoring (forked from M-09 tip — M-09 PR #30
still OPEN/unmerged; flagged in PR description, retarget to staging once #30 merges)

**Done:**
- T-129 (fbba2bb, fe88afa) — edit/scoring data model.
- T-130 (099c62b, ee35ac7, 76147a1, 09351dc) — TipTap editor, save/autosave,
  immutable versioning. Playwright @smoke authored, NOT run (Alpine/musl
  container can't launch Chromium).
- T-131 (ed39a24) — voice dictation via faster-whisper (REST, not T-121's WS
  pipeline — deliberate, documented). 220 backend / 301 frontend tests green.

**Current ticket:** T-132 (image upload + AI diagram suggestions) — next up
**Next:** ticket-loader T-132 → check `lecture_image` upload profile in
api/app/features/files/profiles.py (may not exist yet — T-129/T-130 dossiers
flagged ARCH §11.19 as the source, unconfirmed) → MinIO upload + insert into
TipTap editor + reference-book diagram suggestion (uses M-04 ingested content).

**Tooling (all working now, don't redo workarounds):**
- Backend: `uv run ruff format|check|mypy|pytest` all work normally
  (api/uv.lock fixed in 76147a1).
- Frontend: `pnpm typecheck`/`pnpm test` work directly; `pnpm lint` needs
  `NEXT_PUBLIC_APP_URL` env var (pass via `docker exec -e NEXT_PUBLIC_APP_URL=
  http://localhost:3000 ...` — pre-existing container gap, unrelated to M-10).
- Playwright: browser won't launch (Alpine/musl, confirmed via two install
  attempts). Don't retry — verify equivalent behavior via Vitest/RTL instead.
- OpenAPI regen: `docker exec iqbalai_v2-api-1 python -m app.openapi_export
  > frontend/openapi.json` then `node_modules/.bin/openapi-typescript
  ./openapi.json -o src/lib/api/schema.d.ts` from frontend/ — do this after
  every backend contract change, before touching frontend API client code.

**Out of scope reminder:** M-11 (publish/quiz) and M-12 (viewer) — do not implement.
**Pre-existing untouched changes on disk (not mine, leave alone):** api/app/features/
student_onboarding/service.py, api/app/features/tos/service.py,
frontend/src/lib/__tests__/auth.test.ts, frontend/src/lib/auth.ts, ./Untitled,
infrastructure/authentik/apply_login_branding.py

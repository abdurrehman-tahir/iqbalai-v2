# Session state (live)

**Milestone:** M-10 Lecture Edit + Versions + 7-Dim Scoring
**Branch:** milestone/M-10-lecture-edit-scoring (forked from M-09 tip — M-09 PR #30
still OPEN/unmerged; flagged in PR description, retarget to staging once #30 merges)

**Done (SHAs + full detail in the M-10 backlog file, not repeated here):**
T-129 data model. T-130 TipTap editor/save (Playwright @smoke authored, NOT
runnable here — Alpine/musl). T-131 voice dictation. T-132 image upload + AI
diagram suggestions. T-133 effort tracking. T-134 7-dim LLM scoring (queue
`default`, no dedicated queue exists). T-135 originality check (global
cross-school index for school tenant, tenant-isolated for independent, new
`system` notification namespace). T-136 topic relevance gauge (native
`<progress>`, not a styled div — repo ESLint bans `style` outright, T-226).
T-137 score timeline chart (new paginated GET .../versions list endpoint,
reuses LectureVersionRead; Recharts LineChart, first chart in this repo,
dir="ltr" wrapper for the RTL acceptance per ARCH §13.12). T-138 Teaching
Innovation Record (new teacher_coaching feature: router/service/repository/
schemas x2 tenants; suggestion generated on FIRST weakness detection per
the spec's own lifecycle diagram, not after N recurrences; adapts angle
only once a prior suggestion got a response; also injects pending tips into
the generation prompt, mirroring T-120's exam-overlay pattern).

T-134/135/136/138's weakness-detection step all run from `scoring.py`'s two
tenant functions, each its own decoupled try/except so one failing never
discards the others.

**Current ticket:** T-139 (anonymized benchmarking + admin comparative
metrics) — next up
**Next:** invoke ticket-loader for T-139.

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

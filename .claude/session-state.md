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

T-139 anonymized benchmarking + admin comparative metrics (#37/#38) — DONE.
benchmark_service.py/benchmark_repository.py/benchmark_tasks.py (weekly
beat, queue=ml, Sunday 01:00 PKT) + GET/POST /teachers/me/benchmarks
(school-only). New admin_metrics feature (router/service/repository/schemas)
for #38: GET + CSV export /admin/teacher-metrics, scoped by ROLE_HIERARCHY
mirroring schools/service.py's Platform/District/School precedent, Redis-
cached 1h (first cache-aside pattern in this repo). Frontend: BenchmarkCard
(school wizard only) + TeacherMetricsClient shared across all 3 admin
shells via thin page.tsx re-exports. Commits: backend 5ff9929, frontend
5eba0a8, docs cca4ed2. Full gotcha list in the M-10 backlog file.
Noted-but-not-fixed (pre-existing, out of scope): GenerationStreamPanel.test.tsx
now fails 6 tests under both full-suite and isolated runs (untouched by
T-139); ur/sd/ps locales are missing ~777 keys present in en (whole
namespaces like district_admin.* never got translated in an earlier
milestone) — T-139 only added its own new keys with TODO placeholders.

T-140 notifications + audit + E2E (final M-10 ticket) — implementation DONE,
NOT yet committed. Notifications: 3 new `lectures.*` template keys
(scoring_complete, coaching_suggestion, benchmark_updated; 4 locales, no
__TODO__) wired from scoring.py (post-commit, both tenants), teacher_coaching
service.py (once per scoring run, not per dimension), benchmark_service.py
(per updated teacher, batch wrapped so a notify failure can't fail the beat).
`system.plagiarism_flagged` was already done in T-135 — confirmed, not
re-touched. Audit: 4 new M10_AUDIT_ACTIONS (admin_metrics.accessed/exported
— elevated sensitive-reads; benchmark.opt_out_toggled — routine, not
elevated; lecture.plagiarism_flagged — elevated, system-raised) wired into
admin_metrics/router.py, teacher_coaching/router.py, scoring.py's
_raise_plagiarism_flag. Admin-override audit was already done pre-M10
(LECTURE_ACCESS_OVERRIDDEN, T-123) — confirmed, nothing new needed there.
E2E: Playwright spec authored at frontend/e2e/lecture-scoring-benchmark-e2e.spec.ts
(NOT runnable here, same Alpine/musl gap as always) — plus a genuinely
runnable backend chain test at
api/app/features/lectures/tests/test_m10_e2e_flow.py proving
scoring->benchmark->admin-metrics connect and asserting version immutability
+ the two different privacy tiers (anonymized teacher view vs. named admin
view). All new/changed backend files pass format/lint/mypy --strict; full
app/ mypy baseline confirmed clean; full backend test suite (367 tests
across lectures/teacher_coaching/admin_metrics/audit) passes. Frontend
typecheck/lint clean. Frontend full suite: 336/342 pass — the same 6
pre-existing GenerationStreamPanel.test.tsx failures persist (confirmed
untouched by any M-10 work via git status; now failing consistently, not
just intermittently — flag clearly in the PR as a pre-existing gap, do not
attempt to fix under T-140's scope).
T-140 fully committed: backend 65082d7, frontend/e2e df4effc, docs 75b3931
(also updated the milestone-level Status: done in the M-10 backlog file's
own header — ROADMAP.md itself was deliberately left untouched, it's
script-auto-verified by scripts/check_ticket_status.py on PR, "do not
hand-edit" per its own header).

**M-10 MILESTONE: all 12 tickets (T-129–T-140) done and committed.**
**Next:** run `phase-complete-review` skill, then open the PR
`milestone/M-10-lecture-edit-scoring` -> `staging` per WORKFLOW Step 2,
flagging in the PR description: (1) M-09 PR #30 still open/unmerged — this
branch forked from its tip, retarget once #30 merges; (2) Playwright can't
run in this dev container (Alpine/musl) — E2E specs are authored, not
executed here; (3) the pre-existing GenerationStreamPanel.test.tsx
flakiness (untouched by M-10, now failing consistently not intermittently);
(4) the pre-existing ~777-key ur/sd/ps translation gap from earlier
milestones (M-10 only kept its own new keys in sync). Then send the user
the PR link.

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

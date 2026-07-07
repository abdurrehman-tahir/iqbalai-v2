# Session state (live — Claude Code updates this)

**Current milestone:** M-07 — Exam Framework Engine
**Branch:** milestone/M-07-exam-framework (created off milestone/M-06-student-onboarding)
**Current ticket:** T-099 — E2E smoke test (next)

## Plan
- Branch made off M-06. When M-06 merges to staging, REBASE this branch onto staging (deferred — external event).
- Implement T-091..T-100 one ticket per commit.

## Done this milestone
- T-091 — data model (3 tables + dual-head views) — commit 864b378
- T-092 — Framework definition CRUD (Platform Admin, DRAFT) — commit 6986b64
- T-093 — Pattern-A AI research agent (SearXNG → web_fetch → LLM synthesis) — commit f930079
- T-094 — Approval workflow (PENDING_APPROVAL → PUBLISHED, SLA reminder@7d/escalation@14d) — commit 9625fb5
- T-095 — Versioning + quarterly refresh + deprecation (refresh beat, deprecate, refresh-safe reverts) — commit 863f5ed
- T-096 — Student framework selection + rendering + region scoping (both tenants; /student/exam-frameworks) — commit d0d7eb4
- T-097 — Notifications: system (admin) + self_study (student) namespaces; NATS events; 4-lang templates — commit 51284d0
- T-098 — Audit logging: M07_AUDIT_ACTIONS registry + 4 new audit() calls (create/update/delete/research_triggered) + elevated flags — this commit

## T-097 notes
- User decided: reuse existing §9.21 namespaces (system for admin, self_study for student v2-available), NOT a new `framework` namespace. No amendment.
- pre-commit hook is NOT installed in this clone → my commits don't run ruff/mypy locally; CI (`uv run ruff check .` + `ruff format --check .`) is the real gate. RUN THE FORMAT GATE MANUALLY via api/.venv before each commit.
- Added `[tool.ruff.lint.per-file-ignores]` for notifications/templates/*.py = ["E501"] — fixes latent E501 in the pre-existing connections.py template too (would otherwise fail T-100 CI).
- LATENT RISK for T-100: `ruff check .` runs whole repo; there may be other pre-existing lint issues outside exam_frameworks. Check at PR time.

## T-096 notes
- Legacy independent-signup selection uses `exam_syllabi` (older table), NOT the T-091 `exam_frameworks` engine. T-096 built the real selection engine ALONGSIDE the legacy syllabus path (did not touch signup). Reconciling the two is a product decision for Abd. — flagged, not done.
- Student region is NOT stored on profile (only grade_level). Region+grade are caller-supplied query params on /available. The filtering engine is what T-096 ships.
- `student` i18n namespace is en-only in this repo (ur/sd/ps carry only app/nav/landing/common/auth/admin) — student.frameworks added to en only, consistent with existing student.dashboard/data-rights.
- User's uncommitted M-07b drafts (login milestone) + ROADMAP/_CHANGE_LOG edits are NOT mine — keep them OUT of M-07 commits.

## Notes / gotchas
- Migrations hand-authored in established style (env.py only imports Base; no autogenerate registry).
- Platform-shared tables live in `school` schema; independent schema gets read-only cross-schema views (§3.16/§4.21).
- Register new model modules' imports in tests/test_model_metadata.py for the offline FK/enum lint.
- School head: school_0041. Independent head: independent_0006.

## Pre-existing defects (NOT T-093; awaiting user decision to fix separately)
- graduation_requests.school_id FK missing index=True (M-06 commit 9aca648) — fails test_every_foreign_key_has_ondelete_and_index under cross-test model registration.
- Unused `useEffect` import in IndependentStudentOnboardingClient.tsx (M-05 commit 0e9f6b5) — fails whole-project `next lint`.

# Session state (live — Claude Code updates this)

**Current milestone:** M-07 — Exam Framework Engine
**Branch:** milestone/M-07-exam-framework (created off milestone/M-06-student-onboarding)
**Current ticket:** T-096 — Student framework selection + study-plan rendering + region scoping (next)

## Plan
- Branch made off M-06. When M-06 merges to staging, REBASE this branch onto staging (deferred — external event).
- Implement T-091..T-100 one ticket per commit.

## Done this milestone
- T-091 — data model (3 tables + dual-head views) — commit 864b378
- T-092 — Framework definition CRUD (Platform Admin, DRAFT) — commit 6986b64
- T-093 — Pattern-A AI research agent (SearXNG → web_fetch → LLM synthesis) — commit f930079
- T-094 — Approval workflow (PENDING_APPROVAL → PUBLISHED, SLA reminder@7d/escalation@14d) — commit 9625fb5
- T-095 — Versioning + quarterly refresh + deprecation (refresh beat, deprecate, refresh-safe reverts) — this commit

## Notes / gotchas
- Migrations hand-authored in established style (env.py only imports Base; no autogenerate registry).
- Platform-shared tables live in `school` schema; independent schema gets read-only cross-schema views (§3.16/§4.21).
- Register new model modules' imports in tests/test_model_metadata.py for the offline FK/enum lint.
- School head: school_0041. Independent head: independent_0006.

## Pre-existing defects (NOT T-093; awaiting user decision to fix separately)
- graduation_requests.school_id FK missing index=True (M-06 commit 9aca648) — fails test_every_foreign_key_has_ondelete_and_index under cross-test model registration.
- Unused `useEffect` import in IndependentStudentOnboardingClient.tsx (M-05 commit 0e9f6b5) — fails whole-project `next lint`.

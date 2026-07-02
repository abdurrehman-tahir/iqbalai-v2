# Session state (live — Claude Code updates this)

**Current milestone:** M-07 — Exam Framework Engine
**Branch:** milestone/M-07-exam-framework (created off milestone/M-06-student-onboarding)
**Current ticket:** T-093 — Pattern-A AI research agent (next)

## Plan
- Branch made off M-06. When M-06 merges to staging, REBASE this branch onto staging (deferred — external event).
- Implement T-091..T-100 one ticket per commit.

## Done this milestone
- T-091 — data model (3 tables + dual-head views) — commit 864b378
- T-092 — Framework definition CRUD (Platform Admin, DRAFT) — commit 6986b64

## Notes / gotchas
- Migrations hand-authored in established style (env.py only imports Base; no autogenerate registry).
- Platform-shared tables live in `school` schema; independent schema gets read-only cross-schema views (§3.16/§4.21).
- Register new model modules' imports in tests/test_model_metadata.py for the offline FK/enum lint.
- School head: school_0041. Independent head: independent_0006.

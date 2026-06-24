# Session state (live — Cursor agent updates this)

**Current milestone:** M-03 — Subjects + Grade/Section/Subject offerings (PR opened → staging)
**Branch:** milestone/M-03-grade-section-subject
**Current ticket:** T-052 — Milestone PR + demo — DONE (PR opened)

## Done this milestone
- T-041 through T-051 — all implemented and committed on branch.
- Post-demo fixes: grades/offerings actor lookup by `authentik_id`; `school_0027` aligns `users.role` column with ORM enum; assign-modal loading/error/empty states + en i18n keys.

## Next milestone
- M-04 — Teacher onboarding (see `docs/backlog/M-04-teacher-onboarding.md`)

## Carry-forward flags for the M-03 PR
- Non-en `coordinator` i18n namespace missing (ur/sd/ps) — inherited from M-02, not introduced by M-03.
- Frontend Playwright E2E for grade-detail offerings assign flow not added (T-051 backend harness only).

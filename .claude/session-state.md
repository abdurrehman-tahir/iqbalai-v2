# Session state (live — Claude Code updates this)

**Current milestone:** M-03 — Subjects + Grade/Section/Subject offerings
**Branch:** milestone/M-03-grade-section-subject (off M-02 HEAD; staging lacks M-02's commits yet → stacked branch)
**Current ticket:** T-041 — Subject catalog — DONE (committed). Next: T-042.

## Done this milestone
- T-041 — Subject catalog (model + CRUD + Coordinator UI). Backend: `subjects` table (school schema), CRUD + POST /{id}/archive, Coordinator-and-above (§6.19), unique (school_id,name)→409, archive=status enum. Migration school 0021_subjects. 8 pytest pass. Frontend: Coordinator /coordinator/subjects page (4 UI states, create/edit/archive modals), typed client `subjectsApi` from generated SubjectCreate/SubjectUpdate, FE↔BE contract test, Vitest (7) + Playwright @smoke. i18n en-only (ur/sd/ps lack coordinator namespace since M-02 — flag in PR).

## Next ticket — T-042: Academic Session concept + school active-session setting
- See milestone file L79+. Deps: none flagged blocking.

## Carry-forward flags for the M-03 PR
- Non-en `coordinator` i18n namespace missing (ur/sd/ps) — inherited from M-02, not introduced by T-041.
- Pre-existing `client-request-type` lint violations + unformatted .py files in M-02 code (districts/schools/invites) — out of T-041 scope; not touched.

## Dossier source list (T-041)
- Ticket: docs/backlog/M-03-grade-section-subject.md L34-78
- Spec: flow-2-admin-coordinator-setup.md §3.2 L94-112
- ARCH: §3.18, §4.2-4.8, §4.12, §5.1-5.4, §6.19; AMEND A-001

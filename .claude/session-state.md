# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding (from origin/staging @7000c23)
**Current ticket:** T-028 — District + School data model — **done** (committing)
**Ticket dossier loaded:** via general-purpose agent running the ticket-loader procedure (real loader was broken — see below)
**Dossier source files:** docs/backlog/M-02-school-onboarding.md; ARCH §3.3, §3.13; flow-1 §3.1, flow-2 §3.1

**Done this session:**
- Fixed .claude/agents/ticket-loader.md frontmatter tool names (view/bash → Read/Bash/Grep/Glob). Root cause of empty tool output. Takes effect NEXT session (agent defs cached at session start); used general-purpose agent as workaround this session.
- T-028: created api/app/features/schools/ (models.py: District + School), migration school/0012_districts_schools.py, tests in features/schools/tests/test_school_models.py. Flipped T-028 Status→done in milestone file.

**Key decision (Hamza-approved):**
- §3.3 override of T-028 acceptance #2/#4: districts/schools are tenant ROOTS → NO RLS. District-Admin scoping deferred to repo/role layer in T-029. §3.13 cross-tenant test attaches to first tenant-scoped table, not these roots. Ticket's §3.9 cite is stale (RLS lives in §3.3).

**Verified:**
- ruff + mypy --strict clean on features/schools; 10 model tests pass.
- Migration applied + downgraded cleanly on a throwaway PG (full school chain 0001→0012): FK RESTRICT, indexes, unique constraints, seed data, RLS=off all confirmed.
- NOTE: shared dev DB (compose) is at school_0014 from prior milestone_1a checkout — divergent from this branch (ends at 0012). Did NOT touch it.

**Next intended step:** T-029 — Platform Admin creates District: API + UI (depends on T-028).

**Format-gate run:** ruff format/check ✅ mypy --strict ✅ pytest (schools) ✅

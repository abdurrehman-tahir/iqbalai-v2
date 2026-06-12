# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding (from origin/staging @7000c23)
**Current ticket:** T-032 — School Admin invitation + first login + empty dashboard — **done** (ready to commit)
**Dossier source files:** docs/backlog/M-02-school-onboarding.md; flow-2 §3.1/§3.5; ARCH §6.19

**Done this session (T-032):**
- Backend: InviteService school_admin scope validation (district_admin + school_id); invite router allows district_admin; SchoolService get_my_school + cross-school 404; school_admin_router GET /school/admin/school + /schools/{id}.
- Frontend: SchoolsClient invite modal (UserPlus per school); SchoolAdminShell shows school name + Coordinators nav; schoolAdminApi.getMySchool(); /school/admin/coordinators placeholder.
- Tests: invite service (school admin invite, cross-district 404, accept sets school_id); invite API (district_admin school invite); school admin API (3); SchoolsClient invite vitest.

**Verified:** ruff OK (after fix), backend invites+schools pytest 51/51, frontend vitest 40/40.

**Next intended step:** T-033 (User lifecycle: suspend / reactivate / deactivate).

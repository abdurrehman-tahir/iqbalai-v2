# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding (from origin/staging @7000c23)
**Current ticket:** T-031 — District Admin creates School: API + UI — **done** (committed)
**Dossier source files:** docs/backlog/M-02-school-onboarding.md; flow-2 §4/§5.6; ARCH §6.7, §6.19

**Done this session (T-031):**
- Backend: SchoolRepository + SchoolService with district scope (404 cross-tenant); school_router POST/GET/PUT/DELETE /admin/schools; require_role district_admin + platform inheritance; Idempotency-Key on POST; audit school.*; PostLoginResponse adds district_id/school_id.
- Frontend: /admin/district/schools (SchoolsClient); DistrictAdminShell + AdminLayoutSwitch; schoolsApi; role-based post-login redirect (getPostLoginPath); school admin placeholder /school/admin with sidebar stubs.
- Tests: test_school_service(7), test_school_api(4), SchoolsClient vitest(1), auth getPostLoginPath(3).

**Verified:** ruff OK, backend schools+invites pytest 51/51, frontend vitest 39/39, lint + typecheck clean.

**Next intended step:** T-032 (School Admin invitation + first login + empty dashboard).

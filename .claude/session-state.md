# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding
**Current ticket:** T-033 — User lifecycle — **done** (committed)
**Next intended step:** T-034 (Coordinator role: invitation + scope assignment)

**Done (T-033):**
- Migration 0015 useraccountstatus; UserAccountStatus on User model
- UserLifecycleService + admin_router (list/suspend/reactivate/deactivate)
- AuthMiddleware account status check; post-login suspended/deactivated rejection
- Authentik deactivate_user; UsersClient UI at /admin/users (+ district/school routes)
- Tests: lifecycle service (5), admin users API (3), middleware suspended (1), UsersClient vitest (1)

**Verified:** ruff OK, backend users+invites+middleware pytest 39/39, frontend vitest 41/41

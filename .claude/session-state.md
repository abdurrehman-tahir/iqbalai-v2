# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding (from origin/staging @7000c23)
**Current ticket:** T-030 — Path A invitation flow — **done** (committing)
**Dossier source files:** docs/backlog/M-02-school-onboarding.md; flow-2 §3.1/§5.1/§6; ARCH §6.3-§6.4, §6.12

**Done this session (T-030):**
- Backend: migration school/0014 user_invites; features/invites (model, repo, service, router); POST /admin/users, POST /admin/users/{id}/resend, POST /auth/accept-invite; infrastructure/authentik/client.py (dev stub + REST); infrastructure/notifications/email.py (log provider); config APP_URL/AUTHENTIK_*/EMAIL_*; middleware public accept-invite; UserRepository.get_by_email; FakeRedis incr/expire for rate-limit tests.
- Frontend: invite modal on /admin/districts; /accept-invite page; adminUsersApi + authApi.acceptInvite; i18n en + __TODO__ ur/sd/ps; DistrictsClient invite vitest.
- Also fixed pre-existing lint/typecheck: stale @ts-expect-error in platform-admin-smoke.spec.ts; next-intl mock unused _date.

**Verified:** ruff OK, backend invite+schools+idempotency pytest 40/40, frontend vitest 35/35, lint + typecheck clean.

**Next intended step:** T-031 (District Admin creates School: API + UI).

# M-02 — School Onboarding: District + School + Role Hierarchy

**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-028 through T-040
**Spec source:** `flow-2-admin-coordinator-setup.md` v3

## Goal

Platform Admin creates the first District + School. Creates first District Admin, then School Admin who logs in and lands on their school's empty dashboard. Sets up the user lifecycle (PENDING_INVITE → ACTIVE → SUSPENDED → DEACTIVATED) per Flow 2 v3 §3.5.

**Demo at milestone end:**
- Platform Admin creates a District ("Punjab District 1")
- Platform Admin creates a District Admin user → invite email sent → user accepts → logs in
- District Admin creates a School ("Sample School")
- District Admin creates a School Admin → invite → logs in → sees empty school dashboard
- All actions audit-logged
- Suspended user attempting to log in is rejected with clear message

---

## T-028 — District + School data model + cross-cutting fields

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 (user creation cascades through hierarchy)
- `flow-1-platform-setup.md` §3.1 (role hierarchy)

### ARCH source
- `ARCHITECTURE.md` §3.1-§3.13 (multi-tenancy — district + school as tenant scopes)
- `ARCHITECTURE.md` §3.9 (RLS policies)

### Depends on
- M-01a (foundation remediation + FE/integration enforcement merged — all M-02 tickets build under the new gates)
- T-007 (DB mixins)

### What this ticket builds

**Backend:** Migrations create `districts` and `schools` tables in school schema. RLS policies: `district_id` and `school_id` scoping enforced. Cross-tenant SELECT blocked per §3.13.

**Frontend:** No new UI; tables only.

### Acceptance (demo script)

1. [ ] `districts` and `schools` tables exist with correct constraints
2. [ ] RLS policies enforce scope at DB level
3. [ ] Sample district + sample school inserted via migration seed data
4. [ ] Unit tests: cross-district SELECT returns empty per §3.13

### Out of scope

- District/School CRUD endpoints — T-029
- District Admin / School Admin user creation — T-030

---

## T-029 — Platform Admin creates District: API + UI

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §4 (permissions matrix — Platform Admin creates District Admin/District)
- `flow-2-admin-coordinator-setup.md` §3.1 Path A
- `flow-2-admin-coordinator-setup.md` §5.6 (cross-tenant denial)

### ARCH source
- `ARCHITECTURE.md` §5.1 (URL patterns), §5.9 (Idempotency-Key for POSTs)
- `ARCHITECTURE.md` §6.7 (`require_role('platform_admin')`)
- `ARCHITECTURE.md` §6.19 (inheritance — already locked)

### Depends on
- T-028 (District table)

### What this ticket builds

**Backend:** `POST/GET/PUT/DELETE /api/v1/admin/districts`. `require_role('platform_admin')` per inheritance. Idempotency-Key support on POST. Soft-delete only.

**Frontend:** `/admin/districts` page: list + create modal. Form fields: name, region, language preference.

### Acceptance (demo script)

1. [ ] Platform Admin creates "Punjab District 1" via UI
2. [ ] District row created; audit log entry
3. [ ] District Admin role attempting to access this endpoint → 403
4. [ ] Idempotency-Key replay returns same district_id (no duplicate)
5. [ ] Soft-delete works; subsequent GET excludes deleted

---

## T-030 — Path A invitation flow: invite email + 7-day token + accept flow

**Layer:** 1
**Milestone:** M-02
**Estimate:** 3 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 (Path A admin invitation flow)
- `flow-2-admin-coordinator-setup.md` §5.1 (edge cases — duplicate email, bounce, expiry, lockout)
- `flow-2-admin-coordinator-setup.md` §6 (limits — 200 invites/admin/day, 7-day TTL)

### ARCH source
- `ARCHITECTURE.md` §6.3-§6.4 (Authentik integration)
- `ARCHITECTURE.md` §6.12 (Authentik admin sync)

### Depends on
- T-004 (Authentik), T-008 (require_role), T-029 (District CRUD)

### What this ticket builds

**Backend:** Migration adds `user_invites` table per ledger DB plan. Endpoint `POST /api/v1/admin/users` creates Authentik user (suspended) + sends invite email with 7-day token. Endpoint `POST /api/v1/auth/accept-invite` activates Authentik user + creates User row in internal table. Email sender: `infrastructure/email/` (SMTP container or Resend client per STACK_LOCK).

**Frontend:** Modal in `/admin/districts` (after T-029) and `/admin/schools` (T-031) to invite next-level admin. Accept-invite page at `/accept-invite?token=...`.

### Acceptance (demo script)

1. [ ] Platform Admin invites District Admin via modal
2. [ ] Email sent (logged to MailHog in dev)
3. [ ] District Admin clicks link → password setup → activates
4. [ ] User row in `school.users` with role=`district_admin`, scope set to created district
5. [ ] Expired token (>7 days) shows error
6. [ ] Re-invite resends new token
7. [ ] 3-rejection lockout triggers per Flow 2 §5.1
8. [ ] Audit log per invite + acceptance

### Out of scope

- School user signup (Path B) — that's only for independents, M-05
- Bulk import — Flow 2 §3.1, but Coordinator-driven (M-06)

---

## T-031 — District Admin creates School: API + UI

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §4 permissions matrix
- `flow-2-admin-coordinator-setup.md` §5.6 cross-tenant denial

### ARCH source
- `ARCHITECTURE.md` §6.7 (`require_scope`)
- `ARCHITECTURE.md` §6.19 (inheritance)

### Depends on
- T-029 (District), T-030 (Invite flow)

### What this ticket builds

**Backend:** `POST/GET/PUT/DELETE /api/v1/admin/schools` per `require_role('district_admin')` + `require_scope(district_id)`. Inheritance: Platform Admin can create School in any district.

**Frontend:** District Admin dashboard `/admin/district/schools` shows their schools. School Admin dashboard placeholder (empty).

### Acceptance (demo script)

1. [ ] District Admin logs in, lands on district dashboard
2. [ ] Creates "Sample School" within their district
3. [ ] District Admin from another district → 404 attempting same school
4. [ ] Platform Admin → can create across districts
5. [ ] Audit log entries

---

## T-032 — School Admin invitation + first login + empty dashboard

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 Path A continued
- `flow-2-admin-coordinator-setup.md` §3.5 user lifecycle

### ARCH source
- `ARCHITECTURE.md` §6.19 inheritance

### Depends on
- T-030 (invite flow), T-031 (School creation)

### What this ticket builds

**Backend:** Reuses T-030 invite endpoint with `role=school_admin`. School Admin User row scoped to school_id.

**Frontend:** School Admin dashboard `/school/admin/` — empty placeholder with sidebar (Users, Coordinators, Teachers — coming in M-03, M-04). Header with school name + user info.

### Acceptance (demo script)

1. [ ] District Admin invites School Admin
2. [ ] School Admin accepts → logs in → lands on `/school/admin/`
3. [ ] Sidebar shows nav items (placeholder pages)
4. [ ] Cross-school access → 404

---

## T-033 — User lifecycle: suspend / reactivate / deactivate

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.5 (full lifecycle)
- `flow-2-admin-coordinator-setup.md` §5.2 (edge cases)
- `flow-2-admin-coordinator-setup.md` §6 (limits — last active admin floor)

### ARCH source
- `ARCHITECTURE.md` §14.10 audit log

### Depends on
- T-030 (User invites)

### What this ticket builds

**Backend:** Endpoints `POST /api/v1/admin/users/:id/suspend`, `/reactivate`, `/deactivate`. Suspended users blocked at AuthMiddleware (JWT validation includes status check). Deactivated = one-way soft-delete. Last active admin check per §5.2.

**Frontend:** User list page (`/admin/users`) with status badges + actions per role.

### Acceptance (demo script)

1. [ ] Suspend a School Admin → their JWT immediately invalid on next request
2. [ ] Login attempt shows "account suspended" message
3. [ ] Reactivate → can log in again
4. [ ] Deactivate → can't be reactivated
5. [ ] Last Platform Admin cannot self-deactivate → `PRECONDITION_FAILED`
6. [ ] Audit log per state change

---

## T-034 — Coordinator role: invitation + scope assignment

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 (School Admin creates Coordinator)
- `flow-2-admin-coordinator-setup.md` §8 (open questions Q1 — non-contiguous grade scope)
- `flow-2-admin-coordinator-setup.md` §4 permissions matrix

### ARCH source
- `ARCHITECTURE.md` §6.7 `require_scope` (grade scope)

### Depends on
- T-030 (invite flow), T-032 (School Admin dashboard)

### What this ticket builds

**Backend:** Coordinator invitation endpoint. Scope = SET of grade names (non-contiguous allowed per Q1 — e.g., "Grades 6, 9"). Stored in User.scoped_ids as grade name list.

**Frontend:** School Admin dashboard "Coordinators" page: invite form with grade scope multi-select.

### Acceptance (demo script)

1. [ ] School Admin invites Coordinator with scope "Grades 9, 10"
2. [ ] Coordinator accepts, logs in, lands on Coordinator dashboard (placeholder)
3. [ ] Scope shown in user profile
4. [ ] Cross-grade scope writes (in M-03) blocked

---

## T-035 — Teacher role: invitation (individual; bulk in M-04)

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 + §4 (School Admin creates Teacher)
- `flow-3-teacher-onboarding.md` §3.1 (Teacher onboarding starts after invite)

### ARCH source
- N/A (reuses invite flow)

### Depends on
- T-030 (invite flow)

### What this ticket builds

**Backend:** Teacher invite endpoint. Teacher User row created with `role=teacher`, scope=`school_id`.

**Frontend:** School Admin "Teachers" page: invite form. Teacher dashboard placeholder (`/teacher/`) — empty until M-04 onboarding flow.

### Acceptance (demo script)

1. [ ] School Admin invites Teacher
2. [ ] Teacher accepts, logs in, lands on empty teacher dashboard
3. [ ] Audit log entries

### Out of scope

- Teacher profile completion — M-04 (Flow 3)
- Bulk teacher import — Phase 2 per TODO

---

## T-036 — Permission inheritance integration tests

**Layer:** 1
**Milestone:** M-02
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §4 permissions matrix

### ARCH source
- `ARCHITECTURE.md` §6.19

### Depends on
- T-029, T-031, T-034, T-035

### What this ticket builds

Integration test suite: for each row × column in Flow 2 v3 §4 permissions matrix, verify the endpoint returns correct status (200 / 403 / 404). Covers Coordinator/School Admin/District Admin/Platform Admin combinations.

### Acceptance

1. [ ] Test suite runs in CI
2. [ ] All matrix cells validated
3. [ ] Inheritance verified: higher roles can do lower-role actions within scope

---

## T-037 — Bulk import skeleton (uploads CSV) — Coordinator owned but no real data yet

**Layer:** 1
**Milestone:** M-02
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 (bulk import by Coordinator)
- `flow-2-admin-coordinator-setup.md` §5.4 (edge cases — invalid rows, duplicate emails)
- `flow-2-admin-coordinator-setup.md` §6 (limits — 5000 rows, 5 MB)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`bulk_import` upload profile)

### Depends on
- T-013 (upload pipeline), T-034 (Coordinator role)

### What this ticket builds

**Backend:** `bulk_import` profile in upload registry. Endpoint `POST /api/v1/coordinator/bulk-imports` accepts CSV/XLSX. Validates rows. Stores job in `bulk_imports` table. Per-row results in JSONB. Actual student enrollment happens in M-06; for now, just validation + dry-run.

**Frontend:** Coordinator dashboard "Bulk Import" page: upload form, dry-run results table, commit button (disabled until M-06).

### Acceptance

1. [ ] Coordinator uploads sample CSV (50 rows)
2. [ ] Dry-run validates per row, shows errors
3. [ ] No actual user creation yet (commit button shows "Coming in M-06")

### Out of scope

- Actual commit + user creation — M-06

---

## T-038 — Notifications for M-02 events (account namespace)

**Layer:** 1
**Milestone:** M-02
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §7 (notification table)

### ARCH source
- `ARCHITECTURE.md` §9.21

### Depends on
- T-023 (notification infra)

### What this ticket builds

Wire notification publishers for: invite_sent, invite_expired, invite_accepted, account.suspended, account.reactivated, account.deactivated, account.bulk_import_done.

### Acceptance

1. [ ] All 7 template keys fire correctly
2. [ ] Recipients receive in-app + email per Flow 2 §7
3. [ ] All 4 languages

---

## T-039 — Frontend School Admin "Audit Log" page (scope-restricted)

**Layer:** 1
**Milestone:** M-02
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §9 (audit log queryable — last 50)

### Depends on
- T-025 (audit log infra)

### What this ticket builds

School Admin dashboard "Audit Log" page: scoped to own school. Shows last 50 entries.

### Acceptance

1. [ ] School Admin sees own school's last 50 audit entries
2. [ ] Cannot see other schools' audit logs

---

## T-040 — Milestone M-02 PR + demo

**Layer:** 1
**Milestone:** M-02
**Estimate:** 0.5 days
**Status:** todo

PR with demo video showing District → School → Admin → Coordinator → Teacher flow.

---

## Milestone done — when

All 13 tickets complete. Hierarchy stood up. Ready for M-03 (Grade/Section/Subject + Coordinator/Teacher Setup).

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Initial M-02. 13 tickets. | @abdurrehman (with Claude) |

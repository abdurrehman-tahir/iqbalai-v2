# Flow 2 — Admin & Coordinator Setup

**Status:** draft (v3 — Grade/Section/Subject restructure, promotion workflow with exclusion + approval, manual signup for independents, all roles from start, permission inheritance)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy, esp. §3.16 independent tenant, §3.18 Grade/Section/Subject model NEW, §3.17 subscription), §4 (DB patterns), §6 (auth, §6.19 inheritance, §6.20 independent signup, §6.21 promotion approval workflow NEW), §9.21 (notification namespaces), §10 (Celery), §11.19 (bulk import upload profile), §13 (i18n), §14.10 (audit log)
**Related feature specs:** `flow-1-platform-setup.md`, `flow-3-teacher-onboarding.md`, `flow-4-student-onboarding.md`, `flow-11-group-study-dashboards.md`, `flow-13-subscriptions.md`
**v2 doc features covered:** #2, #3, #4, #5

---

## 1. Purpose

After Flow 1 establishes the platform foundation, Flow 2 populates the operational hierarchy: Platform Admin creates District Admins; District Admins create School Admins; School Admins create Coordinators + Teachers; Coordinators enroll Students. These admin roles also define the **academic structure of each school** — the Grade / Section / Subject model — which Teachers and Students attach to.

The flow's primary job is to **stand up a usable school in the system before any Teacher or Student arrives**. It owns:

- **User creation across all 6 hierarchy levels** (#2) — admin-invitation model for school users; manual public signup for independent users
- **User lifecycle** (#3) — suspend / reactivate / deactivate with audit trail
- **Subject catalog management** (#4) — school-scoped subject definitions
- **Grade / Section / Subject offering structure** (#5) — the new model replacing "Class"
- **Promotion workflow** — Coordinator initiates per-grade promotion; School Admin approves; exclusion list for held-back students; auto-graduation at final grade

Admin dashboards live in Flow 11. Flow 2 owns the setup actions; Flow 11 owns the read-only oversight surfaces.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **Platform Admin** | Creates District Admins. Per §6.19 inheritance, can act as any lower role across all tenants. |
| **District Admin** | Created by Platform Admin. Creates School Admins within own district. Per §6.19, inherits all permissions of School Admin / Coordinator / Teacher across all schools in district. |
| **School Admin** | Created by District Admin. Creates Coordinators + Teachers within own school. Owns subject catalog. Approves promotion requests. Per §6.19, inherits all Coordinator + Teacher permissions within school. |
| **Coordinator** | Created by School Admin. Assigned a scope (e.g., Grades 9 + 10). Within scope: creates Grades + Sections, manages Grade-Subject offerings, assigns Teachers to offerings, enrolls Students into Grade-Sections (bulk + individual), initiates promotion requests. |
| **Teacher** | Created by School Admin. Assigned to Grade-Subject offerings by Coordinator. Onboarding details live in Flow 3. |
| **Student / Parent** | Created via Coordinator enrollment (school students per Flow 4) or via manual public signup (independent users per Flow 4 v3 §3.2). Consume Flow 2 outputs but no admin access. |
| **Independent Teacher / Independent Student** | Self-signup via public form per Flow 1 §6.20. Live in `independent` tenant. No admin hierarchy applies to them. |

---

## 3. Lifecycle

### 3.1 User creation lifecycle (#2) — TWO PATHS

**Path A: Admin invitation (school users — Teachers, Students, Coordinators, School Admins, District Admins).** Same as v2 — invite link → user activates.

**Path B: Manual public signup (independent users + School Admin's school first user when needed).** New per v3 feedback. Public landing page at `/signup` or `/independent/signup` per role.

#### Path A — Admin invitation flow

```
   PENDING_INVITE             (admin creates record; invite email sent; 7-day token)
       ↓ user clicks invite link, sets password (or completes Authentik SSO)
   ACTIVE                     (can log in, can use the app)
       ↓ admin action
   SUSPENDED                  (cannot log in; data intact; reversible)
       ↓ admin action
   ACTIVE again
       OR
       ↓ admin action
   DEACTIVATED                (logically deleted; soft-deleted record; cannot be reactivated)
```

#### Path B — Manual public signup flow (independent users)

```
   PUBLIC_SIGNUP_FORM         (minimalist UI: email + password + role + minimal info)
       ↓ email verification via Authentik
   ACTIVE                     (lives in `independent` tenant per §3.16)
       ↓ standard onboarding (per Flow 4 v3 / Flow 3 v3)
```

**Locked rules (both paths):**
- Email globally unique across all roles + tenants.
- 7-day invite token TTL; resendable (per Path A).
- 3-rejection lockout (per Path A): if invite is rejected 3 times → admin can resend after 30 days.
- Deactivation is one-way at launch (creates new account if user needs to return).
- Path B applies ONLY to independent users at launch per v3 Q21. School users use Path A only.

**Permission inheritance for user creation per §6.19:**

| Action | Platform Admin | District Admin | School Admin | Coordinator |
|---|:---:|:---:|:---:|:---:|
| Create District Admin | ✅ | — | — | — |
| Create School Admin | ✅ (any district) | ✅ (own district) | — | — |
| Create Coordinator | ✅ | ✅ (any school in district) | ✅ (own school) | — |
| Create Teacher | ✅ | ✅ (any school in district) | ✅ (own school) | — |
| Create / bulk-import Student | ✅ | ✅ (any school in district) | ✅ (own school) | ✅ (own scope) |

District Admins and School Admins inherit downward (per §6.19) — they can create any lower role within their scope.

### 3.2 Subject catalog lifecycle (#4)

A subject is a school-scoped catalog entry (e.g., "Physics" for School X). Subjects don't expire; they live across academic years.

```
   CREATED                    (Coordinator OR School Admin creates a subject in catalog)
       ↓ rare edit
   EDITED                     (name change, language)
       ↓ admin action
   ARCHIVED                   (not offered to new grades; existing offerings retained)
```

**Locked rules:**
- A subject is `{school_id, name, language}`. The (school_id, name) tuple is unique within school but not globally.
- Per v3 feedback Q15: **Coordinator owns subject catalog creation AND management.** Simpler than splitting "catalog" vs "offering" ownership. Coordinator does both.
- School Admin inherits the right to create/edit/archive subjects per §6.19.
- A subject is independent of any specific Grade. It's a name + language + school. It only becomes "offered" when a GradeSubjectOffering record exists.
- Archiving a subject: blocked if active GradeSubjectOfferings exist; admin must archive offerings first.

### 3.3 Grade / Section / Subject offering lifecycle (#5) — NEW per v3 feedback

The new model. Grade is the primary entity. Sections are optional children. Subjects are offered to a Grade for a specific academic session.

```
GRADE LIFECYCLE:
   GRADE_CREATED              (Coordinator creates a Grade for an academic session)
       ↓ optionally add Sections
   ACTIVE                     (students enrolled; teachers assigned via offerings)
       ↓ promotion (per §3.4)
   PROMOTED_TO_NEXT            (Grade rolls forward; new instance for next session)
       OR
       ↓ end-of-session
   ARCHIVED                    (historical Grade record retained)

SECTION LIFECYCLE:
   SECTION_CREATED            (Coordinator creates A/B/C under a Grade)
       ↓ students enroll
   ACTIVE
       ↓ Grade archived
   ARCHIVED

GRADE-SUBJECT OFFERING LIFECYCLE:
   OFFERING_CREATED           (Coordinator OFFERS Subject X to Grade Y for session Z)
       ↓ Coordinator assigns Teacher (consumes teacher capacity per Flow 3 v3 §3.5)
   TEACHER_ASSIGNED
       ↓ year ends + promotion
   ARCHIVED                   (historical)
```

**Locked rules:**

- **Grade entity:** `{school_id, name (e.g., "Grade 9"), academic_session (e.g., "2025-2026"), promoted_from_grade_id (nullable, previous session's Grade)}`. Unique (school_id, name, academic_session).
- **Section entity (OPTIONAL):** `{grade_id, name (e.g., "A", "B")}`. A Grade may have 0 Sections (small schools — students enroll into Grade directly via a "default" section internally) or N Sections. Per Q11.
- **GradeSubjectOffering:** `{grade_id, subject_id, assigned_teacher_id (nullable until Coordinator assigns)}`. One Subject offered per Grade per session. Same Subject (e.g., "Physics") can be offered to multiple Grades (9, 10, 11), each its own offering with potentially different teacher.
- **Teacher assignment level:** at the GradeSubjectOffering level (not per-Section). Per Q13 — all Sections of Grade 9 share the same Physics teacher. Per-Section teacher assignment deferred to Phase 2.
- **Teacher capacity consumed per Grade-Subject assignment** per Flow 3 v3 §3.5 (default cap = 5).
- **Student enrollment:** into a Section (which is under a Grade). If no Sections exist, enrollment goes into a default-internal section. Each enrollment has academic_session pinned.
- **Bulk import** (CSV/XLSX): Coordinator imports students into a Grade-Section. Owned by Coordinator per v3 feedback (was School Admin in v2).
- **Cross-grade subject linking from v1/v2 removed** — replaced by the GradeSubjectOffering model + cross-grade lecture linking per Flow 5 #21 (unidirectional).

### 3.4 Promotion workflow lifecycle (NEW per v3 Q6, Q18-Q23)

Year-end promotion of an entire Grade to the next session's Grade. Coordinator initiates with exclusion list; School Admin approves; bulk atomic transaction.

```
   ELIGIBLE_FOR_PROMOTION     (Grade in current session; year-end approaches)
       ↓ Coordinator initiates promotion request
   PENDING_APPROVAL           (request includes target Grade name + session + exclusion list of student_ids)
       ↓ School Admin sees in their approval queue + notification
   APPROVED OR REJECTED
       ↓ if APPROVED
   EXECUTING                  (atomic Celery transaction; bulk migrate students; create next-session Grade record)
       ↓ complete
   EXECUTED                   (students in target Grade; excluded students remain in original Grade with new academic_session reset)
```

**Locked rules:**

- **Per-grade initiation** (Q18): Coordinator initiates for one Grade at a time. Bulk-promote-all deferred to Phase 2.
- **Exclusion list source** (Q19): manual checkboxes by Coordinator at promotion time. Coordinator sees the full Grade roster; checks "stay in Grade X for next session" for held-back students. Per coaching-not-grading: IqbalAI doesn't track pass/fail itself; this list comes from school's external records.
- **Approval gate** (Q21): School Admin must approve. District Admin / Platform Admin inherit approval right per §6.19. Audit log entry per approval.
- **Held-back students** (Q20): stay in current Grade but for the NEW academic session. Their previous-session data preserved; new-session data starts fresh. Effectively a re-enrollment.
- **Final grade (Grade 12 / FSc 2)** (Q22): student → GRADUATED state per Flow 4 v3 §3.9. 6-month school read-only window + auto-migration to independent tenant.
- **Atomic transaction:** entire promotion executes in one Celery task; partial failure → full rollback + retry up to 5 attempts.
- **Notifications:** School Admin gets notification when request lands (`account.promotion_pending_approval`). Coordinator gets notification on approval/rejection. Affected students + parents get notification on execution (`lectures.promoted` or `lectures.held_back`).

### 3.5 User lifecycle (#3) — unchanged from v2

```
   PENDING_INVITE → ACTIVE → SUSPENDED (reversible) → ACTIVE
                              ↓
                          DEACTIVATED (one-way; soft-delete)
```

**Locked rules:**
- Suspension: account login blocked; data intact; reversible by any admin at suspending-admin's level or higher per §6.19.
- Deactivation: one-way; user record soft-deleted; cannot be reactivated. If person needs to return, admin creates a new account.
- The last active admin in a scope cannot self-deactivate (`PRECONDITION_FAILED`).
- Suspending a teacher with active students: per Flow 3 v3 §3.5 — students retain access to existing content; School Admin gets notification to reassign Grade-Subject if needed.
- All status changes audit-logged per §14.10.

---

## 4. Permissions matrix

Per §6.19: every action available to a role is also available to all roles above in scope.

| Action | Coordinator (own scope) | School Admin (own school) | District Admin (own district) | Platform Admin |
|---|:---:|:---:|:---:|:---:|
| Create District Admin (#2) | — | — | — | ✅ |
| Create School Admin (#2) | — | — | ✅ (own district) | ✅ |
| Create Coordinator (#2) | — | ✅ (own school) | ✅ (any school in district) | ✅ |
| Create Teacher (#2) | — | ✅ (own school) | ✅ (any school in district) | ✅ |
| Create Student / Bulk import (#2) | ✅ (own scope) | ✅ (own school) | ✅ (any school in district) | ✅ |
| Suspend / Reactivate user (#3) | — | ✅ (own school) | ✅ (own district) | ✅ |
| Deactivate user (#3) | — | ✅ (own school) | ✅ (own district) | ✅ |
| Create subject (#4) | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Edit / archive subject (#4) | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Create Grade (#5) | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Add Section to Grade | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Create GradeSubjectOffering | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Assign Teacher to GradeSubjectOffering | ✅ (own scope; respects teacher capacity per Flow 3) | ✅ (override capacity, audit) | ✅ (override) | ✅ |
| Enroll students bulk into Grade-Section | ✅ (own scope) | ✅ (own school) | ✅ (any school) | ✅ |
| Unenroll student | ✅ (own scope) | ✅ (own school) | ✅ | ✅ |
| Initiate promotion request | ✅ (own scope) | n/a | n/a | n/a |
| Approve promotion request | — | ✅ (own school) | ✅ (own district) | ✅ |
| Override teacher capacity assignment | — | ✅ (audit) | ✅ (audit) | ✅ |

**Locked rule:** every endpoint enforces `require_role(MIN_ROLE)` + `require_scope(...)` per §6.7 with §6.19 inheritance. Cross-tenant operations (school user attempting to view another district's data) return 404 per §3.13.

---

## 5. Edge cases

### 5.1 User creation
- **Duplicate email at platform level:** rejected. Email globally unique.
- **Same person needs Coordinator + Teacher role:** create two accounts with different emails per launch.
- **Invite email bounces:** create succeeds (record exists in PENDING_INVITE); admin sees "delivery failed" badge in user list.
- **Invite link expires (7 days):** "expired — ask admin to resend"; admin can resend new token.
- **Admin tries to create role above own:** 403 `PERMISSION_DENIED`.
- **Admin self-deactivates being last active admin in scope:** `PRECONDITION_FAILED`.
- **Bulk import with email already in another school:** that row fails; other rows proceed; School Admin sees error report.
- **Independent user manually signs up (Path B):** standard Authentik flow; per Flow 1 §6.20.
- **School user attempts public signup at `/signup`:** signup form requires invitation token (not exposed via the public path); per Q21, only independent role accepts manual public signup at launch.

### 5.2 User lifecycle
- **Suspended user attempts login:** rejected with clear "account suspended; contact your administrator" message.
- **Suspended user has active sessions:** JWT validation checks status on every request; sessions invalidated.
- **Reactivation of deactivated user:** blocked (one-way per §3.5).
- **Suspending teacher with active GradeSubjectOfferings:** existing students retain content access; School Admin gets notification to reassign teachers.
- **Suspending the only School Admin with active users:** blocked; must have ≥ 1 active admin in scope.

### 5.3 Subjects (#4)
- **Two schools have same subject name** (e.g., "Physics"): allowed; school-scoped uniqueness.
- **Archiving subject with active GradeSubjectOfferings:** blocked with `PRECONDITION_FAILED` listing affected offerings.
- **Archiving subject with only historical (archived) GradeSubjectOfferings:** allowed.

### 5.4 Grade / Section / Subject offerings (#5)
- **Grade created without Sections:** allowed; internal default section used for enrollment.
- **Section added after students already enrolled:** future enrollments can target the new section; existing students stay in their original section.
- **Reassigning a Teacher mid-year for a GradeSubjectOffering:** previous teacher's content remains attributed; new teacher inherits the offering + Grade's student roster.
- **Student enrolled in two GradeSubjectOfferings for same subject in same session:** blocked with `PRECONDITION_FAILED`.
- **Teacher at capacity (5 Grade-Subject assignments) — Coordinator tries to assign 6th:** blocked with `PRECONDITION_FAILED` per Flow 3 v3 §3.5. School Admin can override (audit-logged).
- **Bulk import with email of already-active Teacher:** that row fails; teacher import is separate (individual invites per Flow 3).
- **Bulk import student with invalid Grade-Section combo:** that row fails; others proceed.
- **Same Grade across two academic sessions** (e.g., "Grade 9 2024-2025" AND "Grade 9 2025-2026"): both can coexist; distinguished by academic_session.

### 5.5 Promotion workflow
- **Coordinator initiates promotion when target Grade for next session doesn't exist:** auto-created during execution. Coordinator can preview the target structure before submitting.
- **Excluded student is already in DEACTIVATED state:** they're skipped silently; not in either Grade after promotion.
- **Approval pending for too long (> 30 days):** Coordinator gets reminder notification at 30 days; request expires at 60 days; Coordinator must re-initiate.
- **Promotion execution fails partway through (e.g., DB error):** atomic rollback; retry up to 5 attempts; if all fail, Platform Admin notified; students stay in original Grade.
- **Mid-execution student deletion request from a student in the promoting Grade:** deletion request takes precedence; that student excluded from promotion.
- **Held-back student tries to access next-session content:** access denied (still in old Grade); banner explains "you're enrolled for the new session in Grade X."
- **Coordinator initiates promotion for Grade where they're not assigned scope:** blocked per `require_scope(...)`.
- **Coordinator initiates promotion for Grade 12:** triggers graduation lifecycle per Flow 4 v3 §3.9. Students → GRADUATED state on approval.

### 5.6 Cross-scope / cross-tenant
- **District Admin attempts to view another district's data:** 404 per §3.13.
- **School Admin modifying another school's subjects:** 404.
- **Coordinator without assigned scope attempts to write:** 404 (scope must be set).
- **Independent user trying to access any school endpoint:** 404 (different tenant per §3.16).
- **School user trying to access an independent user's data:** 404.

---

## 6. Limits

### User creation
- Max users per school: not enforced at launch (subscription tiers deferred to Flow 13).
- Max invites per admin per day: 200 (anti-abuse).
- Invite token TTL: 7 days.
- Bulk import: 5,000 rows, 5 MB max, CSV/XLSX (`bulk_import` upload profile per §11.19).

### Subjects (#4)
- Max subjects per school: not capped (operational; typical 8-15).
- Subject name max length: 100 chars.

### Grade / Section / Subject offerings (#5)
- Max Grades per school per session: not capped (operational; typical 6-12).
- Max Sections per Grade: 26 (A-Z; operational reality).
- Max students per Section: 60 (Pakistani school typical).
- Max GradeSubjectOfferings per Grade: 10 (typical 5-8 subjects per grade).
- Teacher Grade-Subject assignments per teacher: 1-20 (default 5) per Flow 3 v3 §3.5.

### Promotion workflow
- Max pending promotion requests per school: 12 (one per Grade).
- Promotion task `soft_time_limit`: 10 minutes (for very large Grades 500+).
- Approval expiry: 60 days.
- Coordinator reminder: 30 days unattended.

### User lifecycle (#3)
- Last active admin in scope: hard floor 1 (cannot self-deactivate).
- Audit log retention: 7 years per §14.10.

---

## 7. Notifications

Per §9.21 namespace conventions.

### Namespace: `account`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Admin creates new user | New user | Email (invite) | `account.invite_sent` |
| Invite expires unused | Inviting admin | In-app | `account.invite_expired` |
| User accepts invite | Inviting admin | In-app | `account.invite_accepted` |
| Admin suspends user | Suspended user + suspending admin | Login banner + in-app | `account.suspended` |
| Admin reactivates | Reactivated user + admin | Email + in-app | `account.reactivated` |
| Admin deactivates | Deactivated user (final email) + audit | Email + audit | `account.deactivated` |
| Bulk import completed | Importing admin | In-app | `account.bulk_import_done` |
| Bulk import errors | Importing admin | In-app + email with error report | `account.bulk_import_partial` |
| Promotion request pending (NEW) | School Admin (approval queue) | In-app + push | `account.promotion_pending_approval` |
| Promotion request approved (NEW) | Coordinator + Affected students + parents | In-app + push | `account.promotion_approved` |
| Promotion request rejected (NEW) | Coordinator | In-app | `account.promotion_rejected` |
| Promotion expires unattended | Coordinator | In-app | `account.promotion_expired` |
| Promotion execution failure | Platform Admin + Coordinator | In-app + email | `account.promotion_execution_failed` |

### Namespace: `connections` (per Flow 3 + Flow 4 sub-namespaces)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Coordinator assigns Teacher to GradeSubjectOffering | Teacher | In-app + push | `connections.grade_subject_assigned` (per Flow 3 v3) |
| Coordinator unassigns | Teacher | In-app | `connections.grade_subject_unassigned` |
| School Admin overrides teacher capacity | Teacher | In-app + push | `connections.capacity_admin_override` (per Flow 3 v3) |

### Namespace: `lectures`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Coordinator enrolls student into Grade-Section | Student + parents | In-app + push | `lectures.enrolled` (per Flow 4 v3) |
| Coordinator unenrolls | Student + parents | In-app + push | `lectures.unenrolled` |
| Promotion approved | Student + parents | In-app + push | `lectures.promoted` |
| Student held back (excluded from promotion) | Student + parents | In-app + push | `lectures.held_back` |
| Graduation (Grade 12 promotion) | Student + parents | In-app + push + email | `lectures.graduated_read_only` (per Flow 4 v3 §7) |

**Notifications cannot be turned off** per Flow 1 Q13.

---

## 8. Open questions

1. **Coordinator scope granularity.** Coordinator scope = "Grades 9 and 10" (Q-Flow-2-Q8 confirmed strict one-school). **Sub-question:** can their scope span non-contiguous grades (e.g., Grades 6 + 9)? Recommendation: yes — scope is a SET of grades, not a range. School Admin assigns when creating Coordinator.

2. **Bulk import file format flexibility.** CSV/XLSX at launch. **Sub-question:** what columns required? Recommendation: name + email + grade + section (optional) + language (optional). Phase 2 may add custom field mapping.

3. **Promotion approval delegation.** School Admin owns approval at launch. **Question:** can School Admin delegate to a deputy? Recommendation: no — formal approval gate. District Admin inherits per §6.19 if needed.

4. **Section as identifier vs label.** "Section A" is currently a label string. **Question:** should sections have richer identity (e.g., capacity, primary teacher, schedule)? Recommendation: name + capacity only at launch. Phase 2 may add schedule.

5. **Mid-session enrollment changes.** Coordinator unenrolls a student mid-academic-year. **Question:** what happens to their data? Recommendation: per Flow 4 v3 — historical data retained; access to past content read-only; new content blocked.

6. **Class roll-over before promotion approval.** **Question:** if Coordinator creates "Grade 10 2026-2027" before promotion approves, what links them? Recommendation: `promoted_from_grade_id` field set on execution, not creation. Coordinator can pre-create the target Grade.

7. **Subscription tier visibility for Coordinators.** Flow 13 schema only. **Sub-question:** does Coordinator see school's current subscription status? Recommendation: read-only per §6.19; doesn't affect their actions at launch.

8. **Bulk import "preview before commit".** **Question:** should the bulk import show a dry-run before committing? Recommendation: yes — server-side validation runs first; admin reviews row-by-row results; commits with confirmation. Matches typical SaaS UX.

9. **Audit log queryable surface for School Admin.** "Last 50 actions" UI at launch per Flow 2 v1 §9. **Question:** is this enough for compliance? Recommendation: yes for pilot; full queryable UI Phase 2.

10. **Cross-district transfers.** A student moves from School A in District 1 to School B in District 2. **Question:** what's the workflow? Recommendation: deactivate + recreate at launch. Phase 2 considers cross-school transfer.

---

## 9. Out of scope (for now)

- **Manual public signup for school users.** Path B exists for independents only at launch. School users via Path A only. (TODO: `phase-2-school-user-self-signup`)
- **Bulk-promote-all** grades. Per-grade only at launch. (TODO: `phase-2-bulk-promote-all-grades`)
- **CSV import for exclusion list.** Manual checkboxes only at launch. (TODO: `phase-2-csv-exclusion-import`)
- **Per-Section teacher assignment.** Teacher assigned at GradeSubjectOffering level. (TODO: `phase-2-per-section-teacher-assignment`)
- **Bulk teacher import.** Individual invites only at launch. (TODO: `phase-2-bulk-teacher-import`)
- **Self-service school registration.** Manual Platform Admin onboarding at launch. (TODO: `phase-2-self-service-school-signup`)
- **Co-teaching** (multiple teachers per offering). One primary at launch. (TODO: `phase-2-co-teaching`)
- **Automatic class roll-over.** Manual + approval-driven at launch. (TODO: `phase-2-automatic-rollover`)
- **Coordinator write permissions expansion.** Current scope per §4 matrix; Phase 2 may expand. (TODO: `phase-2-coordinator-write-expansion`)
- **Sub-classes beyond optional A/B/C** Sections. Simple optional Section model at launch. (TODO: `phase-2-class-sections-expansion`)
- **Cross-subject homeroom Grades.** Single subject per offering at launch. (TODO: `phase-2-homeroom-grade`)
- **District Admin policy controls.** Schema exists; UI/enforcement Phase 2. (TODO: `phase-2-district-policy`)
- **Subscription tier user-count caps.** Schema only per Flow 13. (TODO: per Flow 13)
- **Cross-district student transfer.** Deactivate + recreate at launch. (TODO: `phase-2-cross-district-transfer`)
- **Promotion approval delegation.** School Admin only at launch. (TODO: `phase-2-promotion-delegation`)
- **Section richer attributes** (capacity, schedule). Name + optional only. (TODO: `phase-2-section-schedule`)
- **Promotion preview before submission.** Direct submit at launch. (TODO: `phase-2-promotion-preview`)
- **Stale bulk-imported student cleanup.** Manual School Admin review only. (TODO: `phase-2-stale-account-cleanup`)
- **Audit log queryable UI.** Last-50 only at launch. (TODO: `phase-2-audit-log-ui`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy
- **§3.16** — Independent users tenant model
- **§3.17** — Subscription cross-cutting attribute (Flow 13)
- **§3.18** — Grade/Section/Subject model (this flow defines the canonical entities)
- **§3.19** — Exam Framework engine (consumed by Flow 4 / Flow 5)
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations (this flow introduces grades, sections, grade_subject_offerings, grade_promotion_requests)
- **§4.21** — Dual Alembic heads
- **§5.1-5.7, §5.9** — API design + Idempotency-Key for user-creation POSTs (prevents double-invite)
- **§5.10** — If-Match (optimistic concurrency for subject/grade edits)
- **§5.11** — Bulk operations envelope (student import)
- **§6.2** — Role matrix
- **§6.7** — Dependency primitives
- **§6.19** — Permission inheritance (the defining rule for this flow's permissions matrix)
- **§6.20** — Independent user signup path (Path B)
- **§6.21** — Promotion approval workflow (NEW; defines the state machine + auth gates)
- **§9** — NATS events: `user.created`, `user.activated`, `user.suspended`, `user.reactivated`, `user.deactivated`, `grade.created`, `section.created`, `offering.created`, `teacher.assigned`, `student.enrolled`, `student.unenrolled`, `promotion.requested`, `promotion.approved`, `promotion.executed`, `promotion.failed`
- **§9.21** — Notification namespaces (`account`, `connections`, `lectures`)
- **§10.3-10.5** — Celery `@tenant_task` for promotion execution (atomic transaction)
- **§10.6** — Beat schedule: `promotion.expire_unattended` (daily check), `stale_bulk_imports.review_sweep` (Phase 2)
- **§11.2-11.10** — File upload pipeline
- **§11.19** — Upload profile `bulk_import` (CSV/XLSX, 5 MB, 5000 rows)
- **§14.10** — Audit log: all user state changes, promotion events, capacity overrides

### Data model sketch

```
# In school schema:
user_invites
  id (uuidv7), email, invited_by_user_id, invited_role, scope_ids_jsonb,
  token (random 32 bytes), expires_at, accepted_at, status (enum),
  resent_count, rejected_count

# Existing user table from Flow 1 covers the user record with state enum

subjects
  id (uuidv7), school_id, name, language (enum: en/ur/sd/ps),
  is_archived, created_at, updated_at, deleted_at
  UNIQUE (school_id, name)

grades
  id (uuidv7), school_id, name (e.g., "Grade 9"), 
  academic_session (string, e.g., "2025-2026"),
  promoted_from_grade_id (nullable FK self-ref),
  status (enum: active/archived), created_at, updated_at, deleted_at
  UNIQUE (school_id, name, academic_session)

sections
  id (uuidv7), grade_id (FK), name (e.g., "A", "B"),
  capacity (default 60), created_at, updated_at, deleted_at
  UNIQUE (grade_id, name)
  -- A Grade may have 0 Sections; internal "default" section used for enrollment.

grade_subject_offerings
  id (uuidv7), grade_id (FK), subject_id (FK), assigned_teacher_id (nullable FK to users),
  created_by_user_id, assigned_at (when teacher assigned),
  status (enum: active/archived), created_at, updated_at, deleted_at
  UNIQUE (grade_id, subject_id)

class_enrollments
  id (uuidv7), section_id (FK), grade_id (FK, redundant for fast lookup),
  student_user_id (FK), academic_session,
  enrolled_at, unenrolled_at, status (enum)
  UNIQUE (section_id, student_user_id) WHERE unenrolled_at IS NULL

grade_promotion_requests
  id (uuidv7), school_id, initiating_grade_id (FK), target_grade_id (FK, nullable until execution),
  initiated_by_coordinator_id (FK), exclusion_list_jsonb (array of student_user_ids),
  status (enum: pending_approval/approved/rejected/executing/executed/expired/failed),
  requested_at, approved_at, approved_by_user_id (FK), executed_at,
  rejection_reason (nullable), failure_reason (nullable),
  retry_count (default 0)

bulk_imports
  id (uuidv7), school_id, imported_by_user_id, file_key (MinIO),
  total_rows, success_rows, failed_rows, error_report_jsonb,
  status (enum), created_at, completed_at

# Audit table reuses ARCHITECTURE.md §14.10 schema
```

---

## 11. Acceptance criteria

### User creation (#2)
- ✅ Platform Admin creates District Admin via `POST /api/v1/admin/users` with role=district_admin
- ✅ District Admin creates School Admin (own district only); cross-district → 404
- ✅ School Admin creates Coordinator + Teacher (own school)
- ✅ Coordinator creates Students via bulk-import (CSV/XLSX) or individual; respects scope
- ✅ Inheritance per §6.19: District Admin can create Coordinator (any school in district); Platform Admin can create at any level any tenant
- ✅ Invite email + token (7-day TTL) sent on creation
- ✅ Re-invite of active user prompts confirmation + sends password reset
- ✅ Bulk import: 5,000 rows / 5 MB; success/failure report per row
- ✅ Cross-tenant denial: District A trying to read District B → 404 per §3.13
- ✅ Independent users sign up via Path B at `/independent/signup`; school users do not

### User lifecycle (#3)
- ✅ Suspending: existing JWTs invalidated on next request
- ✅ Suspended user login: clear "account suspended" message
- ✅ Reactivation enables login
- ✅ Deactivation soft-deletes record; reactivation attempt → 404
- ✅ Last active admin in scope cannot self-deactivate
- ✅ Self-deactivation otherwise blocked with `PRECONDITION_FAILED`
- ✅ All status changes audit-logged per §14.10

### Subjects (#4)
- ✅ Coordinator creates subject within scope
- ✅ School Admin inherits subject creation per §6.19
- ✅ Subject (school_id, name) unique within school
- ✅ Same subject name allowed across schools
- ✅ Archiving blocked if active GradeSubjectOfferings exist

### Grade / Section / Subject offerings (#5)
- ✅ Coordinator creates Grade with (school_id, name, academic_session) unique tuple
- ✅ Grade may have 0 or N Sections; internal default used when 0
- ✅ Section is child of Grade; (grade_id, name) unique within Grade
- ✅ GradeSubjectOffering created: (grade_id, subject_id) unique
- ✅ Teacher assigned to GradeSubjectOffering (not per-Section per Q13)
- ✅ Teacher capacity check at assignment (default 5; per Flow 3 v3)
- ✅ Student enrolled into Section (or default); blocked duplicate (section_id, student_user_id)
- ✅ Bulk import: target Grade-Section; failed rows reported
- ✅ District Admin / Platform Admin inherit Grade/Section/Offering operations per §6.19

### Promotion workflow
- ✅ Coordinator initiates per-grade promotion request with exclusion list (manual checkboxes)
- ✅ School Admin sees in approval queue + notification (`account.promotion_pending_approval`)
- ✅ District Admin / Platform Admin inherit approval right per §6.19
- ✅ Approval triggers atomic Celery transaction; 5 retries on failure
- ✅ Held-back students: stay in original Grade for new session; previous-year data preserved
- ✅ Grade 12 promotion → student → GRADUATED state (Flow 4 v3 §3.9)
- ✅ Approval expires at 60 days unattended; reminder at 30 days
- ✅ Audit log per approval and execution per §14.10
- ✅ NATS events `promotion.requested`, `promotion.approved`, `promotion.executed`, `promotion.failed`

### Permissions & scoping
- ✅ Coordinator cannot create users above their level (returns 403)
- ✅ School Admin cannot modify other schools' subjects/grades (returns 404)
- ✅ Per §6.19: District Admin inherits all School Admin actions; Platform Admin inherits all
- ✅ All endpoints have `require_role + require_scope` dependencies; no body-level checks

### Notifications
- ✅ All 12+ notification triggers fire with correct namespace and language
- ✅ Bulk import completion notification with pass/fail counts
- ✅ Promotion-related notifications in `account` + `lectures` namespaces

### Audit & cross-tenant
- ✅ Every action audit-logged per §14.10
- ✅ Cross-tenant attempts return 404; school users cannot access independent tenant; vice versa
- ✅ Platform Admin audit-logged when crossing tenants

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v2 → v3:**
- **Grade / Section / Subject restructure** — entire §3.3 redesigned around Grade (primary) + Section (optional child) + GradeSubjectOffering. Replaces v2's "Class" model. Per v3 feedback.
- **Promotion workflow** (NEW §3.4): Coordinator-initiated, School Admin-approved, exclusion list, atomic execution, retry-on-failure. Per Q6, Q18-Q23.
- **All 6 roles created from start** per Q8 (District Admin not skipped at launch).
- **Subject management owned by Coordinator** per Q15 simpler model (was split in earlier draft).
- **Teacher capacity redefined** as Grade-Subject assignment count per Flow 3 v3 §3.5 (default 5). Replaces v2's student-count cap.
- **Permission inheritance §6.19** explicitly applied throughout permissions matrix. Higher roles inherit all lower-role permissions within scope.
- **Manual public signup (Path B)** for independent users only per Q21. School users via Path A admin-invitation only.
- **Promotion approval** for Grade 12 promotion triggers graduation lifecycle per Flow 4 v3 §3.9.
- **Cross-grade subject linking** from v1/v2 REMOVED — replaced by GradeSubjectOffering model + cross-grade lecture linking per Flow 5 #21 (unidirectional).
- **Notification namespaces** applied per §9.21 (account, connections, lectures).
- **Subscription tier visibility** added (Flow 13 cross-ref); read-only at launch per §6.19.
- **Bulk student import** moved from School Admin (v2) to Coordinator (v3) per scope alignment.
- Open Questions Q1-Q12 from v1/v2 resolved (incorporated into spec or moved to TODO).

# M-03 — Subjects + Grade / Section / Subject Offerings

**Status:** todo
**Estimated duration:** 2 weeks
**Tickets:** T-041 through T-052
**Spec source:** `flow-2-admin-coordinator-setup.md` v3 (§3.2 Subject catalog, §3.3 Grade/Section/Offering)

## Goal

Build the academic structure model that replaces the old "Class" concept. A Coordinator (created in M-02) defines their school's **Subjects**, creates **Grades** for an academic session, optionally adds **Sections**, **offers** Subjects to Grades, and **assigns Teachers** to those offerings — subject to teacher capacity limits. The cross-grade unidirectional access rule is enforced at the API. No student enrollment yet (that's M-06).

**Demo at milestone end:**
- School Admin creates a Coordinator with scope (Grades 9 + 10) — *(Coordinator role already exists from M-02 T-034; this confirms scope assignment)*
- Coordinator sets the active academic session ("2025-2026")
- Coordinator creates Subject "Physics" in the catalog
- Coordinator creates "Grade 9" and "Grade 10" for the session
- Coordinator adds Sections "A" and "B" under Grade 9
- Coordinator offers Physics to Grade 9 (creates a GradeSubjectOffering)
- Coordinator assigns a Teacher to the Grade 9 Physics offering — teacher capacity decrements
- Coordinator attempts a 6th assignment to a teacher at cap 5 → blocked with `PRECONDITION_FAILED`; School Admin overrides → audit-logged
- A Grade 9 offering attempting to link Grade 10 material is blocked (cross-grade rule); Grade 10 → Grade 9 is allowed
- All structure actions are audit-logged and scoped to the Coordinator's assigned Grades

---

## T-041 — Subject catalog (model + CRUD + Coordinator UI)

**Layer:** 2
**Milestone:** M-03
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.2 (Subject catalog lifecycle #4)

### ARCH source
- `ARCHITECTURE.md` §3.18 (Grade/Section/Subject model — Subject row)
- `ARCHITECTURE.md` §4.2-§4.8 (DB mixins), §4.12 (migrations)
- `ARCHITECTURE.md` §5.1-§5.7 (API design)
- `ARCHITECTURE.md` §6.19 (permission inheritance — Coordinator + higher)

### Depends on
- T-034 (Coordinator role + scope assignment)
- T-028 (School data model)

### What this ticket builds

**Backend:** Migration creates `subjects` table in the school schema `{id, school_id, name, language, status (active|archived), created_at, ...}` with unique `(school_id, name)`. CRUD endpoints (create / list / edit / archive) gated to Coordinator-and-above per §6.19. Archive blocked if active GradeSubjectOfferings exist (deferred check stub until T-044; for now archive always allowed with a TODO marker).

**Frontend:** Coordinator "Subjects" page — table of subjects, "Add Subject" modal (name + language), edit + archive actions. Empty state when none exist.

### Acceptance (demo script)

1. [ ] Coordinator opens Subjects page, sees empty state
2. [ ] Coordinator creates "Physics" (language English) → appears in table
3. [ ] Duplicate "Physics" in same school → rejected with clear error (unique constraint)
4. [ ] Coordinator edits subject language → persists
5. [ ] Coordinator archives a subject → status=archived, hidden from default list
6. [ ] Unit test: a different school can independently create its own "Physics" (school-scoped uniqueness)

### Out of scope
- Archive-blocked-by-active-offering enforcement (real check added in T-044 once offerings exist)
- Offering a subject to a grade (T-044)

### Notes / known gotchas
- A Subject is independent of any Grade — it's just `{school_id, name, language}`. It only becomes "offered" via a GradeSubjectOffering.
- Coordinator owns subject creation per Flow 2 v3 §3.2 Q15; School Admin inherits per §6.19.

---

## T-042 — Academic Session concept + school active-session setting

**Layer:** 2
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (Grade entity carries `academic_session`)

### ARCH source
- `ARCHITECTURE.md` §3.18 (Grade definition — session-scoped)
- `ARCHITECTURE.md` §4.2-§4.8 (DB mixins)

### Depends on
- T-028 (School data model)
- T-034 (Coordinator role)

### What this ticket builds

**Backend:** A lightweight `academic_session` representation. Decision: store sessions as a school-level setting (`school.active_academic_session` string, e.g., "2025-2026") plus a small `academic_sessions` lookup table `{school_id, label, is_active, start_date, end_date}` so Grades can pin to a session value. One active session per school at a time. Endpoint to set/list sessions (Coordinator-and-above).

**Frontend:** A session selector in the Coordinator structure area header showing the active session, with a "Manage sessions" affordance to add a new session and mark it active.

### Acceptance (demo script)

1. [ ] Coordinator sees current active session in the structure header
2. [ ] Coordinator creates session "2025-2026" and marks it active
3. [ ] Only one session is `is_active=true` per school at any time (marking a new one active deactivates the prior)
4. [ ] Grades created later pin to the active session (verified in T-043)
5. [ ] Unit test: session label unique per school

### Out of scope
- Promotion / rolling a session forward (M-22)
- Cross-session reporting

### Notes / known gotchas
- Keep this minimal — it's a string + lookup, not a calendar system. Promotion (M-22) is what actually rolls Grades between sessions.

---

## T-043 — Grade entity (model + CRUD + Coordinator UI)

**Layer:** 2
**Milestone:** M-03
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (Grade lifecycle #5 — Grade entity)

### ARCH source
- `ARCHITECTURE.md` §3.18 (Grade definition + ownership)
- `ARCHITECTURE.md` §4 (DB patterns), §5 (API)
- `ARCHITECTURE.md` §6.19 (Coordinator scope)

### Depends on
- T-042 (active academic session)
- T-034 (Coordinator role + scope)

### What this ticket builds

**Backend:** Migration creates `grades` table `{id, school_id, name, academic_session, promoted_from_grade_id (nullable), status (active|archived), created_at, ...}` with unique `(school_id, name, academic_session)`. Grade is pinned to the active session on creation. CRUD endpoints scoped to the Coordinator's assigned grade scope (Coordinator can only create Grades within their scope; School Admin any).

**Frontend:** Coordinator "Grades" page — list grades for the active session, "Add Grade" (name picker, e.g., Grade 9), archive. Shows which session each grade belongs to.

### Acceptance (demo script)

1. [ ] Coordinator creates "Grade 9" → pinned to active session "2025-2026"
2. [ ] Duplicate "Grade 9" in same school + session → rejected (unique constraint)
3. [ ] Same "Grade 9" name allowed in a different session (after T-042 session switch)
4. [ ] Coordinator outside scope (e.g., assigned only Grades 11+) is blocked from creating Grade 9 → `FORBIDDEN`
5. [ ] Archive a Grade → status=archived, retained in history
6. [ ] `promoted_from_grade_id` is nullable and unset for a freshly created Grade

### Out of scope
- Sections (T-044)
- Offerings (T-045)
- Promotion linkage population of `promoted_from_grade_id` (M-22)

### Notes / known gotchas
- Grade scope enforcement is per the Coordinator's `scope` from T-034. Cross-scope creation must be blocked at the API, not just hidden in UI.

---

## T-044 — Section entity (model + CRUD + Coordinator UI, optional + default-internal)

**Layer:** 2
**Milestone:** M-03
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (Section lifecycle #5 — optional sections, default-internal per Q11)

### ARCH source
- `ARCHITECTURE.md` §3.18 (Section definition — optional)
- `ARCHITECTURE.md` §4 (DB patterns), §5 (API)

### Depends on
- T-043 (Grade entity)

### What this ticket builds

**Backend:** Migration creates `sections` table `{id, grade_id, name, is_default_internal (bool), status, created_at}`. When a Grade is created with no explicit Sections, a `is_default_internal=true` Section is auto-created so future student enrollment (M-06) always targets a Section. Explicit Sections (A, B, C) created by Coordinator coexist; if explicit Sections are added, the default-internal one remains usable but hidden from UI. CRUD endpoints scoped to Coordinator.

**Frontend:** On a Grade's detail page, a "Sections" panel — add Section (A/B/C), list, archive. Default-internal section is NOT shown as a user-facing section.

### Acceptance (demo script)

1. [ ] Creating Grade 9 auto-creates a hidden default-internal section
2. [ ] Coordinator adds Section "A" and "B" under Grade 9 → both appear; default-internal hidden
3. [ ] Duplicate Section "A" under same Grade → rejected
4. [ ] Archiving the Grade cascades Sections to archived
5. [ ] Unit test: a Grade with 0 explicit sections still has exactly one default-internal section

### Out of scope
- Student enrollment into Sections (M-06)
- Per-Section teacher assignment (Phase 2 per §3.18)

### Notes / known gotchas
- Teacher assignment is at the offering level, NOT per-Section (§3.18). All sections of Grade 9 share the same Physics teacher.
- The default-internal section exists so M-06 enrollment has a uniform target whether or not the school uses sections.

---

## T-045 — GradeSubjectOffering (model + CRUD + "offer subject to grade" UI)

**Layer:** 2
**Milestone:** M-03
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (GradeSubjectOffering lifecycle #5)

### ARCH source
- `ARCHITECTURE.md` §3.18 (GradeSubjectOffering definition + unique constraint)
- `ARCHITECTURE.md` §4 (DB), §5 (API), §6.19 (scope)

### Depends on
- T-041 (Subjects)
- T-043 (Grades)

### What this ticket builds

**Backend:** Migration creates `grade_subject_offerings` table `{id, school_id, grade_id, subject_id, assigned_teacher_id (nullable), academic_session, status, created_at}` with unique `(grade_id, subject_id)` per session. Create/list/archive endpoints scoped to Coordinator. `assigned_teacher_id` stays NULL until T-046. Now wire the real "archive Subject blocked if active offerings exist" check stubbed in T-041.

**Frontend:** On a Grade's detail page, an "Offerings" panel — "Offer a Subject" (pick from catalog), list offerings with their (currently unassigned) teacher slot. Archive an offering.

### Acceptance (demo script)

1. [ ] Coordinator offers "Physics" to Grade 9 → offering created, teacher slot empty
2. [ ] Offering the same Subject to the same Grade+session again → rejected (unique constraint)
3. [ ] Same "Physics" can be offered to Grade 10 separately → allowed (distinct offering)
4. [ ] Attempting to archive "Physics" subject while an active offering exists → blocked with clear error (the T-041 stub is now real)
5. [ ] Archiving the offering first, then the subject → succeeds
6. [ ] Coordinator outside Grade scope cannot create an offering for that Grade → `FORBIDDEN`

### Out of scope
- Teacher assignment + capacity (T-046)
- Lecture content under the offering (M-04+)

### Notes / known gotchas
- One Subject can be offered to multiple Grades, each a separate offering, each with potentially a different teacher.

---

## T-046 — Teacher assignment to offering + capacity check + override

**Layer:** 2
**Milestone:** M-03
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (teacher assignment at offering level)
- `flow-3-teacher-onboarding.md` §3.5 (teacher capacity — default cap 5, range [1,20], School Admin override)

### ARCH source
- `ARCHITECTURE.md` §3.18 (teacher capacity rule + PRECONDITION_FAILED + override audit)
- `ARCHITECTURE.md` §5.10 (If-Match / optimistic concurrency on assignment)
- `ARCHITECTURE.md` §6.19 (override authority), §14.10 (audit log)

### Depends on
- T-045 (GradeSubjectOffering)
- T-035 (Teacher role invitation)

### What this ticket builds

**Backend:** Endpoint to assign a Teacher to an offering (sets `assigned_teacher_id`). Capacity rule: a teacher's number of Grade-Subject assignments must not exceed their cap (default 5, range [1,20]). Coordinator exceeding cap → `PRECONDITION_FAILED` with a message naming the teacher + current count. School Admin (and above) can override; override writes an audit-log entry per §14.10. Unassign endpoint frees capacity.

**Frontend:** On an offering, "Assign Teacher" picker showing eligible teachers + their current assignment count vs cap. Over-cap teachers shown disabled with "at capacity (5/5)". School Admin sees an "override" affordance with a confirmation that states the action is logged.

### Acceptance (demo script)

1. [ ] Coordinator assigns Teacher T to Grade 9 Physics → `assigned_teacher_id` set; T's count = 1
2. [ ] Assigning T to 5 offerings reaches cap; 6th by Coordinator → `PRECONDITION_FAILED` naming T (5/5)
3. [ ] School Admin overrides the 6th assignment → succeeds; audit log entry written
4. [ ] Unassigning an offering decrements T's count → frees capacity
5. [ ] Capacity counts Grade-Subject assignments, NOT students (verify with a teacher on 2 offerings across different grades = count 2)
6. [ ] Concurrent double-assign (two requests) handled via If-Match; one wins, other gets `412`

### Out of scope
- Teacher onboarding details / library (M-04)
- Reassignment-on-suspension flow (Flow 3 §3.5 — surfaced in M-04)

### Notes / known gotchas
- Capacity = count of Grade-Subject assignments per §3.18, explicitly NOT student count.
- Override authority is School-Admin-and-above only; Coordinator can never self-override.

---

## T-047 — Cross-grade unidirectional access rule enforcement

**Layer:** 2
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.3 (cross-grade subject linking replaced by unidirectional rule)

### ARCH source
- `ARCHITECTURE.md` §3.18 (cross-grade unidirectional rule: Grade N accesses ≤ N)
- `ARCHITECTURE.md` §7.21 (cross-grade unidirectional retrieval weighting)

### Depends on
- T-045 (offerings exist to reference)

### What this ticket builds

**Backend:** A reusable guard `assert_cross_grade_access(source_grade, target_grade)` enforcing that a Grade may access/link material only from grades ≤ itself (lower or equal year-level). Higher-grade access is blocked at the API with `FORBIDDEN`. Wire this guard at the offering/material-linking boundary so later content flows (M-04+, Flow 5 #21) inherit it. Provide unit-test coverage of the rule matrix.

**Frontend:** No new page — when a future "link material from another grade" UI appears (M-04+), this guard backs it. For this ticket, expose the rule via API only + tests.

### Acceptance (demo script)

1. [ ] `assert_cross_grade_access(Grade 10, Grade 9)` → allowed
2. [ ] `assert_cross_grade_access(Grade 9, Grade 9)` → allowed (equal)
3. [ ] `assert_cross_grade_access(Grade 9, Grade 10)` → `FORBIDDEN`
4. [ ] Guard is importable/reusable for M-04+ content linking
5. [ ] Unit tests cover the full ≤ / > matrix across several grade levels

### Out of scope
- Actual lecture linking UI (Flow 5 #21, later milestone)
- RAG retrieval weighting implementation (§7.21 — content milestones)

### Notes / known gotchas
- Grade ordering must be derived from a normalized year-level, not the string name. Decide a `grade.level_ordinal` derivation (e.g., parse "Grade 9" → 9) and store it so comparison is reliable across naming variants. Add `level_ordinal` to the grades table if not already present (coordinate with T-043 — may require a follow-up migration).

---

## T-048 — Coordinator scope + permission inheritance enforcement (structure-wide)

**Layer:** 2
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3 (Coordinator scope; permission inheritance)

### ARCH source
- `ARCHITECTURE.md` §6.19 (permission inheritance — defining rule)
- `ARCHITECTURE.md` §6.7 (dependency primitives)

### Depends on
- T-041, T-043, T-044, T-045, T-046 (all structure CRUD)

### What this ticket builds

**Backend:** A consistent permission layer across ALL M-03 structure endpoints: a Coordinator may act only within their assigned Grade scope; School Admin inherits all Coordinator rights for the whole school; District + Platform Admin inherit downward per §6.19. Centralize this so each endpoint doesn't re-implement scope logic. Add an integration test sweep proving scope is enforced on every structure endpoint (not just the UI).

**Frontend:** UI hides out-of-scope grades/actions for Coordinators; School Admin sees all. (Reuses existing role-aware nav from M-01/M-02.)

### Acceptance (demo script)

1. [ ] Coordinator scoped to Grades 9+10 cannot create/read/edit Grade 11 structure → `FORBIDDEN` on every endpoint
2. [ ] School Admin can act on any grade in the school (inheritance)
3. [ ] District Admin can act within their district's schools; Platform Admin anywhere
4. [ ] Integration test sweep: every M-03 endpoint enforces scope server-side
5. [ ] UI correctly hides out-of-scope items for Coordinator

### Out of scope
- Cross-school coordinator (not a concept; coordinators are single-school)

### Notes / known gotchas
- Enforcement must be server-side on every endpoint. UI hiding alone is not security (§6 is security-critical).

---

## T-049 — Notifications for M-03 structure events

**Layer:** 2
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3 (structure events)

### ARCH source
- `ARCHITECTURE.md` §9.21 (notification namespaces)
- `ARCHITECTURE.md` §9 (NATS events)

### Depends on
- T-046 (teacher assignment — the key notifiable event)
- T-038 (notifications infra from M-02)

### What this ticket builds

**Backend:** Emit + deliver notifications for the meaningful structure events: a Teacher is notified when assigned to a Grade-Subject offering (`account.teacher_assigned_offering`); a School Admin is notified when a Coordinator triggers a capacity override request or when an override occurs (`account.capacity_override`). NATS events published for each structure mutation for downstream consumers. Templates in all 4 languages.

**Frontend:** Notifications appear in the existing M-02 notification inbox; no new page.

### Acceptance (demo script)

1. [ ] Assigning Teacher T to an offering → T receives `account.teacher_assigned_offering` in their inbox
2. [ ] School Admin override of a capacity limit → School Admin sees `account.capacity_override`
3. [ ] NATS events published for grade/section/offering/assignment mutations
4. [ ] All templates present in en/ur/sd/ps (no `__TODO__` placeholders)

### Out of scope
- Student-facing notifications (no students in M-03)
- Digest/batching of structure notifications (Phase 2)

### Notes / known gotchas
- Reuse the M-02 `account` namespace; don't invent a new namespace for structure events.

---

## T-050 — Audit logging for structure changes + capacity overrides

**Layer:** 2 / 6 (cross-cutting)
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3 (audit-logged actions)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log)

### Depends on
- T-046 (override is the highest-value audit event)
- T-036 (audit log infra from M-02, scope-restricted)

### What this ticket builds

**Backend:** Write audit-log entries for: Subject create/archive, Grade create/archive, Section create/archive, Offering create/archive, Teacher assign/unassign, and — flagged as elevated — School Admin capacity overrides. Each entry captures actor, action, target, scope, timestamp. Reuse the M-02 audit infra; just register the new action types.

**Frontend:** The existing M-02 scope-restricted "Audit Log" page now shows M-03 structure actions. No new page.

### Acceptance (demo script)

1. [ ] Each structure mutation writes an audit entry (actor, action, target, timestamp)
2. [ ] Capacity override entries are flagged/elevated and clearly distinguishable
3. [ ] Audit log page (M-02) displays M-03 actions, scope-restricted per role
4. [ ] Coordinator sees only their scope's audit entries; School Admin sees the school's

### Out of scope
- Audit export (Phase 2 per TODO)
- Tamper-evidence / signing (Phase 3 per TODO)

### Notes / known gotchas
- Don't build a new audit system — register new action types against the M-02 infra.

---

## T-051 — E2E smoke test (automated demo flow)

**Layer:** 6 (cross-cutting)
**Milestone:** M-03
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.2-§3.3 (full structure flow)

### ARCH source
- `ARCHITECTURE.md` §0 (E2E test convention from M-00/M-01/M-02)

### Depends on
- T-041 through T-050 (everything in the milestone)

### What this ticket builds

**Backend + test harness:** An automated E2E test that runs the entire milestone demo: create session → subject → grades → sections → offering → assign teacher → hit capacity → override → verify cross-grade rule → confirm notifications + audit entries. Runs in CI against the compose stack. This is the executable form of the "Demo at milestone end" script.

### Acceptance (demo script)

1. [ ] E2E test runs green in CI end-to-end (session → assignment → override)
2. [ ] Capacity `PRECONDITION_FAILED` path asserted
3. [ ] Cross-grade `FORBIDDEN` path asserted (Grade 9 → Grade 10 blocked)
4. [ ] Audit + notification side-effects asserted
5. [ ] Test is idempotent / re-runnable (cleans up or uses fresh tenants)

### Out of scope
- Load testing (separate concern)
- Frontend E2E (Playwright) — Phase 2 unless already established

### Notes / known gotchas
- Follow the same E2E pattern established by T-026 (M-01) and T-040 (M-02) so CI wiring is consistent.

---

## T-052 — Milestone M-03 PR + demo

**Layer:** 6 (cross-cutting)
**Milestone:** M-03
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` v3 (whole flow)

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking for PR), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-041 through T-051

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-03 branch PR, fill the PR description (spec source read, ARCH sections read per §1.4, acceptance summary), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-03` → `staging` with full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes (section-tracking, spec adherence)
3. [ ] CI green (including T-051 E2E)
4. [ ] Live demo of the milestone-end script runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-03 ticket set

### Notes / known gotchas
- One PR per milestone (not per ticket) per WORKFLOW.md. Tickets are commits on the milestone branch.

---

## Milestone notes

- **No student enrollment.** Sections are created here but students enroll in M-06 (Student Onboarding). The default-internal section (T-044) exists precisely so M-06 has a uniform enrollment target.
- **No promotion.** Grades carry `academic_session` and `promoted_from_grade_id` (nullable) but promotion is M-22.
- **Cross-grade rule is enforced but not yet exercised by content** — T-047 ships the reusable guard; M-04+ content/lecture flows consume it.
- **Teacher capacity** is the one rule most likely to confuse: it counts Grade-Subject *assignments*, not students. Default cap 5, range [1,20], School-Admin-and-above override (audit-logged).
- **Source flow:** Flow 2 v3 §3.2 + §3.3. No blockers — the flow spec is finalized.

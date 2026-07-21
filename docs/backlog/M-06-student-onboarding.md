# M-06 — Student Onboarding (school) + Parent Linking

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** in-progress
**Estimated duration:** 2-3 weeks
**Tickets:** T-077 through T-090
**Spec source:** `flow-4-student-onboarding.md` v3 (school-student portions: §3.1, §3.3, §3.7, §3.8, §3.9)

## Goal

A Coordinator enrolls students into a Grade + Section (M-03 structure), the student accepts an invite and completes a trimmed onboarding to READY_TO_STUDY, and parents self-register and link to their children (student-approved, read-only). This milestone also builds the graduation lifecycle: a 6-month school-read-only window after final grade, then atomic auto-migration to the independent tenant.

**Scope boundary:** school students + parents only (independent students = M-05, done). Exam Framework engine = M-07. Diagnostic execution + full Mode Switcher = M-08. Lecture creation = M-09+. Parent monitoring surface (dashboards) = Flow 10 (later). This milestone covers enrollment, onboarding, the linking mechanism, exam-date capture, data rights, and graduation/migration.

**Demo at milestone end:**
- Coordinator enrolls a student into Grade 9 / Section A (single + bulk CSV)
- Student accepts the invite, sets a password, confirms name + language + ToS, picks a mode → READY_TO_STUDY
- A Parent self-registers, requests a link to the student by email → student approves → parent gets read-only link state
- Either side revokes the link → access removed immediately
- Student files a data-export request (#15); a delete request is captured
- A final-grade student is graduated → enters SCHOOL_READ_ONLY (Self-Study works, Lecture read-only); after `GRADUATION_GRACE_DAYS` the auto-migration Celery task moves them to the independent tenant atomically, severing parent links

---

## T-077 — School student data model + Coordinator enrollment into Grade-Section

**Layer:** 3
**Milestone:** M-06
**Estimate:** 2 days
**Status:** done
**Commit:** ae47fd1

### Spec source
- `flow-4-student-onboarding.md` §3.1 (enrollment by Coordinator into Grade + Section)

### ARCH source
- `ARCHITECTURE.md` §3.18 (Grade/Section/enrollment), §4 (DB), §6.19 (Coordinator scope)

### Depends on
- T-043 (Grade), T-044 (Section incl. default-internal), T-034 (Coordinator)

### What this ticket builds

**Backend:** `student_enrollments {id, school_id, student_user_id, grade_id, section_id, academic_session, status, enrolled_at}`. Coordinator-scoped enrollment endpoint targeting a Grade + Section (defaulting to the default-internal section from T-044 when the school doesn't use named sections). Student account created in INVITED state.

**Frontend:** On a Section's detail page, "Enroll Student" (name + email) → creates an invited student bound to that Grade+Section.

### Acceptance (demo script)

1. [ ] Coordinator enrolls a student into Grade 9 / Section A → enrollment row + invited account
2. [ ] Enrollment into a sectionless Grade targets the default-internal section
3. [ ] Coordinator outside scope → FORBIDDEN
4. [ ] A student can hold exactly one active enrollment per academic session
5. [ ] Unique constraint prevents duplicate active enrollment

### Out of scope
- The student's own onboarding flow (T-078)
- Bulk import (T-079)
- Promotion between grades (M-22)

---

## T-078 — Student onboarding (invite → password → trimmed fields → mode → READY)

**Layer:** 3
**Milestone:** M-06
**Estimate:** 2 days
**Status:** done
**Commit:** 594cec1

### Spec source
- `flow-4-student-onboarding.md` §3.1 (mandatory fields trimmed; mode selection mandatory)

### ARCH source
- `ARCHITECTURE.md` §6 (auth, invite tokens), §6.19

### Depends on
- T-077 (enrollment creates invited account)

### What this ticket builds

**Backend + frontend:** Invite-link acceptance (7-day validity) → set password → forced PROFILE_BASIC (confirm name, set language, accept ToS — NOTHING else mandatory) → a minimal mode pick (Lecture or Self-Study; at least one) → READY_TO_STUDY derived. Deferrable fields (DOB, avatar, exam framework, date, diagnostic) surface in a dismissible "complete your profile" banner — never blocking.

### Acceptance (demo script)

1. [ ] Invite link valid 7 days; expired link → clear re-invite path
2. [ ] PROFILE_BASIC requires ONLY name + language + ToS
3. [ ] Mode pick (≥1 mode) is required to reach READY_TO_STUDY
4. [ ] Deferrable fields are skippable; banner persists until filled
5. [ ] READY_TO_STUDY derived server-side (grade enrollment auto-satisfied from T-077)

### Out of scope
- Full Mode Switcher UI + persistence (M-08)
- Diagnostic execution (M-08)
- Exam framework selection engine (M-07; date capture is T-083)

### Notes / known gotchas
- Per §3.1: do NOT add fields beyond name/language/ToS to the mandatory set. Mode pick here is minimal (default Lecture for school); the full switcher is M-08.

---

## T-079 — Bulk student enrollment (CSV import)

**Layer:** 3
**Milestone:** M-06
**Estimate:** 2 days
**Status:** done
**Commit:** 4ad9464

### Spec source
- `flow-4-student-onboarding.md` §3.1 (enrollment at scale)

### ARCH source
- `ARCHITECTURE.md` §5.11 (bulk operations), §11.19 (CSV upload profile if applicable)

### Depends on
- T-077 (enrollment), T-039 (bulk import skeleton, M-02)

### What this ticket builds

**Backend + frontend:** Real implementation of the M-02 bulk-import skeleton for students: upload a CSV (name, email, grade, section), validate rows, create invited enrollments in a batch, report per-row success/failure. Partial success allowed (good rows enrolled, bad rows reported).

### Acceptance (demo script)

1. [ ] Coordinator uploads a CSV of 30 students → all enrolled into the correct Grade/Section
2. [ ] Malformed rows reported individually; valid rows still processed
3. [ ] Duplicate emails handled (skip + report, no crash)
4. [ ] Import scoped to Coordinator's grades (out-of-scope rows rejected)
5. [ ] Large import (e.g., 200 rows) completes within a reasonable bound (async if needed)

### Out of scope
- Bulk parent import (parents self-register, T-080)

---

## T-080 — Parent registration (public signup)

**Layer:** 3
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** 2ac9420

### Spec source
- `flow-4-student-onboarding.md` §3.3 (parent registration)

### ARCH source
- `ARCHITECTURE.md` §6 (auth), §6.13 (ParentChildLink)

### Depends on
- T-005 (Authentik, M-00)

### What this ticket builds

**Backend + frontend:** Public parent signup (email + password + name + language) → email verification → PARENT_ACTIVE_UNLINKED. Parents are school-tenant users with the `parent` role but no school_id until linked (link defines scope). 90-day auto-suspend of unlinked parent accounts (resumable on next login).

### Acceptance (demo script)

1. [ ] Parent self-registers and verifies email → PARENT_ACTIVE_UNLINKED
2. [ ] Unlinked parent has no child data access
3. [ ] 90-day inactivity auto-suspends an unlinked parent; next login resumes
4. [ ] Parent role carried in JWT

### Out of scope
- Linking (T-081), monitoring surface (Flow 10)
- Parent linking to independent students (not allowed at launch)

---

## T-081 — Parent → student link request + student approval

**Layer:** 3
**Milestone:** M-06
**Estimate:** 2 days
**Status:** done
**Commit:** 3d10ad6

### Spec source
- `flow-4-student-onboarding.md` §3.3 (link request → student approval, §6.13 opt-in)

### ARCH source
- `ARCHITECTURE.md` §6.13 (ParentChildLink — explicit consent), §6.19

### Depends on
- T-080 (parent accounts), T-078 (student accounts)

### What this ticket builds

**Backend + frontend:** Parent initiates a link by student email → LINK_PENDING → student receives an approval request → explicit student approval creates the link (LINKED). Approval is from the STUDENT side only (consent per §6.13). Until approved, the parent has no access.

### Acceptance (demo script)

1. [ ] Parent requests link by student email → LINK_PENDING
2. [ ] Student sees the pending request and must explicitly approve
3. [ ] On approval → LINKED; parent gains read-only state (access surface = Flow 10, later)
4. [ ] Link to an independent student → blocked (not allowed at launch)
5. [ ] Link to a non-existent / unverified email → clear error, no leak of whether the account exists

### Out of scope
- Read-only monitoring dashboards (Flow 10)
- Revocation (T-082)

### Notes / known gotchas
- Consent is student-initiated approval (§6.13). Never auto-link. Don't reveal account existence on a failed link request (privacy).

---

## T-082 — Link revocation + multi-parent/multi-child + read-only access state

**Layer:** 3
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** 6977d1c

### Spec source
- `flow-4-student-onboarding.md` §3.3 (revocation; multiple parents/children)

### ARCH source
- `ARCHITECTURE.md` §6.13 (ParentChildLink cardinality)

### Depends on
- T-081 (links exist)

### What this ticket builds

**Backend + frontend:** One-click revocation from EITHER side, immediate. A parent may link to multiple students; a student may have multiple parents. Revocation removes access but preserves link history. The "read-only access state" flag is the gate later consumed by Flow 10.

### Acceptance (demo script)

1. [ ] Parent revokes → access removed immediately; history preserved
2. [ ] Student revokes → same
3. [ ] One parent linked to 2 students works; one student with 2 parents works
4. [ ] Revoked link can be re-requested (fresh approval needed)
5. [ ] Access state correctly reflects LINKED vs UNLINKED at all times

### Out of scope
- The actual monitoring views (Flow 10)

---

## T-083 — Exam date capture (#52, school students, deferrable)

**Layer:** 3
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** e93bab4

### Spec source
- `flow-4-student-onboarding.md` §3.7 (exam date lifecycle #52)

### ARCH source
- `ARCHITECTURE.md` §3.19 (Exam Framework — date feeds it later)

### Depends on
- T-078 (student profile)

### What this ticket builds

**Backend + frontend:** A school student can set/update an exam date (deferrable field from the "complete your profile" banner). Stored on the student profile; later consumed by the Exam Framework engine (M-07) and study plans (M-08+). Exam-countdown notifications wired (30/14/7/1 day) but reuse the existing notification infra.

### Acceptance (demo script)

1. [ ] Student sets an exam date from the profile banner (skippable)
2. [ ] Past date → rejected with guidance
3. [ ] Date persists and is editable
4. [ ] Countdown notification hooks registered (delivery validated in M-07/M-08)

### Out of scope
- Exam Framework engine / AI study plan (M-07)
- Diagnostic (M-08)

---

## T-084 — Data rights (#15) — export + delete request

**Layer:** 3
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** f79990c

### Spec source
- `flow-4-student-onboarding.md` §3.8 (data rights lifecycle #15)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit), §14 (retention)

### Depends on
- T-078 (student accounts)

### What this ticket builds

**Backend + frontend:** A student (and parent, for own data) can request a data export (machine-readable bundle of their own data) and submit a deletion request (captured + queued for review, not immediate hard-delete given audit-retention rules). PDPB 2025 alignment. Both actions audit-logged.

### Acceptance (demo script)

1. [ ] Student requests data export → receives a downloadable bundle of their data
2. [ ] Student submits a deletion request → captured + queued (not instant hard-delete)
3. [ ] Export excludes other users' data (only the requester's)
4. [ ] Both actions audit-logged
5. [ ] PDPB-aligned messaging shown to the user

### Out of scope
- Automated hard-deletion pipeline (Phase 2 / launch-readiness)

### Notes / known gotchas
- Don't hard-delete on request — capture + queue, given 7-year audit retention. Surface clear expectations to the user.

---

## T-085 — Graduation: 6-month school-read-only window

**Layer:** 3
**Milestone:** M-06
**Estimate:** 2 days
**Status:** done
**Commit:** 9cef9ed

### Spec source
- `flow-4-student-onboarding.md` §3.9 (GRADUATED — SCHOOL_READ_ONLY)

### ARCH source
- `ARCHITECTURE.md` §3.18 (final grade), §6.19, §14.10

### Depends on
- T-077 (enrollment), T-078 (student state)

### What this ticket builds

**Backend + frontend:** When a final-grade student is graduated (Coordinator request + School Admin approval), enter SCHOOL_READ_ONLY: Lecture Mode visible but read-only (past lectures viewable; no new lectures/questions), Self-Study FULLY accessible, all AI personalization intact, linked parents retain access. State + enforcement only — migration is T-086. Student communication at graduation per §3.9.

### Acceptance (demo script)

1. [ ] Graduating a final-grade student → SCHOOL_READ_ONLY
2. [ ] Lecture Mode is read-only (no new lectures/questions); Self-Study fully works
3. [ ] AI personalization / Cognitive DNA / materials intact
4. [ ] Linked parents retain access during the window
5. [ ] Graduation message delivered to the student

### Out of scope
- Auto-migration (T-086)
- Promotion between non-final grades (M-22)

---

## T-086 — Graduation: atomic auto-migration to independent tenant

**Layer:** 3
**Milestone:** M-06
**Estimate:** 3 days
**Status:** done
**Commit:** 223fc56

### Spec source
- `flow-4-student-onboarding.md` §3.9 (AUTO_MIGRATED_TO_INDEPENDENT, atomic, retries)

### ARCH source
- `ARCHITECTURE.md` §3.16 (independent tenant), §4.21 (dual schemas), §10.3-§10.6 (Celery beat + retries)
- `ARCHITECTURE.md` §6.20 (tenant_type JWT update)

### Depends on
- T-085 (read-only window), T-069 (independent schema/routing, M-05)

### What this ticket builds

**Backend:** Celery beat task scanning for students past `GRADUATION_GRACE_DAYS` (default 180) in SCHOOL_READ_ONLY. Atomic migration transaction: copy migratable data (account, Flow 9 learning data, self-study materials, notes/highlights/flashcards, framework selections, AI conversation history, quiz/diagnostic history) school → independent schema; flip Authentik JWT claim `tenant_type` school→independent (same email/password); mark school records `migrated_out`; auto-sever parent links. NEVER half-migrate (5-attempt retry, then Platform Admin alert; student stays read-only until resolved). School keeps alumni records for 7-year audit. 30-day + 7-day pre-migration reminders.

### Acceptance (demo script)

1. [ ] Student past grace window → migration task fires
2. [ ] Migration is atomic; failure mid-flight → full rollback, retry (5×), then Platform Admin alert
3. [ ] Migratable data lands in independent schema; teacher-attributed records stay in school schema (student's copy migrates)
4. [ ] JWT tenant_type flips school→independent (same credentials)
5. [ ] Parent links auto-severed; alumni record retained in school schema
6. [ ] 30-day + 7-day reminders delivered; migration-day confirmation sent
7. [ ] One-way (no return path to school tenant)

### Out of scope
- Manual admin re-migration tooling (Phase 2)

### Notes / known gotchas
- Atomicity is critical: half-migration is the worst outcome. Use a single transaction with explicit rollback + bounded retries. This is the highest-risk ticket in the milestone.

---

## T-087 — Notifications (account + connections namespaces)

**Layer:** 3
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** 58c8fe0

### Spec source
- `flow-4-student-onboarding.md` §7 (notifications)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS)

### Depends on
- T-081 (link events), T-085/T-086 (graduation events), T-038 (notif infra, M-02)

### What this ticket builds

**Backend:** Deliver notifications: enrollment invite (`account.student_invited`), link request (`connections.link_requested`), link approved/revoked (`connections.link_*`), graduation (`account.graduated`), pre-migration reminders + migration-day confirmation (`account.migration_*`). NATS events for each. All templates in 4 languages.

### Acceptance (demo script)

1. [ ] Each event delivers the right template to the right recipient
2. [ ] Link request notifies student; approval notifies parent
3. [ ] Graduation + migration reminders fire on schedule
4. [ ] NATS events published
5. [ ] Templates present in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Parent monitoring digests (Flow 10)

---

## T-088 — Audit logging

**Layer:** 3 / 6
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** 5fd30e8

### Spec source
- `flow-4-student-onboarding.md` §3.8, §3.9 (audit-logged actions)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log)

### Depends on
- T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Register audit action types: enrollment, bulk import, link request/approve/revoke, data export/delete request, graduation, migration. Migration + data-rights actions flagged elevated. Surface in the existing scope-restricted audit page.

### Acceptance (demo script)

1. [ ] Each action writes an audit entry (actor, action, target, scope, time)
2. [ ] Migration + data-rights flagged elevated
3. [ ] Audit page shows M-06 actions, scope-restricted per role

### Out of scope
- Audit export (Phase 2)

---

## T-089 — E2E smoke test

**Layer:** 6
**Milestone:** M-06
**Estimate:** 1 day
**Status:** done
**Commit:** 91a1488

### Spec source
- `flow-4-student-onboarding.md` §3.1, §3.3, §3.9 (full flows)

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-077 through T-088

### What this ticket builds

**Test harness:** Automated E2E: Coordinator enrolls (single + bulk) → student onboards to READY_TO_STUDY → parent registers + links + student approves → revoke → graduation → read-only enforcement → (time-warped) auto-migration with schema isolation + parent-sever asserted. Runs in CI.

### Acceptance (demo script)

1. [ ] E2E runs green end-to-end
2. [ ] Enrollment + onboarding + READY asserted
3. [ ] Parent link request/approve/revoke asserted
4. [ ] Graduation read-only enforcement asserted
5. [ ] Auto-migration atomicity + schema isolation + parent-sever asserted (grace window mocked)

### Out of scope
- Frontend Playwright E2E (Phase 2)

---

## T-090 — Milestone M-06 PR + demo

**Layer:** 6
**Milestone:** M-06
**Estimate:** 0.5 day
**Status:** done

### Spec source
- `flow-4-student-onboarding.md` v3 (school-student + parent portions)

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-077 through T-089

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-06 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-06` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-089 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-06 ticket set

---

## Milestone notes

- **School students + parents only.** Independent students were M-05.
- **Deferred to later milestones:** Exam Framework engine → M-07; Diagnostic execution + full Mode Switcher → M-08; lecture creation → M-09+; parent monitoring dashboards → Flow 10.
- BLOCKED-HOOK: parent read-only monitoring surface (dashboards, digests; the parent-link access-state flag is the gate) → Flow 10 / M-19 (link + revocation + access-state flag built now; the monitoring views are Flow 10)
- **Highest-risk ticket is T-086 (auto-migration)** — atomicity is non-negotiable; a half-migrated student is the worst outcome. Single transaction, bounded retries, Platform Admin escalation, never a partial state.
- **Onboarding fields are deliberately trimmed** (§3.1): only name + language + ToS are mandatory. Don't expand the mandatory set.
- **Parent linking is consent-first** (§6.13): student-side approval always required; never auto-link; never leak account existence on failed requests.
- **Bulk import (T-079)** finally implements the M-02 skeleton (T-039).
- **Source flow:** Flow 4 v3 (school portions) — finalized, no blockers.

# M-22 — Promotion Workflow + Graduation Lifecycle

**Status:** drafted
**Layer:** 6
**Sequence:** after M-15 (build order); before M-23
**Ticket range:** T-250 to T-261 (off the T-249 high-water mark from M-07a; **non-positional** numbering)
**One PR** (merge commit). **Branch off `staging` only after this docs draft merges.**
**Estimate:** ~1 week (CC-tiered). ROADMAP’s prior “~2-3 days / largely built” note was half-true: graduation/migration shipped in M-06; the **entire Grade promotion state machine** (Flow 2 §3.4 / ARCH §6.21) is greenfield.
**Spec source:** `flow-2-admin-coordinator-setup.md` §3.4 / §5.5 / notifications; `flow-4-student-onboarding.md` §3.9 / §5.9
**ARCH source:** §6.21 (promotion state machine + auth gates), §6.19 (inheritance), §10.3–10.5 (Celery atomic), §9.21 (notification namespaces), §3.16 / §4.21 (dual schema for migration)

## Goal

Year-end **per-grade promotion**: Coordinator initiates with an exclusion list; School Admin (or higher per §6.19) approves; an atomic Celery task migrates eligible enrollments to the next-session Grade (auto-creating the target Grade if needed), resets held-back students onto the same Grade name under the **new** academic session, and sets `promoted_from_grade_id`. **Final-grade (Grade 12 / FSc 2) approval** cascades into the existing graduation lifecycle (M-06): cohort → `GRADUATED` / school-read-only → auto-migration to independent after `GRADUATION_GRACE_DAYS`.

**Demo at milestone end:**
- Coordinator opens a Grade roster, checks held-back students, submits a promotion request → School Admin sees it in the approval queue
- Approve a mid-level Grade → eligible students land in the next-session Grade; held-back stay; `promoted_from_grade_id` populated; notifications fire
- Approve a Grade 12 promotion → non-excluded cohort enters school-read-only graduation; after a time-warped grace window, migration to independent runs atomically
- Reject / expire paths work; failed execution retries then alerts Platform Admin without half-promoted students

---

## Already built (do NOT rebuild)

Built-or-not audit (2026-10-15) against `staging`. Cite these paths; extend / wire — do not fork parallel implementations.

| Area | Evidence |
|---|---|
| Graduation request model + statuses | `api/app/features/graduation/models.py` (`GraduationRequest`, incl. `REJECTED` enum value) |
| Coordinator / School Admin graduation APIs (per-student path) | `api/app/features/graduation/coordinator_router.py`, `school_admin_router.py` |
| Grace window + migrate Celery + beat | `api/app/features/graduation/service.py`, `tasks.py`; beat entries in `api/app/tasks/beat_schedule.py` |
| Graduated / migrated flags | `api/app/features/student_onboarding/models.py` (`is_graduated`, `migrated_out`); config `GRADUATION_GRACE_DAYS`, `FINAL_GRADE_LEVEL_ORDINAL` in `api/app/config.py` |
| Graduation / migration notification templates | `api/app/infrastructure/notifications/templates/account.py` (`account.graduated`, `account.migration_*`) |
| Graduation NATS helpers | `api/app/infrastructure/events/graduation.py` |
| Student graduated banner | `frontend/src/app/student/StudentHomeClient.tsx` |
| `promoted_from_grade_id` column on Grade | `api/app/features/grades/models.py` + Alembic `school/0028_grades_promoted_from_index.py` — **column exists; nothing sets it yet** |
| Graduation service unit tests | `api/app/features/graduation/tests/test_graduation_service.py` |

**What is NOT built (this milestone’s job):** `api/app/features/promotions/` (entire feature), promotion APIs from §6.21, `execute_promotion` Celery task, `promotion.expire_unattended` beat, promotion notification keys + NATS events, Grade-12-promotion→graduation cascade, Coordinator/School Admin promotion UIs, graduation **reject** endpoint, lecture-feature `lecture_read_only` enforcement, `lectures.graduated_read_only` template.

**Inherited forward notes (folded in):** M-03 out-of-scope “Promotion / `promoted_from_grade_id` population (M-22)”; M-06 out-of-scope “Promotion between grades / non-final grades (M-22)”. No literal `BLOCKED-HOOK: … → M-22` lines found.

---

## Pre-draft audit record

1. **Sources on disk:** Flow 2 §3.4, Flow 4 §3.9, ARCH §6.21 — present.
2. **Hooks:** no `BLOCKED-HOOK → M-22`; M-03/M-06 parenthetical deferrals folded above.
3. **Stale-ref:** §6.21 auth table + Celery sketch match Flow 2; notification keys match Flow 2 §7 tables.
4. **Deps:** M-03 (grades/enrollment), M-06 (graduation/migration), M-15 done — OK.
5. **Open-item gate:** no `resolve-before M-22` in STACK_LOCK (pilot-tagged items only).
6. **Modernization:** tickets below carry API contract / Tests / UX-acceptance fields (post-M-01a template).

---

## T-250 — Promotion data model + state machine enums

**Layer:** 6
**Milestone:** M-22
**Estimate:** 0.5 day
**Status:** done
**Commit:** 353900d

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 (state machine), §10 (data-model sketch if present)

### ARCH source
- `ARCHITECTURE.md` §6.21 (states), §4 / §4.12 (model-first migration)

### Depends on
- M-03 grades + enrollments (done); M-06 graduation feature exists for later cascade

### What this ticket builds

**Backend:** New school-schema feature package `api/app/features/promotions/` with SQLAlchemy model intent for `grade_promotion_requests` (or equivalent plural table): source `grade_id`, target session/name fields, `exclusion_list` (JSONB UUID array or child table — prefer child table if relational queries needed), status enum matching §6.21 (`pending_approval` → `approved` → `executing` → `executed` | `rejected` | `expired` | `failed`), attempt count, timestamps, tenant/audit/soft-delete mixins. Model-first Alembic on the **school** head only. Pydantic schemas for Read/Create. No public routes yet.

### API contract
- No HTTP routes in this ticket (schemas only).

### Tests (required)
- pytest: model round-trip create + status enum values; unique “one pending request per grade” constraint if specified.
- Migration upgrades on a fresh school schema (`alembic upgrade heads`).

### Acceptance (demo script)
1. [ ] Table exists in school schema with §6.21 statuses
2. [ ] Autogenerated migration reviewed (one concern) and applies cleanly
3. [ ] Model unit test green

### Out of scope
- Initiate/approve APIs (T-251/T-252); Celery (T-253)

---

## T-251 — Coordinator: initiate promotion + exclusion list

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** done
**Commit:** 323b85f

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 (per-grade initiation, exclusion list), §4 (permissions), §5.5 (scope / auto-create target preview)

### ARCH source
- `ARCHITECTURE.md` §6.21 (`POST /api/v1/grades/:grade_id/promotion-requests`), §6.7 / §6.19

### Depends on
- T-250

### What this ticket builds

**Backend:** `POST /api/v1/grades/{grade_id}/promotion-requests` — Coordinator + `require_scope` on the grade’s school. Body: target academic session (+ optional target grade name), `exclusion_list` of student IDs from the current roster. Validates every exclusion ID is enrolled in that grade; rejects duplicate pending request; returns 404 on cross-tenant/out-of-scope. Roster helper endpoint for the FE (or reuse existing grade roster) so the Coordinator can checkbox held-back students. Emits notification/NATS hooks only if T-255 lands same PR wave — otherwise leave a clear service hook; prefer shipping T-255 before FE.

### API contract
- `POST /api/v1/grades/{grade_id}/promotion-requests` → `response_model=` promotion request Read; roles: coordinator (scoped).
- `GET` roster-for-promotion helper if not already available — declare `response_model=`.
- Regenerate OpenAPI + `schema.d.ts` (`pnpm gen:api`).

### Tests (required)
- pytest API: happy path creates `pending_approval`; exclusion of non-enrolled student → 422; out-of-scope grade → 404; second pending → precondition failed.
- Cross-tenant denial (§3.13).

### Acceptance (demo script)
1. [ ] Coordinator creates a pending promotion with 2 held-back students on the exclusion list
2. [ ] Out-of-scope Coordinator gets 404
3. [ ] Typed client regenerated

### Out of scope
- Approve/reject (T-252); execution (T-253); FE (T-258)

---

## T-252 — School Admin: list / approve / reject (+ inheritance)

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** done
**Commit:** be3c263

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 (approval gate), §4 (Approve promotion), §5.5 (re-initiate after reject)

### ARCH source
- `ARCHITECTURE.md` §6.21 (`GET …/promotion-requests`, `…/approve`, `…/reject`), §6.19

### Depends on
- T-251

### What this ticket builds

**Backend:** List pending (filterable by status) for the school; `POST …/approve` and `POST …/reject` with School Admin minimum role + scope (District/Platform inherit). Approve → status `approved` and enqueue `execute_promotion` (T-253). Reject → terminal `rejected` with optional reason; Coordinator may re-initiate. Audit log entry per approval/reject. `GET /api/v1/promotion-requests/{id}` for coordinator/admin scoped view.

### API contract
- Endpoints exactly as §6.21 table; every route declares `response_model=` + access deps; `pnpm gen:api`.

### Tests (required)
- pytest: School Admin approve/reject happy paths; Coordinator cannot approve; wrong school → 404; inheritance smoke for District Admin.
- Side-effect fixtures: Celery enqueue mocked until T-253 (autouse AsyncMock).

### Acceptance (demo script)
1. [ ] School Admin sees pending request in list
2. [ ] Approve transitions to `approved` and enqueues execution
3. [ ] Reject is terminal; Coordinator can create a new request afterward

### Out of scope
- Celery body (T-253); FE queue (T-259)

---

## T-253 — Celery `execute_promotion` (atomic + retries + linkage)

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1.5 days
**Status:** done
**Commit:** 35b7a00

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 (atomic bulk migrate / held-back session reset), §5.5 (rollback, auto-create target Grade), soft_time_limit note

### ARCH source
- `ARCHITECTURE.md` §6.21 (task sketch), §10.3–10.5, §4 (`promoted_from_grade_id`)

### Depends on
- T-252

### What this ticket builds

**Backend:** `api/app/features/promotions/tasks.py` — `@tenant_task(max_retries=5)` `execute_promotion`: single DB transaction; ensure/create target Grade for next session; migrate eligible enrollments; held-back → same grade name + **new** academic session (re-enrollment semantics); set target Grade.`promoted_from_grade_id` = source grade; status `executing` → `executed` (or `failed` after retries). Full rollback on error; Platform Admin notified on terminal failure (wire notification in T-255 if not yet present — stub hook OK). Soft time limit ~10 minutes for large grades. **Non-final grades only here** — final-grade cascade is T-256 (detect final grade and branch).

### API contract
- No new HTTP; task invoked from approve path.

### Tests (required)
- pytest: promotes N students, excludes M; rolls back on injected failure; retries; asserts `promoted_from_grade_id`; held-back academic_session updated.
- Disposable-engine pattern for Celery/async tests (`run_db` / per-loop engine).

### Acceptance (demo script)
1. [ ] Approve a Grade 9 promotion → students appear in Grade 10 next session
2. [ ] Held-back students remain on Grade 9 under the new session
3. [ ] Forced mid-task failure leaves original enrollments intact after retries exhaust

### Out of scope
- Grade 12 graduation cascade (T-256); beat expiry (T-254)

### Notes / known gotchas
- Populate the **existing** `promoted_from_grade_id` column — do not add a duplicate linkage field.

---

## T-254 — Beat: expire unattended + 30-day reminder

**Layer:** 6
**Milestone:** M-22
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §5.5 (30-day reminder; 60-day expiry; re-initiate)

### ARCH source
- `ARCHITECTURE.md` §10.6 (beat), §9.21

### Depends on
- T-251 (pending requests exist); T-255 for template delivery (can land same milestone PR)

### What this ticket builds

**Backend:** Celery beat task `promotion.expire_unattended`: at 30 days pending → reminder to Coordinator (`account.promotion_expired` is for expiry; use the pending-reminder key from Flow 2 tables — `account.promotion_pending_approval` already sent at create; add a distinct reminder or reuse per spec); at 60 days → status `expired` (terminal). Coordinator must re-initiate after expiry/reject.

### API contract
- N/A (beat only). Register in `beat_schedule.py`.

### Tests (required)
- pytest: time-warped pending request gets reminder flag/send mock at 30d; expires at 60d; executed/approved requests ignored.

### Acceptance (demo script)
1. [ ] 30-day-old pending request triggers reminder (mocked clock)
2. [ ] 60-day-old pending request becomes `expired`
3. [ ] Beat entry present in schedule

### Out of scope
- Notification template copy polish beyond keys (T-255)

---

## T-255 — Promotion notifications + NATS events

**Layer:** 6
**Milestone:** M-22
**Estimate:** 0.75 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §7 notification tables (`account.promotion_*`, `lectures.promoted`, `lectures.held_back`)

### ARCH source
- `ARCHITECTURE.md` §9.21, §9.3–9.7 / publish-after-commit

### Depends on
- T-251–T-254 (call sites); reuse notif infra from M-02/M-06

### What this ticket builds

**Backend:** Templates (en/ur/sd/ps, no `__TODO__`) for: `account.promotion_pending_approval`, `account.promotion_approved`, `account.promotion_rejected`, `account.promotion_expired`, `account.promotion_execution_failed`, `lectures.promoted`, `lectures.held_back`. NATS: `promotion.requested` / `approved` / `executed` / `failed` (publish-after-commit). Wire into initiate/approve/reject/execute/expire paths. Autouse AsyncMocks in existing promotion tests.

### API contract
- N/A (side effects).

### Tests (required)
- pytest: each transition publishes the expected template key + NATS subject (mocked bus).
- Snapshot: template keys exist in all 4 locales.

### Acceptance (demo script)
1. [ ] Initiate → School Admin notified
2. [ ] Execute → promoted + held-back student/parent notifications
3. [ ] Terminal failure → Platform Admin + Coordinator notified

### Out of scope
- `lectures.graduated_read_only` (T-257)

---

## T-256 — Grade 12 promotion → graduation cascade

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 / §5.5 (final grade → Flow 4 §3.9)
- `flow-4-student-onboarding.md` §3.9 (cohort via promotion approval)

### ARCH source
- `ARCHITECTURE.md` §6.21 (Grade 12 triggers graduation cascade)

### Depends on
- T-253; M-06 T-085/T-086 (`GraduationService`)

### What this ticket builds

**Backend:** When executing a promotion whose source Grade is final (`FINAL_GRADE_LEVEL_ORDINAL`, default 12): do **not** create a next academic Grade for the cohort; instead mark non-excluded students graduated via existing `GraduationService` (school-read-only window). Excluded students follow held-back session-reset rules. Prefer promoting the **cohort path** as the canonical graduation entry; keep the M-06 per-student request APIs for edge/admin cases unless product decides to deprecate (do not delete in this ticket — document coexistence). Ensure migration beat still picks them up.

### API contract
- No new endpoints unless a thin “preview final-grade” flag is needed on the Read schema.

### Tests (required)
- pytest: Grade 12 approve → eligible students `is_graduated`; exclusions held back; mid-level grade still uses enrollment migrate path.
- Integration: time-warp grace → existing migrate task still succeeds for cascade-graduated students.

### Acceptance (demo script)
1. [ ] Approve Grade 12 promotion → cohort enters school-read-only
2. [ ] Held-back Grade 12 students do **not** graduate
3. [ ] Existing migration beat still migrates a cascade-graduated student after grace

### Out of scope
- Alumni dashboards (Flow 11 / M-20b)
- Deep copy of not-yet-built Flow 9 DNA payloads (migrate what exists; extend when M-18 ships)

### Notes / known gotchas
- BLOCKED-HOOK: richer migrate payload (full Cognitive DNA / predictions / FSRS state) → Flow 9 / M-18 once those stores exist (M-06 already copies account + available learning fields).

---

## T-257 — Graduation gap closure (reject, read-only enforcement, edge locks)

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.9 (Lecture Mode read-only; Self-Study full), §5.1 (delete during window cancels migration), mid-flight migration lock

### ARCH source
- `ARCHITECTURE.md` §6.21 cascade note; lecture feature gates as applicable

### Depends on
- T-256; existing M-06 graduation routers

### What this ticket builds

**Backend + light FE if needed:**
1. School Admin **reject** endpoint for `GraduationRequest` (`REJECTED` enum already exists — wire the route).
2. Enforce `lecture_read_only` on lecture study surfaces for graduated students (block new questions / new lecture sessions; past lectures viewable) — Soft-Study untouched.
3. Add `lectures.graduated_read_only` notification template if missing; send on cascade/graduation.
4. Account deletion during grace cancels pending migration; mid-flight migration returns clear 503 / lock so login doesn’t half-serve two tenants.

### API contract
- `POST /api/v1/graduation/requests/{id}/reject` (or school-admin mirror of approve) with `response_model=`; `pnpm gen:api`.

### Tests (required)
- pytest: reject path; graduated student blocked from new lecture Q&A; delete cancels migration; concurrent migrate lock.
- Vitest if any FE banner/copy changes.

### Acceptance (demo script)
1. [ ] School Admin can reject a standalone graduation request
2. [ ] Graduated student can open past lectures but cannot post a new question
3. [ ] Delete-during-window cancels migration

### Out of scope
- Coordinator/School Admin FE for the standalone graduation path (optional polish — promotion UI is the primary cohort path)
- Parent email about Independent move beyond existing templates (extend only if a dedicated key is specified and missing)

---

## T-258 — FE: Coordinator promotion + exclusion UI

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 (roster checkboxes)

### ARCH source
- `ARCHITECTURE.md` §12 / §13 (four states, i18n)

### Depends on
- T-251; typed client from T-251/T-252

### What this ticket builds

**Frontend:** Nav-reachable Coordinator page/flow on the existing grades surface: pick Grade → see full roster → checkbox “stay in Grade X for next session” → submit promotion request (target session). Loading / empty / error / success states; next-intl keys only; RTL-aware layout. Uses generated client types for the Create body.

### API contract
- Consumes generated `*Create` / Read types only (no hand-mirrored request shapes).

### Tests (required)
- Vitest+RTL: four UI states; exclusion checkboxes update payload.
- Playwright `@smoke` against real backend: initiate promotion for a seeded grade.

### UX acceptance
- Reachable from Coordinator nav; real roster content; scrolls; responsive; RTL; all strings via next-intl.

### Acceptance (demo script)
1. [ ] Coordinator submits a promotion with two exclusions from the UI
2. [ ] Empty roster / error / success states visible
3. [ ] Smoke E2E green

### Out of scope
- School Admin queue (T-259); bulk-promote-all (Phase 2 / deferred register)

---

## T-259 — FE: School Admin promotion approval queue

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.4 / §4

### ARCH source
- `ARCHITECTURE.md` §12 / §13

### Depends on
- T-252; T-258 (shared types/components OK)

### What this ticket builds

**Frontend:** School Admin approval queue — list pending promotion requests; detail with exclusion summary; Approve / Reject actions; four UI states; i18n. After approve, show executing/executed status (poll or invalidate query).

### API contract
- Generated client only.

### Tests (required)
- Vitest+RTL: list + approve/reject flows (mock network for unit; contract shapes from schema).
- Playwright `@smoke` real-backend: approve a pending request seeded by API.

### UX acceptance
- Reachable from School Admin nav; real content; scrolls; responsive; RTL; i18n.

### Acceptance (demo script)
1. [ ] School Admin approves from UI → students promoted (or Grade 12 graduated)
2. [ ] Reject shows terminal state and notifies Coordinator (assert via API/notif mock in unit; E2E checks status)

### Out of scope
- District Admin dedicated UI (inheritance via same queue + role is enough at launch)

---

## T-260 — Permissions matrix, audit labels, i18n completeness

**Layer:** 6
**Milestone:** M-22
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §4 promotion rows; Flow 4 §4 promotion rows

### ARCH source
- `ARCHITECTURE.md` §6.19, §14.10 (audit)

### Depends on
- T-251–T-259

### What this ticket builds

**Backend + frontend:** Confirm every promotion endpoint uses `require_role` + `require_scope` with §6.19 inheritance; register audit action labels for initiate/approve/reject/execute/fail/expire; finish any missing next-intl keys (en/ur/sd/ps). Permission matrix test table.

### API contract
- N/A (hardening).

### Tests (required)
- pytest parametrize role×action matrix for promotion endpoints.
- Frontend audit label map covers new actions.

### Acceptance (demo script)
1. [ ] Matrix test green for coordinator/school_admin/district_admin/platform_admin
2. [ ] Audit page shows promotion actions with human labels
3. [ ] No `__TODO__` in promotion/graduation i18n keys touched this milestone

### Out of scope
- Promotion approval delegation (TODO `phase-2-promotion-delegation` — Rollout/deferred series)

---

## T-261 — M-22 E2E journey + PR + demo

**Layer:** 6
**Milestone:** M-22
**Estimate:** 1 day
**Status:** todo

### Spec source
- Flow 2 §3.4 + Flow 4 §3.9 acceptance themes

### ARCH source
- Milestone close-out per WORKFLOW

### Depends on
- T-250 through T-260

### What this ticket builds

**Test harness + close-out:** Playwright (or API+E2E hybrid) covering: mid-grade promote with exclusions → held-back session reset → Grade 12 cascade → read-only enforcement → time-warped migration. Open the milestone PR to `staging` with phase-complete-review; demo script for Abd. + Awais. Mark all tickets done with commit SHAs; ROADMAP roll-up via CI.

### API contract
- N/A.

### Tests (required)
- Milestone `@smoke` / E2E green in CI against composed backend.

### Acceptance (demo script)
1. [ ] Full mid-grade promotion journey green
2. [ ] Full Grade 12 → graduate → migrate journey green (grace mocked)
3. [ ] PR merged to `staging`; ROADMAP M-22 → `done`

### Out of scope
- M-23 drafting/implementation

---

## Soft dependencies / deferred

- **Bulk-promote-all grades** — Phase 2 / deferred register (`phase-2` in Flow 2).
- **Promotion approval delegation** — `phase-2-promotion-delegation`.
- **Promotion preview before submit** — `phase-2-promotion-preview` (auto-create target at execute remains).
- **Alumni dashboard status** — Flow 11 / M-20b.
- **Full Flow 9 learning-payload migrate** — BLOCKED-HOOK on T-256 → M-18.

---

## Open questions (for PR description; merger decides)

1. Keep M-06 per-student graduation request UI forever, or soft-deprecate once promotion cascade is canonical? (Code keeps APIs either way in T-256.)
2. Exact reminder template key at day-30 pending (Flow 2 lists pending/expired/failed — confirm whether a distinct `account.promotion_reminder` is wanted or reuse pending).

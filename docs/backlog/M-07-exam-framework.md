# M-07 — Exam Framework Engine (platform tier)

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-091 through T-100
**Spec source:** `flow-4-student-onboarding.md` v3 §3.5 (Exam Framework lifecycle), ARCH §3.19 + §8.21

## Goal

Platform Admin defines an Exam Framework (e.g., "Matric Punjab Board — Physics"), triggers an AI research run (Pattern-A agent: SearXNG web search → web_fetch → LLM synthesis) that produces a versioned, structured study plan (JSONB), manually approves it, and publishes it. Students can then select frameworks (optional for school, mandatory for independent — both gated already in M-05/M-06). Frameworks refresh quarterly via a Celery beat agent.

**Scope boundary:** the framework ENGINE + selection. Self-Study integration is hooked here; the Lecture Mode "exam prep track" overlay UI is deferred to M-09+ (lecture mode doesn't exist yet). Diagnostic = M-08. Study-plan execution against the framework = Flow 8 (M-08+).

**Demo at milestone end:**
- Platform Admin creates a framework definition (DRAFT): name, exam target, region, target grade range, language
- Platform Admin triggers AI research → RESEARCHING (SearXNG + web_fetch + LLM synthesis) → PENDING_APPROVAL with cited sources
- Platform Admin reviews the generated study-plan JSONB + sources → approves → PUBLISHED v1
- A student selects the framework → ACTIVE, pinned to v1; the structured plan renders in a learnable UI
- The quarterly refresh agent (time-warped) produces v2 → Platform Admin approves → existing students see "updated to v2 — switch?" (opt-in); new students get v2
- Region scoping verified: a Punjab student sees Punjab + "any" frameworks, not Sindh-only ones

---

## T-091 — Exam Framework data model (definitions + versions + selections)

**Layer:** 3
**Milestone:** M-07
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-4-student-onboarding.md` §3.5.1, §3.5.2, §3.5.3

### ARCH source
- `ARCHITECTURE.md` §3.19 (Exam Framework engine), §3.16 (platform-shared tables), §4 (DB)

### Depends on
- T-016 (Platform Admin, M-01), T-021 (exam syllabi seeded, M-01)

### What this ticket builds

**Backend:** Migrations for platform-shared tables (live in school schema, exposed to independent via cross-schema views per §3.16): `exam_frameworks {id, name, exam_target, region, target_grade_range int[], language, status ENUM[draft, researching, pending_approval, published, refreshing, deprecated], created_by, created_at}`; `framework_study_plans {id, framework_id, version, content_jsonb, sources_cited_jsonb, generated_at, approved_by (nullable), approved_at (nullable), status}`; `student_framework_selections {id, tenant_type, student_user_id, framework_id, pinned_version, status ENUM[active, abandoned], selected_at}`.

**Frontend:** None (model only).

### Acceptance (demo script)

1. [ ] All three tables exist with the status enums + constraints
2. [ ] `content_jsonb` holds the §3.5.2 structure (topics, weekly_pacing, exam_strategy)
3. [ ] Frameworks are platform-tier; reachable read-only from independent schema (cross-schema view)
4. [ ] `target_grade_range` + `region` present for filtering (T-096)
5. [ ] A student may have multiple active selections (no unique-per-student constraint)

### Out of scope
- Research agent (T-093), selection UI (T-096)

---

## T-092 — Framework definition CRUD (Platform Admin, DRAFT)

**Layer:** 3
**Milestone:** M-07
**Estimate:** 1 day
**Status:** done
**Commit:** 6986b64

### Spec source
- `flow-4-student-onboarding.md` §3.5.1 (DRAFT creation)

### ARCH source
- `ARCHITECTURE.md` §3.19, §6.19 (Platform Admin only)

### Depends on
- T-091 (data model)

### What this ticket builds

**Backend + frontend:** Platform Admin creates/edits/deletes framework definitions in DRAFT (name, exam target, region, target grade range, language). Platform-Admin-only. Definition is a thin metadata record until research runs.

### Acceptance (demo script)

1. [ ] Platform Admin creates a DRAFT framework with all metadata fields
2. [ ] Non-Platform-Admin → FORBIDDEN
3. [ ] Edit/delete a DRAFT works
4. [ ] Region + grade range validated (grade range within 1-14)
5. [ ] Framework list page shows status per definition

### Out of scope
- Triggering research (T-093)

---

## T-093 — Pattern-A AI research agent (SearXNG → web_fetch → LLM synthesis)

**Layer:** 3
**Milestone:** M-07
**Estimate:** 4 days
**Status:** done
**Commit:** f930079

### Spec source
- `flow-4-student-onboarding.md` §3.5.1 (AI research workflow), §3.5.2 (output structure)

### ARCH source
- `ARCHITECTURE.md` §7.12 (Pattern A — Agentic RAG), §8.21 (quarterly framework refresh agent)
- `ARCHITECTURE.md` §10.3-§10.5 (Celery), §3.19 (cost ceiling)

### Depends on
- T-092 (DRAFT frameworks), T-010/T-011 (RAG+LLM base, M-00), searxng service (M-00)

### What this ticket builds

**Backend:** The Pattern-A agentic research run as a Celery task: (1) SearXNG web search for past papers / study guides / syllabus / expert tips; (2) `web_fetch` top 10-20 sources; (3) LLM synthesis into the §3.5.2 JSONB structure (topics with priority weights + exam frequency + key concepts + pitfalls + past-paper patterns + AI-generated practice problems + expert tips; weekly pacing; exam strategy); (4) record `sources_cited`; (5) set status PENDING_APPROVAL. Status flows DRAFT → RESEARCHING → PENDING_APPROVAL. Cost ceiling `FRAMEWORK_RESEARCH_COST_CEILING_USD` (default 10) enforced.

**Frontend:** "Trigger AI research" button on a DRAFT framework; progress indicator through RESEARCHING.

### Acceptance (demo script)

1. [ ] Triggering research moves DRAFT → RESEARCHING → PENDING_APPROVAL
2. [ ] SearXNG search + web_fetch executed; 10-20 sources gathered
3. [ ] LLM synthesis produces valid §3.5.2 JSONB structure
4. [ ] `sources_cited` populated with URLs + titles
5. [ ] Practice problems are AI-generated (not verbatim copies); copyright note attached
6. [ ] Cost ceiling enforced; overrun halts with partial result flagged
7. [ ] Research failure retries (3×) then surfaces error; framework stays DRAFT

### Out of scope
- Approval (T-094), refresh scheduling (T-095)
- Verbatim past-paper republishing (explicitly forbidden)

### Notes / known gotchas
- This is the heaviest ticket — first real Pattern-A agentic run. Reuse the §7.12 agent primitives; don't build a parallel agent.
- Copyright: AI generates SIMILAR practice problems, never republishes copyrighted past papers. Always cite sources.

---

## T-094 — Approval workflow (PENDING_APPROVAL → PUBLISHED, SLA + escalation)

**Layer:** 3
**Milestone:** M-07
**Estimate:** 2 days
**Status:** done
**Commit:** 9625fb5

### Spec source
- `flow-4-student-onboarding.md` §3.5.1 (manual approval gate; 72hr SLA, 7-day reminder, 14-day escalation)

### ARCH source
- `ARCHITECTURE.md` §3.19 (approval workflow), §10.6 (beat for SLA timers), §14.10 (audit)

### Depends on
- T-093 (produces PENDING_APPROVAL plans)

### What this ticket builds

**Backend + frontend:** Platform Admin review surface — read the generated study-plan JSONB + cited sources, then approve (→ PUBLISHED) or reject (→ back to DRAFT with notes). SLA timers via Celery beat: 72hr target; 7-day reminder; 14-day escalation. Unapproved plans never reach students; students see "framework being prepared."

### Acceptance (demo script)

1. [ ] Platform Admin reviews plan content + sources before approving
2. [ ] Approve → PUBLISHED v1 (visible/selectable by students)
3. [ ] Reject → DRAFT with reviewer notes
4. [ ] 7-day reminder + 14-day escalation fire for unapproved plans
5. [ ] Students never see unapproved plans ("being prepared" message)
6. [ ] Approval audit-logged

### Out of scope
- Versioning/refresh (T-095)

---

## T-095 — Versioning + quarterly refresh + deprecation

**Layer:** 3
**Milestone:** M-07
**Estimate:** 2 days
**Status:** done
**Commit:** _pending (this commit)_

### Spec source
- `flow-4-student-onboarding.md` §3.5.1 (REFRESHING, versioning, deprecation)

### ARCH source
- `ARCHITECTURE.md` §8.21 (refresh agent), §10.6 (beat `framework.refresh_quarterly`), §3.19

### Depends on
- T-093 (research agent), T-094 (approval)

### What this ticket builds

**Backend + frontend:** Celery beat `framework.refresh_quarterly` (cadence `FRAMEWORK_REFRESH_DAYS`, default 90) re-runs research for each active framework → new version → same approval gate. Students pinned to v1 see "updated to v2 — review/switch?" (opt-in). New students get the latest published version. Platform Admin can deprecate (no new selections; existing students grandfathered).

### Acceptance (demo script)

1. [ ] Quarterly beat triggers re-research → new version → PENDING_APPROVAL
2. [ ] Approved v2 published; v1-pinned students see opt-in switch banner
3. [ ] New students get the latest version by default
4. [ ] Deprecate → not offered to new students; existing grandfathered
5. [ ] Version history retained

### Out of scope
- Auto-switching students without consent (forbidden — opt-in only)

---

## T-096 — Student framework selection + study-plan rendering + region scoping

**Layer:** 3
**Milestone:** M-07
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.5.2 (render structure), §3.5.3 (selection), §3.5.4 (mode interaction)

### ARCH source
- `ARCHITECTURE.md` §3.19 (selection + mode interaction)

### Depends on
- T-094 (published frameworks), T-071 (independent student, M-05), T-078 (school student, M-06)

### What this ticket builds

**Backend + frontend:** Students browse + select frameworks (filtered by region matching their region OR "any", and grade range). Multiple selections allowed. Selection pins to current published version. The §3.5.2 JSONB renders into a learnable study-plan UI (topics, weekly pacing, exam strategy). Self-Study integration hook: framework structure available to the (future Flow 8) self-study planner. Lecture Mode "exam prep track" overlay is a documented hook only (UI deferred to M-09+).

### Acceptance (demo script)

1. [ ] Student selects a framework → ACTIVE, pinned to current version
2. [ ] Region filter: Punjab student sees Punjab + "any"; not Sindh-only
3. [ ] Grade-range filter applied
4. [ ] Multiple frameworks per student supported
5. [ ] JSONB renders into a readable study-plan UI
6. [ ] Self-study hook exposes framework structure (consumed in Flow 8 / M-08+)
7. [ ] Switch/drop works; historical progress retained

### Out of scope
- Lecture Mode overlay UI (M-09+; hook only here)
- Self-study plan EXECUTION (Flow 8, M-08+)
- Diagnostic calibration from framework (M-08)

---

## T-097 — Notifications (`framework` namespace)

**Layer:** 3
**Milestone:** M-07
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.5 (framework events)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS)

### Depends on
- T-093, T-094, T-095 (events), T-038 (notif infra, M-02)

### What this ticket builds

**Backend:** Deliver notifications: research complete / pending approval (Platform Admin), approval SLA reminders + escalation (Platform Admin), framework published, v2 available for pinned students (`framework.version_available`). NATS events for lifecycle transitions. Templates in 4 languages.

### Acceptance (demo script)

1. [ ] Research-complete + pending-approval notify Platform Admin
2. [ ] SLA reminder + escalation fire on schedule
3. [ ] Published + v2-available notify relevant students
4. [ ] NATS events published per transition
5. [ ] Templates in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Student study-plan reminders (Flow 8, M-08+)

---

## T-098 — Audit logging

**Layer:** 3 / 6
**Milestone:** M-07
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.5 (audit-logged actions)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log)

### Depends on
- T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Register audit action types: framework create/edit/delete, research triggered, approval/rejection, publish, refresh, deprecate. Approval + publish flagged elevated (they expose content to students). Surface in the audit page.

### Acceptance (demo script)

1. [ ] Each lifecycle action writes an audit entry
2. [ ] Approval + publish flagged elevated
3. [ ] Audit page shows M-07 actions (Platform-Admin scope)

### Out of scope
- Audit export (Phase 2)

---

## T-099 — E2E smoke test

**Layer:** 6
**Milestone:** M-07
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.5 (full framework flow)

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-091 through T-098

### What this ticket builds

**Test harness:** Automated E2E: Platform Admin creates DRAFT → triggers research (SearXNG/web_fetch mocked or sandboxed) → PENDING_APPROVAL → approve → PUBLISHED v1 → student selects (region filter asserted) → plan renders → quarterly refresh (time-warped) → v2 approved → pinned-student opt-in banner asserted. Runs in CI.

### Acceptance (demo script)

1. [ ] E2E runs green end-to-end
2. [ ] Research run asserted (mocked external fetch — no live network in CI)
3. [ ] Approval gate + SLA path asserted
4. [ ] Student selection + region filter asserted
5. [ ] Refresh → v2 → opt-in switch asserted

### Out of scope
- Frontend Playwright E2E (Phase 2)

### Notes / known gotchas
- CI network is restricted — mock/sandbox SearXNG + web_fetch in the test; do not hit live web.

---

## T-100 — Milestone M-07 PR + demo

**Layer:** 6
**Milestone:** M-07
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` v3 §3.5

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-091 through T-099

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-07 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-07` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-099 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-07 ticket set

---

## Milestone notes

- **Platform-tier feature.** Frameworks live in platform-shared tables (school schema), reachable read-only from the independent schema via cross-schema views (§3.16) — same pattern as M-05 Platform Library.
- **Heaviest ticket is T-093 (Pattern-A research agent)** — first real agentic run (SearXNG → web_fetch → LLM synthesis). Reuse §7.12 primitives; enforce the cost ceiling; never republish copyrighted past papers (AI-generate similar problems + cite sources).
- **Manual approval is a hard gate** — no AI-generated plan reaches students without Platform Admin approval (72hr SLA, escalation).
- **Versioning is opt-in for pinned students** — never auto-switch a student to a new version.
- **Mode interaction:** self-study integration is a real hook here; the Lecture Mode "exam prep track" overlay UI is deferred to M-09+ (lecture mode not built yet). Documented, not implemented.
- **Selection gating** (optional school / mandatory independent) was already enforced in M-05 (T-071) and M-06 (T-078); this milestone provides the selection mechanics + content.
- **Source flow:** Flow 4 v3 §3.5 + ARCH §3.19/§8.21 — finalized, no blockers.

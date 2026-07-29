# M-08 — Student Mode + Diagnostic + Cognitive DNA seed

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-101 through T-112
**Spec source:** `flow-4-student-onboarding.md` v3 §3.4 (Mode selection #53), §3.6 (Diagnostic #51), §3.7 (Exam date approach #52)

## Goal

School students get a real Mode Switcher (Lecture ⇄ Self-Study, instant, no data loss); independent students stay locked to Self-Study. Students take a diagnostic (per-subject for school, per-framework for independent) whose results are framed as "areas to focus on" (never grades) and seed a minimal **Cognitive DNA** store. Exam-date approach notifications go live.

**⚠ Soft dependency / scope caution:** the FULL Cognitive DNA engine (mistake tracking, pass probability, spaced repetition, forgetting curve, Question Bank) is **Flow 9 / M-18**, which is **not yet drafted (blocked)**. M-08 builds ONLY the *seed*: a minimal `cognitive_dna` store that the diagnostic initializes (per-topic confidence + focus areas). Its schema is **provisional** and will be extended by Flow 9/M-18. Diagnostic questions are **LLM-generated** at launch; the Question Bank (#74, Flow 9) is a deferred hook. If Flow 9 drafting later changes the DNA structure, a follow-up migration may be needed (tracked in milestone notes + TODO).

**Demo at milestone end:**
- A school student toggles Lecture ⇄ Self-Study instantly; dashboard adapts; no data loss
- An independent student has no switcher; a mode-switch API call returns 404
- A school student takes a per-subject diagnostic (15-25 LLM-generated questions); can save + resume within 7 days
- An independent student takes a per-framework diagnostic calibrated by their framework's topic priorities
- Results show as "focus areas" (coaching), never a grade
- Diagnostic results seed the student's Cognitive DNA (correct schema per tenant)
- A retake is blocked within 30 days
- Exam-date approach (30 days out) fires a countdown notification

---

## T-101 — Mode Switcher (school toggle; independent locked)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 2 days
**Status:** done
**Commit:** `1ab1253`

### Spec source
- `flow-4-student-onboarding.md` §3.4 (Mode selection #53)

### ARCH source
- `ARCHITECTURE.md` §3.16 (independent tenant), §6.19, §6.20 (tenant_type)

### Depends on
- M-07a (login-flow remediation merged — cookie auth + per-role E2E are the base every M-08 surface builds on)
- T-078 (school student onboarding, M-06), T-071 (independent student, M-05)

### What this ticket builds

**Backend + frontend:** A real Mode Switcher for school students (Lecture ⇄ Self-Study), switching instantly with no data loss; mode persisted in `user_settings`. Dashboard is mode-conditional (Lecture section hidden in Self-Study). Independent students: NO switcher rendered; backend rejects mode-switch API calls with 404.

### Acceptance (demo script)

1. [ ] School student toggles Lecture ⇄ Self-Study instantly; state persists
2. [ ] No data loss across switches (each mode restores its last state)
3. [ ] Dashboard is mode-conditional (Lecture hidden in Self-Study Mode)
4. [ ] Independent student sees no switcher
5. [ ] Mode-switch API for an independent user → 404

### Out of scope
- Lecture Mode content surfaces (M-09+); Self-Study sessions (Flow 8, M-17)
- Per-session AI adaptation (#61 — hook only, T-108)

### Notes / known gotchas
- The minimal mode pick at onboarding shipped in M-06 (T-078). This ticket is the full switcher + persistence + mode-conditional dashboard.

---

## T-102 — Cognitive DNA seed data model (provisional)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 1 day
**Status:** done
**Commit:** `2dcd28c`

### Spec source
- `flow-4-student-onboarding.md` §3.6 (results seed Cognitive DNA per Flow 9 #83)

### ARCH source
- `ARCHITECTURE.md` (file tree `infrastructure/ml/cognitive_dna.py`), §3.16 (per-tenant), §4

### Depends on
- T-069 (independent schema, M-05), T-077 (school student, M-06)

### What this ticket builds

**Backend:** A MINIMAL `cognitive_dna` store written to BOTH schemas: `cognitive_dna {id, tenant_type, student_user_id, subject_id (nullable), framework_id (nullable), topic_confidence_jsonb, focus_areas_jsonb, source ENUM[diagnostic, ...], last_updated_at}`. This is the seed only — Flow 9/M-18 will extend it with mistake history, predictions, spaced-repetition state, etc. Schema explicitly marked provisional.

**Frontend:** None.

### Acceptance (demo script)

1. [ ] `cognitive_dna` table exists in both schemas (provisional, documented as seed-only)
2. [ ] Holds per-topic confidence + focus areas as JSONB
3. [ ] Per-tenant isolation (school DNA in school schema, independent in independent)
4. [ ] `source` enum allows future expansion (diagnostic now; more later)
5. [ ] A code comment + TODO marks this as Flow 9/M-18-extensible

### Out of scope
- Mistake tracking, pass probability, spaced repetition, forgetting curve, Question Bank (ALL Flow 9 / M-18)

### Notes / known gotchas
- Do NOT build the full DNA engine here. Minimal seed only. Flow 9 owns the real structure; coordinate when M-18 is unblocked.
- BLOCKED-HOOK: `cognitive_dna` schema extension (mistake history, predictions, spaced-repetition state) → Flow 9 / M-18 (provisional diagnostic-seed schema for now)

---

## T-103 — Diagnostic data model + lifecycle

**Layer:** 3
**Milestone:** M-08
**Estimate:** 2 days
**Status:** done
**Commit:** `9c04c15`

### Spec source
- `flow-4-student-onboarding.md` §3.6 (NOT_TAKEN→IN_PROGRESS→COMPLETED→RETAKEN; save/resume 7d; 30d cooldown)

### ARCH source
- `ARCHITECTURE.md` §3.16 (per-tenant), §4, §6.19

### Depends on
- T-077 (school student), T-071 (independent student)

### What this ticket builds

**Backend:** `diagnostics {id, tenant_type, student_user_id, subject_id (nullable, school), framework_id (nullable, independent), status ENUM[not_taken, in_progress, completed], questions_jsonb, answers_jsonb, started_at, completed_at, expires_at}`. Save/resume within 7 days (`expires_at`). 30-day retake cooldown enforced. Per-subject for school; per-framework for independent.

**Frontend:** None (UI in T-105).

### Acceptance (demo script)

1. [ ] Diagnostic lifecycle states enforced
2. [ ] Save + resume works within 7 days; expires after
3. [ ] 30-day retake cooldown enforced (earlier retake blocked with clear message)
4. [ ] School diagnostic scoped per-subject; independent per-framework
5. [ ] Stored in correct tenant schema

### Out of scope
- Question generation (T-104), UI (T-105), DNA seeding (T-106)

---

## T-104 — Diagnostic question generation (LLM; Question Bank hook deferred)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 2 days
**Status:** done
**Commit:** `7f55135`

### Spec source
- `flow-4-student-onboarding.md` §3.6 (15-25 questions; per-subject/per-framework calibration; Question Bank #74 where available, LLM fallback)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompt for question generation), §7 (RAG context)

### Depends on
- T-103 (diagnostic model), T-057 (curriculum topic tree, M-04), T-096 (framework content, M-07)

### What this ticket builds

**Backend:** Generate 15-25 diagnostic questions via LLM (typed prompt `diagnostic_generate_v1.py`), calibrated to: school → grade + subject (curriculum topic tree as context); independent → exam framework (framework topic priorities as context). The Question Bank (#74, Flow 9) is a documented hook: when present, prefer banked questions; until then, LLM fallback always.

### Acceptance (demo script)

1. [ ] School diagnostic generates 15-25 questions calibrated to grade + subject
2. [ ] Independent diagnostic calibrated by the framework's topic priorities
3. [ ] Question count within 15-25
4. [ ] Question Bank hook present (currently always LLM fallback)
5. [ ] Generation failure retries; clear error if it can't produce questions

### Out of scope
- Question Bank implementation (#74, Flow 9 / M-18)

### Notes / known gotchas
- BLOCKED-HOOK: Question Bank #74 (banked diagnostic questions) → Flow 9 / M-18 (LLM-generated questions for now; hook prefers banked when present)

---

## T-105 — Diagnostic taking UI + coaching results (never grades)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 2 days
**Status:** done
**Commit:** `7eaddec`

### Spec source
- `flow-4-student-onboarding.md` §3.6 (results as "areas to focus on", never grades; coaching principle)

### ARCH source
- `ARCHITECTURE.md` §13 (i18n), §6.19

### Depends on
- T-103 (model), T-104 (questions)

### What this ticket builds

**Frontend + backend:** Diagnostic-taking UI (one question at a time, progress, save/resume). On completion, results render as **focus areas** ("Spend more time on Newton's Laws") — NEVER a score/grade/percentage. Coaching tone enforced (CXO rule: coaching, never grading).

### Acceptance (demo script)

1. [ ] Student takes the diagnostic; can pause + resume (within 7 days)
2. [ ] Completion shows focus areas, NOT a grade/score/percentage
3. [ ] Coaching language only (no "you failed", no marks)
4. [ ] UI in all 4 languages (en/ur/sd/ps; RTL handled)
5. [ ] Timeout finalizes the diagnostic gracefully

### Out of scope
- DNA seeding (T-106)

### Notes / known gotchas
- HARD rule: never display a grade/score. Results are coaching-framed focus areas only.

---

## T-106 — Diagnostic → Cognitive DNA seeding + retake cooldown

**Layer:** 3
**Milestone:** M-08
**Estimate:** 1 day
**Status:** done
**Commit:** `6c7205d`

### Spec source
- `flow-4-student-onboarding.md` §3.6 (results seed Cognitive DNA; 30-day retake)

### ARCH source
- `ARCHITECTURE.md` §9 (NATS event for DNA seeding), §3.16

### Depends on
- T-102 (DNA seed model), T-103 (diagnostic), T-105 (completion)

### What this ticket builds

**Backend:** On diagnostic COMPLETED, write per-topic confidence + focus areas into `cognitive_dna` (correct tenant schema). Emit a NATS event (`student.diagnostic_completed`) for future Flow 9 consumers. Enforce 30-day retake cooldown. Independent students' DNA writes to the independent schema (separate from school DNA).

### Acceptance (demo script)

1. [ ] Completed diagnostic seeds `cognitive_dna` (topic confidence + focus areas)
2. [ ] School DNA → school schema; independent DNA → independent schema
3. [ ] NATS `student.diagnostic_completed` emitted (Flow 9 consumes later)
4. [ ] Retake within 30 days blocked; allowed after
5. [ ] Retake updates (not duplicates) the DNA seed

### Out of scope
- Flow 9 consuming the event (M-18)

### Notes / known gotchas
- BLOCKED-HOOK: `student.diagnostic_completed` event consumer → Flow 9 / M-18 (event emitted now; no consumer until Flow 9)

---

## T-107 — Exam-date approach notifications (#52 delivery)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 1 day
**Status:** done
**Commit:** `3dc456d`

### Spec source
- `flow-4-student-onboarding.md` §3.7 (exam date approach #52)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §10.6 (beat for date checks)

### Depends on
- T-083 (exam date capture, M-06), T-038 (notif infra, M-02)

### What this ticket builds

**Backend:** Celery beat checks exam dates; fires countdown notifications at 30 days out (and reuses self-study countdown hooks from Flow 8 spec where applicable). Past-date → prompt to set a new exam. Exam date drives framework weekly pacing (consumed by M-07 framework + future Flow 8 plans).

### Acceptance (demo script)

1. [ ] 30-day approach fires a countdown notification
2. [ ] Past date → "set a new exam date" prompt
3. [ ] >5-year future date allowed with a warning (per §3.7)
4. [ ] Notification templates in 4 languages

### Out of scope
- Full self-study reminder cadence (Flow 8, M-17)

---

## T-108 — Mode-conditional dashboard polish + per-session adaptation hook

**Layer:** 3
**Milestone:** M-08
**Estimate:** 1 day
**Status:** done
**Commit:** 5a96d43

### Spec source
- `flow-4-student-onboarding.md` §3.4 (dashboard mode-conditional; AI personalization adapts per Flow 6 #61)

### ARCH source
- `ARCHITECTURE.md` §6.19, §8 (LLM personalization context)

### Depends on
- T-101 (mode switcher), T-106 (DNA seed exists to personalize from)

### What this ticket builds

**Frontend + backend:** Polish the mode-conditional dashboard (correct sections per mode). Expose a per-session adaptation HOOK: the AI personalization context can read the Cognitive DNA seed (focus areas) — the FULL per-session adaptation (#61) lives in Flow 6 (M-09+); this ticket only wires the read-hook so future surfaces can consume the seed.

### Acceptance (demo script)

1. [ ] Dashboard shows correct sections per mode (Lecture vs Self-Study)
2. [ ] Cognitive DNA focus areas are readable by the personalization context (hook)
3. [ ] Hook is documented for Flow 6 / Flow 8 consumption (no full adaptation here)
4. [ ] Independent dashboard shows Self-Study layout only

### Out of scope
- Full per-session adaptation #61 (Flow 6, M-09+)
- Self-study planning (Flow 8, M-17)

---

## T-109 — Notifications (`account` / diagnostic events)

**Layer:** 3
**Milestone:** M-08
**Estimate:** 1 day
**Status:** done
**Commit:** `caefb7a`

### Spec source
- `flow-4-student-onboarding.md` §3.6, §3.7 (diagnostic + exam events)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS)

### Depends on
- T-106 (diagnostic events), T-038 (notif infra, M-02)

### What this ticket builds

**Backend:** Notifications: diagnostic available (after onboarding), diagnostic completed (focus-areas summary), retake-available (after 30 days). NATS events for mode + diagnostic transitions. Templates in 4 languages. (Exam-date countdown handled in T-107.)

### Acceptance (demo script)

1. [ ] Diagnostic-available + completed + retake-available notifications deliver
2. [ ] Completion notification shows focus areas (coaching), not a grade
3. [ ] NATS events published
4. [ ] Templates in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Self-study reminders (Flow 8, M-17)

---

## T-110 — Audit logging

**Layer:** 3 / 6
**Milestone:** M-08
**Estimate:** 0.5 day
**Status:** done
**Commit:** `4c07b0e`

### Spec source
- `flow-4-student-onboarding.md` §3.4, §3.6

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log)

### Depends on
- T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Register audit action types: mode switch (optional / low-noise), diagnostic started/completed/retaken, DNA seed written. Diagnostic + DNA actions are the meaningful ones. Surface in the audit page.

### Acceptance (demo script)

1. [ ] Diagnostic + DNA actions write audit entries
2. [ ] Audit page shows M-08 actions, scope-restricted
3. [ ] Mode switches logged at low verbosity (or aggregated) to avoid noise

### Out of scope
- Audit export (Phase 2)

---

## T-111 — E2E smoke test

**Layer:** 6
**Milestone:** M-08
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.4, §3.6, §3.7

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-101 through T-110

### What this ticket builds

**Test harness:** Automated E2E: school student toggles modes (no data loss) + independent 404 on switch; school student takes per-subject diagnostic (LLM questions mocked/sandboxed), saves+resumes, completes → DNA seeded in school schema; independent takes per-framework diagnostic → DNA in independent schema; retake within 30 days blocked; exam-date 30-day countdown fires (time-warped). Runs in CI.

### Acceptance (demo script)

1. [ ] E2E runs green end-to-end
2. [ ] Mode toggle + independent 404 asserted
3. [ ] Diagnostic lifecycle + save/resume + 30-day cooldown asserted
4. [ ] DNA seeded in correct schema per tenant asserted
5. [ ] Results never expose a grade (coaching-only) asserted

### Out of scope
- Frontend Playwright E2E (Phase 2)

### Notes / known gotchas
- Mock LLM question generation in CI (no live network).

---

## T-112 — Milestone M-08 PR + demo

**Layer:** 6
**Milestone:** M-08
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` v3 §3.4, §3.6, §3.7

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-101 through T-111

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-08 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-08` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-111 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-08 ticket set

---

## Milestone notes

- **⚠ Cognitive DNA is SEED-ONLY here.** The full intelligence engine (mistake tracking, pass probability, spaced repetition, forgetting curve, Question Bank #74) is **Flow 9 / M-18**, which is **blocked (Flow 9 not yet drafted)**. M-08 builds a minimal `cognitive_dna` store the diagnostic initializes. **Soft dependency:** when Flow 9 is drafted, the DNA schema will be extended — a follow-up migration may be needed. Tracked in TODO. Do not over-build the DNA engine here.
- BLOCKED-HOOK: full Cognitive DNA engine + cognitive_dna schema extension → Flow 9 / M-18 (built as a minimal diagnostic-seeded store for now)
- BLOCKED-HOOK: Question Bank #74 (banked diagnostic questions) → Flow 9 / M-18 (LLM-generated for now)
- BLOCKED-HOOK: `student.diagnostic_completed` event consumer → Flow 9 / M-18 (emitted now; no consumer yet)
- **Diagnostic questions are LLM-generated** at launch; the Question Bank (#74) is a deferred hook (Flow 9).
- **Coaching, never grading** — diagnostic results are focus areas only; no grade/score/percentage anywhere. This is a hard CXO rule (T-105).
- **Mode Switcher** is fully built here; M-06 only shipped the minimal onboarding mode pick.
- **Per-session adaptation (#61)** is a read-hook only here; the full adaptation is Flow 6 (M-09+).
- **Exam-date capture** shipped in M-06 (T-083); M-08 delivers the countdown notifications (T-107).
- **Source flow:** Flow 4 v3 §3.4/§3.6/§3.7 — finalized. The Cognitive DNA reference (#83) points at Flow 9, which is not drafted; M-08 stays within the minimal seed that Flow 4 §3.6 specifies.
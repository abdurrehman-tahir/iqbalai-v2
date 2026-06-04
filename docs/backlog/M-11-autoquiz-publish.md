# M-11 — Auto-quiz Per Student + Publish Lecture

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2 weeks
**Tickets:** T-141 through T-150
**Spec source:** `flow-5-teacher-creates-lecture.md` v1 §3.3 (auto-quiz per student #23b), §3.1 + §3.5 (publish lifecycle → PUBLISHED)

## Goal

Completes Flow 5: the teacher publishes the lecture (it becomes visible to the enrolled students of its Grade-Subject), and **each enrolled student automatically gets a quiz calibrated to their own level** — stronger students get harder questions, weaker students get more foundational ones on the same topics. Quizzes generate in parallel (one Celery task per student), publish alongside the lecture, appear on each student's dashboard, are attempted and scored, and results roll up to teacher / coordinator / admin per the permission inheritance rules. Students who enroll *after* publish get their quiz generated automatically. Independent teachers get no auto-quiz.

**Scope boundary:** publish + auto-quiz (generate → calibrate → publish → attempt → results). Lecture *consumption* (the viewer, highlighting, in-lecture Q&A, voice) is Flow 6 / M-12 — not here. Cross-grade linking + per-lecture access already shipped in M-09 (T-122/T-123); edit + scoring + benchmarking shipped in M-10.

**⚠ Soft dependency / calibration caution:** Flow 5 §3.3 says per-student quiz calibration uses **Cognitive DNA (Flow 9 #83)** + diagnostic results (Flow 4 §3.6). The **full Cognitive DNA engine is Flow 9 / M-18, which is BLOCKED (Flow 9 not drafted).** M-11 therefore calibrates off the **M-08 diagnostic seed** (`cognitive_dna` focus-areas + topic-confidence — which IS available) and exposes a documented hook for richer DNA-based calibration when M-18 ships. Quizzes are fully functional at launch on the seed; calibration just gets richer later.

**Demo at milestone end:**
- Teacher publishes an edited lecture → it becomes visible to the enrolled students of that Grade-Subject
- On publish, each enrolled student already has a quiz (generated in parallel when the lecture was created)
- A stronger student's quiz has harder/applied questions; a weaker student's covers the same topics more foundationally
- Quizzes appear on each student's dashboard as pending; a student attempts one and sees immediate results
- The teacher sees per-student + aggregate results; a Coordinator sees aggregate-in-scope; a School Admin sees aggregate-for-school
- A student who enrolls the next day automatically gets their quiz generated (no teacher action)
- An independent teacher publishes a lecture-plan → no auto-quiz is generated

---

## T-141 — Quiz data model

**Layer:** 4
**Milestone:** M-11
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (quiz_assignments per student; status lifecycle)

### ARCH source
- `ARCHITECTURE.md` §4 (DB; `quiz definitions`), §4.18 (versioning where required), §3.16 (per-tenant)

### Depends on
- T-113 (lectures, M-09), T-077 (student enrollment, M-06)

### What this ticket builds

**Backend:** Migrations (school schema; independent schema gets the tables but auto-quiz never populates them) for: `quizzes {id, lecture_id, lecture_version_id, status, created_at}`; `quiz_questions {id, quiz_id, ordinal, stem, options_jsonb, correct_answer, difficulty, source_metadata_jsonb}` (source attribution per §4106); `quiz_assignments {id, quiz_id, student_user_id, status ENUM[pending, published, attempted, completed], calibration_jsonb, assigned_at}` (one per enrolled student); `quiz_attempts {id, quiz_assignment_id, answers_jsonb, score, max_score, attempted_at}`. Quiz questions carry per-question source attribution (which lecture content the question is based on).

**Frontend:** None.

### Acceptance (demo script)

1. [ ] All quiz tables exist with constraints; `quiz_assignments` is per-student
2. [ ] `quiz_assignments.status` enum covers pending → published → attempted → completed
3. [ ] `quiz_questions` carry `difficulty` + per-question `source_metadata_jsonb`
4. [ ] `calibration_jsonb` records what the per-student calibration was based on (seed inputs)
5. [ ] Tables exist in both schemas; independent schema rows never auto-populated

### Out of scope
- Generation/calibration logic (T-143/T-144)

---

## T-142 — Lecture publish lifecycle

**Layer:** 4
**Milestone:** M-11
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5 (PUBLISHED — visible to enrolled students per Grade-Subject), §3.1 (READY_FOR_PUBLISH)

### ARCH source
- `ARCHITECTURE.md` §5 (API), §3.18 (Grade-Subject enrollment → student roster), §6.19 (who can publish)

### Depends on
- T-130 (edit lifecycle reaches READY_FOR_PUBLISH, M-10), T-123 (per-lecture access, M-09)

### What this ticket builds

**Backend + frontend:** Publish action — a lecture at READY_FOR_PUBLISH (or READY_FOR_EDIT, publish-as-is) transitions to PUBLISHED and becomes visible to the enrolled students of its Grade-Subject offering (respecting the per-lecture access set in T-123). Publishing a lecture also triggers quiz publication (T-145). Emits NATS `lecture.published`. Teacher owns publish for their offering; Admin override-publish per §6.19 (audit-logged).

### Acceptance (demo script)

1. [ ] Teacher publishes → lecture PUBLISHED, visible to enrolled students of the Grade-Subject
2. [ ] Per-lecture access restrictions (T-123) honored on publish
3. [ ] `lecture.published` emitted
4. [ ] Admin override-publish works + is audit-logged (§6.19)
5. [ ] Re-publishing an edited version updates what students see (latest published version)

### Out of scope
- Student lecture viewer/consumption (Flow 6 / M-12)

---

## T-143 — Auto-quiz generation per student (parallel pipeline) (#23b)

**Layer:** 4
**Milestone:** M-11
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (QUIZ_GEN_REQUESTED → per-student parallel → QUIZ_READY; 5-10 Q; 2-min class SLA)

### ARCH source
- `ARCHITECTURE.md` §7 (Pattern S quiz generation — bounded corpus, structured output), §8.6 (typed prompt), §10 (Celery `quiz_gen` queue), §4106 (quiz source attribution required), §9 (NATS)

### Depends on
- T-141 (quiz model), T-116 (lecture generation triggers quiz gen, M-09), T-077 (enrolled roster, M-06)

### What this ticket builds

**Backend:** When a lecture is generated (Flow 5 §3.1: "auto-quiz generation kicks off in parallel"), enqueue one Celery task per enrolled student on the `quiz_gen` queue. Each task generates 5-10 questions on the lecture topic via the Pattern-S quiz prompt (varied difficulty per student — calibration in T-144), with per-question source attribution. Creates `quiz_assignments` rows (status=pending). SLA = 2 minutes for a full class (e.g. 30 students → 30 parallel tasks, ~30-60s each). QUIZ_GEN_REQUESTED → QUIZ_GENERATING_PER_STUDENT → QUIZ_READY.

### Acceptance (demo script)

1. [ ] Lecture generation enqueues one quiz task per enrolled student (parallel)
2. [ ] Each student gets 5-10 questions on the lecture topic
3. [ ] Each question carries source attribution to lecture content
4. [ ] `quiz_assignments` rows created (status=pending) per student
5. [ ] Full-class generation completes within the 2-minute SLA (parallel, not serial)
6. [ ] Quizzes are NOT yet visible to students (pending until publish)

### Out of scope
- Calibration internals (T-144), publish surfacing (T-145)

---

## T-144 — Per-student calibration (diagnostic-seed-based; DNA hook for M-18)

**Layer:** 4
**Milestone:** M-11
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (per-student calibration; stronger→harder, weaker→foundational)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompt with calibration context), `flow-4-student-onboarding.md` §3.6 (diagnostic seed)

### Depends on
- T-143 (generation pipeline), T-106 (diagnostic → `cognitive_dna` seed, M-08)

### What this ticket builds

**Backend:** Calibration layer for T-143's generation. For each student, read their `cognitive_dna` **diagnostic seed** (focus areas + topic confidence from M-08) and shape the quiz: stronger students (high topic confidence) → harder, conceptual + applied questions; weaker students (focus-area topics) → more foundational questions on the same topics. Record what calibration was based on in `quiz_assignments.calibration_jsonb`. **Hook (not implemented):** when the full Cognitive DNA engine ships (Flow 9 / M-18 — mastery map, mistake history, pass probability), calibration reads from it for richer signal; until then, the diagnostic seed is the sole input. If a student has no diagnostic seed yet, fall back to grade-level default difficulty.

### Acceptance (demo script)

1. [ ] Calibration reads the M-08 diagnostic seed per student
2. [ ] Stronger students get harder/applied questions; weaker get foundational on same topics
3. [ ] `calibration_jsonb` records the seed inputs used
4. [ ] No diagnostic seed → grade-level default difficulty (no crash)
5. [ ] Cognitive DNA hook is documented + stubbed for Flow 9 / M-18 (not implemented now)

### Out of scope
- Full Cognitive DNA mastery-map calibration (Flow 9 / M-18, BLOCKED)

### Notes / known gotchas
- Soft dependency on Flow 9. Build against the M-08 seed only; do NOT attempt to build the DNA mastery map here. When M-18 lands, this calibration input is swapped/enriched — keep the calibration input behind a clear interface.
- BLOCKED-HOOK: full Cognitive DNA calibration → Flow 9 / M-18 (built against M-08 diagnostic seed for now)

---

## T-145 — Quiz publish + student dashboard surface

**Layer:** 4
**Milestone:** M-11
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (QUIZ_PUBLISHED — students see quiz on dashboard)

### ARCH source
- `ARCHITECTURE.md` §5 (API), §12 (frontend), §6.19 (student sees own)

### Depends on
- T-142 (lecture publish), T-143 (quizzes READY)

### What this ticket builds

**Backend + frontend:** When the lecture is published (T-142), its `quiz_assignments` flip pending → published and each student sees their pending quiz on their dashboard (status, lecture/topic, question count). Students see ONLY their own quiz. Quiz publication is bound to lecture publication (no separate publish step).

### Acceptance (demo script)

1. [ ] Lecture publish flips that lecture's quiz_assignments → published
2. [ ] Each student sees their own pending quiz on their dashboard
3. [ ] A student never sees another student's quiz
4. [ ] Unpublished lectures' quizzes are not visible to anyone
5. [ ] Dashboard shows topic + question count + status

### Out of scope
- Attempt/scoring (T-146)

---

## T-146 — Quiz attempt + scoring + immediate student results

**Layer:** 4
**Milestone:** M-11
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (results visible to student immediately after attempt)

### ARCH source
- `ARCHITECTURE.md` §5 (API), §2723 (idempotent quiz submission), §9 (NATS `student.quiz.completed`)

### Depends on
- T-145 (published quizzes)

### What this ticket builds

**Frontend + backend:** Student takes the quiz (one question at a time or single page), submits (idempotent per §2723), gets scored against `correct_answer`, sees immediate results — score + per-question correct/incorrect + the source content for review. Creates a `quiz_attempts` row; flips assignment → completed; emits `student.quiz.completed`. Results framed supportively (highlight what to review), but the quiz itself is a real assessment with correct answers (this is distinct from the coaching-not-grading rule, which governs AI evaluation of teachers + diagnostics).

### Acceptance (demo script)

1. [ ] Student attempts + submits; submission is idempotent (no double-scoring)
2. [ ] Scored against correct answers; immediate results shown
3. [ ] Per-question correct/incorrect + source content for review
4. [ ] `quiz_attempts` row created; assignment → completed; `student.quiz.completed` emitted
5. [ ] Results presentation is supportive (review-oriented), not punitive

### Out of scope
- Mistake tracking / spaced repetition off quiz results (Flow 9 / M-18)

---

## T-147 — Quiz results visibility + aggregates (§6.19)

**Layer:** 4
**Milestone:** M-11
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (results visibility: student / teacher per-student+aggregate / coordinator aggregate-scope / admin aggregate-school)

### ARCH source
- `ARCHITECTURE.md` §6.19 (permission inheritance), §5 (API)

### Depends on
- T-146 (attempts exist)

### What this ticket builds

**Backend + frontend:** Results surfaces per §6.19 — student sees their own; teacher sees per-student + class aggregate for their offering; Coordinator sees aggregate within scope (no individual unless their inheritance grants it); School Admin sees aggregate within school; District/Platform inherit. Aggregates: completion rate, average score, per-question difficulty hot-spots.

### Acceptance (demo script)

1. [ ] Student sees only own results
2. [ ] Teacher sees per-student + class aggregate (own offering)
3. [ ] Coordinator sees aggregate within scope per §6.19
4. [ ] School Admin sees aggregate within school; higher tiers inherit
5. [ ] Aggregates: completion rate + average + per-question hot-spots

### Out of scope
- Cross-lecture longitudinal analytics (Phase 2)

---

## T-148 — Late-enrollment quiz generation + independent exclusion

**Layer:** 4
**Milestone:** M-11
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (per enrolled student — including those who enroll after publish), §3.10 + line 121 (independent teachers: NO auto-quiz)

### ARCH source
- `ARCHITECTURE.md` §10 (NATS-event-triggered task `quiz.generate_for_late_enrollment`, listens for `student.enrolled`; NOT in beat schedule), §3.16 (independent exclusion)

### Depends on
- T-143 (generation pipeline), T-144 (calibration), T-077 (enrollment emits `student.enrolled`, M-06)

### What this ticket builds

**Backend:** A `student.enrolled`-triggered task (`quiz.generate_for_late_enrollment`, NATS-event-driven, not beat) that, when a student enrolls into a Grade-Subject after lectures are already published, generates their calibrated quizzes for the already-published lectures and assigns them. Independent-tenant guard: auto-quiz is never generated for independent teachers (their published lecture-plans skip the whole quiz pipeline).

### Acceptance (demo script)

1. [ ] Student enrolling after publish → `student.enrolled` triggers quiz generation for published lectures
2. [ ] Late quizzes are calibrated (T-144) and assigned the same way
3. [ ] Triggered by event, not on a schedule
4. [ ] Independent teachers: no auto-quiz at any point (pipeline skipped)
5. [ ] No duplicate quizzes if the student already has one for a lecture

### Out of scope
- Bulk back-fill for historical lectures beyond the enrollment scope (Phase 2)

---

## T-149 — Notifications + audit

**Layer:** 4 / 6
**Milestone:** M-11
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3 (quiz events)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS), §14.10 (audit)

### Depends on
- T-142, T-145, T-146 (events), T-038 (notif infra, M-02), T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Notifications — lecture published (enrolled students + their parents per Flow 10 read-only), quiz available (student), quiz results ready (teacher aggregate). Audit — publish + admin override-publish, quiz generation failures, results access/export. Templates in 4 languages.

### Acceptance (demo script)

1. [ ] Publish notifies enrolled students (+ parents read-only per Flow 10)
2. [ ] Quiz-available notifies students; results-ready notifies teacher
3. [ ] Audit: publish/override-publish, quiz-gen failures, results access
4. [ ] NATS events published per transition
5. [ ] Templates in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Student quiz reminders cadence (Phase 2)

---

## T-150 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-11
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.3, §3.5

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` §1.8 + §2.x

### Depends on
- T-141 through T-149

### What this ticket builds

**Test + PR:** Automated E2E — generate lecture (LLM mocked) → per-student parallel quiz gen (calibrated off seeded diagnostics for 2 students of different levels) → publish lecture → quizzes appear on both students' dashboards → both attempt (idempotency asserted) → results visible to student + teacher aggregate + admin aggregate (scope asserted) → late-enrollment student gets a quiz via `student.enrolled` → independent teacher publish produces NO quiz. Then the single milestone PR per `WORKFLOW.md` Step 2 (description, `phase-complete-review`, demo for Abd. + Awais, merge to `staging`).

### Acceptance (demo script)

1. [ ] E2E runs green (LLM mocked; no live network)
2. [ ] Per-student calibration difference asserted (strong vs weak)
3. [ ] Publish → quiz visibility + attempt + idempotency asserted
4. [ ] §6.19 results scope + late-enrollment + independent-no-quiz asserted
5. [ ] PR `milestone/M-11` → `staging`; `phase-complete-review` passes; CI green; demo clean; merged

### Out of scope
- Anything beyond the M-11 ticket set

---

## Milestone notes

- **Completes Flow 5.** Publish + auto-quiz close the teacher lecture arc; lecture *consumption* (viewer/highlight/Q&A/voice) is Flow 6 / M-12.
- **⚠ Calibration soft-dependency on Flow 9.** Full Cognitive DNA is M-18 (BLOCKED). M-11 calibrates off the **M-08 diagnostic seed** with a clean interface so DNA enrichment swaps in when M-18 ships. Do not build the DNA mastery map here. No-seed students fall back to grade-level default.
- **Quiz generation is per-student-parallel** on the `quiz_gen` queue (Pattern S, §7); 2-minute class SLA; never serial.
- **Quiz publication is bound to lecture publication** — no separate publish step; quizzes flip published when the lecture does.
- **Late enrollment is event-driven** (`quiz.generate_for_late_enrollment` on `student.enrolled`), NOT a beat job.
- **Independent teachers get no auto-quiz** — the whole pipeline is school-tenant; independent quiz tooling is deferred to Flow 8 (generic quiz tooling).
- **Quizzes are real assessments** (correct answers, scores) — this is distinct from the coaching-not-grading rule, which governs AI evaluation of *teachers* (Innovation Record) and *diagnostics*; quiz results are still presented supportively/review-oriented.
- **Closers:** notifications+audit (T-149) and E2E+PR (T-150) split across two tickets to fit the 10-ticket cap.
- **Source flow:** Flow 5 v1 §3.3 + §3.1/§3.5 — finalized; the only open item is the Flow 9 calibration enrichment (tracked, non-blocking).

# M-17 — Student Self-Study Mode

**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-209 through T-222
**Spec source:** `flow-8-self-study.md` v1 §3.1-§3.13, features #62, #63, #64, #65, #66, #67, #68, #69, #70, #72

## Goal

Self-study mode — the student-driven study loop, and the **primary surface for independent-tenant students** (who are locked to it per Flow 4 v3 §3.2). A student sets a daily goal, uploads their own materials (PDF / camera / gallery / typed), categorises books, and the system extracts topics from their prep book, builds a conversational study plan, renders it on a built-in calendar with reminders, and tracks adherence. Self-study sessions **reuse the Flow 6 components** (hybrid widget, live panel, adaptation, NATS pipeline) — they are not re-implemented here. Flow 8 is also the **canonical owner of the #72 privacy setting**.

**This milestone consumes hooks from earlier flows** (pre-draft audit): M-14's daily-goal metric (#69 built here), M-08's adaptation hook (Flow 8 session side), and M-15's `flashcard.created` (Flow 8 *surfaces* due cards). Independent students were routed here from Flow 4.

**Scope boundary — what Flow 8 does NOT own (corrected against the spec):**
- **Spaced-repetition *scheduling* (py-fsrs) + the question queue #76 are Flow 9 / M-18**, not here. Flow 8 surfaces "due flashcards" but does **not** compute the schedule. (This corrects M-15's note that called the py-fsrs deck an M-17 build.)
- **Cognitive DNA, mistake tracking, pass probability** are Flow 9 — Flow 8 only *emits signals* (goal achievement, adherence) for Flow 9 to consume.
- **Subscription tier caps** (active plans / monthly uploads) are Flow 13 / M-23 — present here as a no-op placeholder (schema hooks, limits unset).

**Stack note (resolves the flagged Google-Calendar item):** the primary calendar is our own **FullCalendar** (STACK_LOCK §2, MIT core); `.ics` export is always available (provider-neutral, no external dependency); "Add to Google Calendar" is an **env-gated user-OAuth integration** (`GOOGLE_CALENDAR_SYNC_ENABLED`) that hides + degrades to `.ics` when unconfigured — an integration, not a GCP managed-service dependency (STACK_LOCK forbids GCP managed services but the built-in calendar is primary). Reminders use the locked FCM / Brevo / Jazz+Telenor channels (NOT SendGrid/Twilio), all degrading silently without env vars.

**Demo at milestone end:**
- Independent student opens straight into self-study (no mode toggle); school student toggles in (#53, Flow 4) and resumes where they left off
- Student sets a free-text daily goal (voice or text) → it steers the session AI and shows on the live panel
- Student uploads a prep book (PDF or camera→PaddleOCR) and a reference book; categorises each; study-plan generation is hard-blocked until a prep book exists
- Topics extracted from the prep book (weighted by frequency) → AI asks 5 conversational questions → builds a study plan; "Make Mondays lighter" regenerates only the affected items
- Plan renders on the built-in calendar (granularity auto-set by exam distance); student exports `.ics`; reminders fire 30 min before sessions
- Nightly adherence check: 2 consecutive misses alerts the student (and parent, when Flow 10 ships); adherence % is emitted for Flow 9
- Setting #72 to "No" makes that school student's self-study questions invisible to every teacher-facing surface (inviolate)

---

## T-209 — Self-study data model + entering-mode + state persistence

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.1 (entering mode; independent redirect; state persistence; subscription no-op placeholder), §10 (data model sketch)

### ARCH source
- `ARCHITECTURE.md` §3.16 (dual-schema; both tenants), §4 (DB), §4.12 (migrations)

### Depends on
- T-067-range (Flow 4 mode-state #53), T-001-range (tenant schemas, M-00)

### What this ticket builds

**Backend:** Migrations (BOTH `school` and `independent` schemas, tenant-routed) for: `student_materials`, `student_goals`, `prep_book_topics`, `study_plans`, `study_plan_items`, `study_plan_days`, `student_self_study_privacy` (or column on `user_settings`), `reminder_preferences` — per the §10 sketch. Entering-mode behaviour: school students consume Flow 4's `mode=self_study` state and resume their last self-study view; **independent students render no mode switcher and any Lecture-Mode route redirects to self-study home**. State persistence (last goal/material/plan view) per `user_settings`. The subscription gate is a **no-op placeholder** (schema hooks present, limits unset → Flow 13 / M-23).

### Acceptance (demo script)

1. [ ] All §10 tables exist in both schemas, tenant-routed
2. [ ] Independent students open directly into self-study; Lecture-Mode routes redirect
3. [ ] School students resume last self-study state; mode-state preserved across toggles
4. [ ] State persistence per `user_settings`
5. [ ] Subscription gate present but no-op (limits unset)

### Out of scope
- Subscription enforcement (Flow 13 / M-23)

---

## T-210 — Self-study session interaction (reuse Flow 6) + due-flashcards surface

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.11 (reuses Flow 6 widget #57 / panel #59 / adaptation #61 / pipeline #60; tenant-tagged `mode=self_study`; RAG Pattern P + overlays), §3.8-ref / Q10 (surfaces "due flashcards"; scheduling is Flow 9)

### ARCH source
- `ARCHITECTURE.md` §7 (RAG Pattern P personal pool, §7.21 cross-grade overlay), §9 (event emission, `mode=self_study` tag)

### Depends on
- T-155 (hybrid widget, M-12), T-177/T-182 (panel + adaptation, M-14), T-209 (materials/pool)

### What this ticket builds

**Backend + frontend:** The self-study session — **reusing the exact Flow 6 components** (no re-implementation): hybrid widget #57, live panel #59, per-session adaptation #61, NATS pipeline #60. Events carry `tenant_type` + `mode=self_study` (school events with #72=share reach Flow 7; independent events never reach a teacher surface). RAG retrieval = **Pattern P (personal pool)** primary; school students add the §7.21 cross-grade curriculum overlay; independent students add an exam-syllabus overlay if selected, else AI knowledge. Surfaces **"due flashcards"** as a read-only deck view — the **scheduling is not computed here** (Flow 9).

### Acceptance (demo script)

1. [ ] Session reuses Flow 6 widget/panel/adaptation/pipeline (no duplicate impl)
2. [ ] Events tagged `mode=self_study` + tenant_type; independent events never reach Flow 7
3. [ ] RAG uses Pattern P + correct per-tenant overlay
4. [ ] "Due flashcards" surfaced read-only (no schedule computed here)
5. [ ] Both tenants share the session UI

### Out of scope
- py-fsrs scheduling (BLOCKED-HOOK below); goal injection (T-211)

### Notes / known gotchas
- BLOCKED-HOOK: spaced-repetition scheduling (py-fsrs) + question queue #76 that compute which flashcards are "due" → Flow 9 / M-18 (Flow 8 surfaces the deck; Flow 9 owns the schedule; consumes M-15's `flashcard.created`).

---

## T-211 — Daily goal (#69)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.2 (free-text via #57; injected into session AI context; live panel displays; one/day editable; end-of-session check; feeds Cognitive DNA)

### ARCH source
- `ARCHITECTURE.md` §8.6 (`self_study_session_v1` prompt — goal injection), §9 (goal event)

### Depends on
- T-210 (session context + panel), T-209 (`student_goals`)

### What this ticket builds

**Backend + frontend:** Daily goal — free-text in the student's own words via the hybrid widget #57 (text/voice; no dropdown/template), stored in `student_goals` (one per day, editable until EOD, replace-with-confirm if reset). The goal is **injected as context** into the session AI system prompt (the AI steers toward it) and **displayed on the live panel #59** (the M-14 daily-goal metric hook lands here). End-of-session check ("Did you achieve your goal?") fires once/day on leaving a >5-min session (skippable). A goal-achievement event is emitted.

### Acceptance (demo script)

1. [ ] Goal is free-text via #57 (text or voice); one per day, editable until EOD
2. [ ] Goal injected into the session AI prompt; AI references it
3. [ ] Live panel #59 displays the active goal (M-14 metric satisfied)
4. [ ] End-of-session check fires once/day on >5-min sessions; skippable
5. [ ] Goal event emitted

### Out of scope
- Cognitive DNA consumption of the goal signal (BLOCKED-HOOK below)

### Notes / known gotchas
- BLOCKED-HOOK: daily-goal achievement signal → Cognitive DNA, Flow 9 / M-18 (Flow 8 emits the event; Flow 9 consumes as a self-awareness / goal-pattern signal).

---

## T-212 — Material upload — 4 types (#62)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.3 (PDF / camera / gallery / typed; PaddleOCR; `student_material` + `student_question_image` profiles; Instant Answer vs Add-to-Library; private personal pool; MinIO per tenant+user)

### ARCH source
- `ARCHITECTURE.md` §7.3 (PaddleOCR, Tesseract fallback), §11.19 (upload profiles), §8.22 (vision for question images), §7 (Pattern P pool), §14 (MinIO retention)

### Depends on
- T-209 (`student_materials`), T-168 (vision routing, M-13)

### What this ticket builds

**Backend + frontend:** Four input methods — PDF upload, device camera, gallery picker, typed query (typed path uses widget #57). OCR via **PaddleOCR** (multilingual incl. Urdu; Tesseract 5 fallback) — **not Google Vision**. Image profiles: `student_material` (full-page doc photos), `student_question_image` (§11.19: max 3, 5 MB each, EXIF-stripped, routed to vision-LLM §8.22). Post-upload choice: **Instant Answer** (ephemeral one-shot RAG, not persisted, still emits an event) vs **Add to Study Library** (persisted to the private Student Personal Pool → triggers categorisation #63). Storage MinIO scoped per tenant + per user; pool is private to the student (not teacher/coordinator/peers).

### Acceptance (demo script)

1. [ ] All four input methods work; OCR via PaddleOCR (Tesseract fallback)
2. [ ] Image profiles enforced (§11.19: 3×5MB, EXIF stripped)
3. [ ] Instant Answer is ephemeral (not persisted); Add-to-Library persists to private pool
4. [ ] Personal pool visible only to the owning student
5. [ ] MinIO storage scoped per tenant + user

### Out of scope
- Book categorisation (T-213); vision-LLM internals (M-13)

---

## T-213 — Book categorisation + prep-book gate (#63)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.4 (`book_type` ENUM; HARD BLOCK plan-gen without a prep book; exact error; re-categorisation re-triggers gate)

### ARCH source
- `ARCHITECTURE.md` §4 (`student_materials.book_type`)

### Depends on
- T-212 (library add)

### What this ticket builds

**Backend + frontend:** On Add-to-Library, categorise each book: `book_type ENUM[prep_questions, reference_content]`. **Hard validation:** study-plan generation (#65) is BLOCKED unless the student has ≥1 `prep_questions` book — exact error "Please upload a prep question book to generate a study plan." (a blocker, not a soft warning). Re-categorisation is allowed; changing the last prep book to reference re-triggers the gate.

### Acceptance (demo script)

1. [ ] Each library book categorised (prep_questions / reference_content)
2. [ ] Plan-gen hard-blocked without a prep book, exact error message
3. [ ] Re-categorisation allowed
4. [ ] Removing the last prep book re-triggers the gate
5. [ ] Both tenants identical

### Out of scope
- Topic extraction (T-214)

---

## T-214 — Question-to-topic extraction (#64)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.5 (Celery `self_study.extract_topics` on prep-book add; LLM batch classify; weighted topic list; $0.25/book, 500q cap; school curriculum mapping)

### ARCH source
- `ARCHITECTURE.md` §10 (`self_study.extract_topics` `@tenant_task`), §8.6 (`question_topic_extract_v1`), §3.19 (Exam Framework syllabus mapping), §4 (`prep_book_topics`)

### Depends on
- T-213 (prep book), T-209 (`prep_book_topics`)

### What this ticket builds

**Backend:** A background Celery task `self_study.extract_topics` (`@tenant_task`) on prep-book add (non-blocking). Parse questions, LLM batch-classify each into a curriculum topic (mapped to the student's exam syllabus via §3.19 where available; free-text topic for independents without a syllabus). Output a **weighted topic list** (`weight = question_count_for_topic / total_questions`) cached for plan generation. Failures → build from what parsed + banner. **Cost ceiling $0.25/book; cap 500 questions** (overflow flagged).

### Acceptance (demo script)

1. [ ] Extraction runs as a non-blocking Celery task on prep-book add
2. [ ] Questions classified to topics (syllabus-mapped for school / exam-syllabus students; free-text otherwise)
3. [ ] Weighted topic list produced (frequency weighting)
4. [ ] Cost ≤ $0.25/book; 500-question cap with overflow flagged
5. [ ] Partial-parse degrades with a banner

### Out of scope
- Plan generation (T-215)

---

## T-215 — Conversational study plan creation (#65)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.6 (AI 5-question chat via #57; pre-fill; weighted list → `study_plans` + `study_plan_items`; NL refinement; one active plan/exam; $0.50 gen / $0.10 refine; retry 3)

### ARCH source
- `ARCHITECTURE.md` §8.6 (plan-creation typed prompt), §4 (`study_plans`, `study_plan_items`), Flow 4 #52 (exam date pre-fill)

### Depends on
- T-214 (weighted topics), T-213 (gate passed)

### What this ticket builds

**Backend + frontend:** Conversational plan creation — **AI chat, not a form** — via widget #57: 5 guided questions one at a time (exam, date, books, daily hours, strong topics), pre-filling known values (exam date from Flow 4 #52, books from library). Generates `study_plans` + `study_plan_items` from the weighted topic list + answers. **Natural-language refinement** ("Make Mondays lighter") regenerates only affected items. **One active plan per student per exam** at launch (two exams → two plans, subscription-gated later; switching exams archives the prior). Cost ceiling $0.50/generation, $0.10/refinement; 3 retries then a graceful failure preserving the student's answers.

### Acceptance (demo script)

1. [ ] AI asks the 5 questions conversationally (not a form), pre-filling known values
2. [ ] Plan + items generated from weighted topics + answers
3. [ ] NL refinement regenerates only affected items
4. [ ] One active plan per exam; switching exams archives the prior
5. [ ] Cost ceilings enforced; failure preserves answers

### Out of scope
- Granularity logic (T-216); calendar render (T-217)

---

## T-216 — Study plan granularity (#66)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.7 (auto granularity by duration: ≤14d day / 15-90d 3-day / >90d weekly; nightly auto-refine)

### ARCH source
- `ARCHITECTURE.md` §10 (`self_study.refine_granularity` beat), §4 (`study_plan_items.granularity`)

### Depends on
- T-215 (plan + items)

### What this ticket builds

**Backend:** Auto-select granularity by plan duration (exam_date − today), no user choice at launch: ≤14 days → `day`, 15-90 days → `3day`, >90 days → `week` (daily detail rendered only for the current week). A nightly Celery task `self_study.refine_granularity` auto-refines as the exam approaches (a >90-day plan crossing the 90-day threshold regenerates the now-current portion into 3-day blocks).

### Acceptance (demo script)

1. [ ] Granularity auto-set by duration (day / 3day / week)
2. [ ] >90-day plan shows daily detail only for the current week
3. [ ] Nightly refine regenerates the now-current portion at finer granularity
4. [ ] `study_plan_items.granularity` reflects the band
5. [ ] Both tenants identical

### Out of scope
- Calendar UI (T-217)

---

## T-217 — Built-in calendar + optional external sync (#67)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.8 (FullCalendar primary; `.ics` always; "Add to Google Calendar" env-gated OAuth; no Apple API)

### ARCH source
- `ARCHITECTURE.md` §12 (FullCalendar — STACK_LOCK §2), §13 (i18n/RTL)

### Depends on
- T-215/T-216 (plan items)

### What this ticket builds

**Frontend + backend:** Render the active plan on the **built-in FullCalendar** (month/week toggle, colour-coded by subject; auto-updates on regeneration) — the primary experience. **`.ics` export** always available (provider-neutral; Apple/Outlook/anything; no external dependency). **"Add to Google Calendar"** via the student's own OAuth, **env-gated** by `GOOGLE_CALENDAR_SYNC_ENABLED` — hidden when unconfigured (only `.ics` shows), degrades gracefully. Each event: title=topic, duration=`est_minutes`, colour=subject. No Apple Calendar API (`.ics` only).

### Acceptance (demo script)

1. [ ] Plan renders on FullCalendar (month/week, subject colours), auto-updates
2. [ ] `.ics` export always available (no external dependency)
3. [ ] "Add to Google Calendar" appears only when `GOOGLE_CALENDAR_SYNC_ENABLED`; else hidden
4. [ ] Google sync uses the student's own OAuth; degrades to `.ics`
5. [ ] RTL / i18n

### Out of scope
- Reminders (T-218)

---

## T-218 — Reminders — push + email + SMS (#68)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.9 (Celery per-session 30-min-before; FCM / Brevo / Jazz+Telenor; degrade silently; channel prefs; missed-task catch-up)

### ARCH source
- `ARCHITECTURE.md` §10 (Celery reminder schedule), STACK_LOCK §notifications (FCM `FCM_*`, Brevo `EMAIL_*`, SMS `SMS_*`), §4 (`reminder_preferences`)

### Depends on
- T-215 (plan items have times), T-209 (`reminder_preferences`)

### What this ticket builds

**Backend:** Per-session reminders 30 min before each scheduled study session, via three channels per STACK_LOCK §notifications — **FCM** push, **Brevo** email (NOT SendGrid), **Jazz + Telenor** SMS (NOT Twilio; critical for low-connectivity Pakistan). All three **degrade silently** when their env vars are absent. Student channel preferences in `reminder_preferences` (default push+email+SMS on). Missed-task catch-up: the next-day reminder includes the missed task.

### Acceptance (demo script)

1. [ ] Reminder fires 30 min before each scheduled session
2. [ ] Push (FCM) / email (Brevo) / SMS (Jazz+Telenor) all wired
3. [ ] Each channel no-ops silently without its env vars
4. [ ] Channel preferences respected
5. [ ] Missed-task catch-up included next day

### Out of scope
- Adherence computation (T-219)

---

## T-219 — Plan adherence tracking + alerts (#70)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.10 (Celery beat `self_study.check_adherence` ~22:00 Karachi; activity-inferred completion; 2-miss alert student + parent; adherence% → Flow 9 pass probability)

### ARCH source
- `ARCHITECTURE.md` §10 (`self_study.check_adherence` beat; `ADHERENCE_CHECK_HOUR_KARACHI`), §9.21 (`self_study.adherence_alert`, `self_study.adherence_updated`), §4 (`study_plan_days`)

### Depends on
- T-210 (session activity), T-215 (plan)

### What this ticket builds

**Backend:** A daily Celery beat `self_study.check_adherence` (~22:00 Asia/Karachi; `ADHERENCE_CHECK_HOUR_KARACHI` default 22). Task completion is **inferred from activity** (a study session logged on the topic, practice questions attempted) — not a gameable checkbox. Compute `study_plan_days.adherence_pct = completed/scheduled`. **2 consecutive missed days → alert the student** (`self_study.adherence_alert`). Emit `self_study.adherence_updated` (adherence % is a Flow 9 pass-probability input — computed there, not here).

### Acceptance (demo script)

1. [ ] Beat runs ~22:00 Karachi; completion inferred from activity
2. [ ] `adherence_pct` computed per `study_plan_days`
3. [ ] 2 consecutive misses → student alert
4. [ ] `self_study.adherence_updated` emitted
5. [ ] No pass-probability computed here (verified: Flow 9 owns it)

### Out of scope
- Pass-probability computation + parent alert (BLOCKED-HOOKs below)

### Notes / known gotchas
- BLOCKED-HOOK: adherence % → pass-probability model (#85) → Flow 9 / M-18 (Flow 8 emits `self_study.adherence_updated`; Flow 9 computes pass probability).
- BLOCKED-HOOK: parent adherence alert on 2 consecutive misses → Flow 10 / M-19 (student alert built here; parent alert routing — configurable, default on — when Flow 10 ships).

---

## T-220 — Self-study privacy #72 (canonical owner)

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.12 (#72 canonical owner; default share; INVIOLATE when No; aggregate-anonymous regardless; hidden for independent; mid-session toggle)

### ARCH source
- `ARCHITECTURE.md` §6.19 (#72 enforcement), §4 (`student_self_study_privacy`), §14 (aggregate-anonymous disclosure)

### Depends on
- T-209 (privacy table), T-210 (session events)

### What this ticket builds

**Backend + frontend:** Flow 8 is the **canonical owner of #72** — the setting, its storage, and its enforcement live here (Flow 6/7 only reference it). School-student setting "Share self-study activity with teacher: Yes/No", default **Yes**. **INVIOLATE** when No: no role (teacher, coordinator, school admin, platform admin) can see that student's self-study questions in any teacher-facing surface. **Aggregate-anonymous data flows regardless** (Flow 9 training / platform quality analysis receives anonymised signals even at No — disclosed in onboarding + help text). **#72 does not exist for independent students** (hidden entirely). **Mid-session toggle** to No tags subsequent events private (historical already-collected questions remain per Flow 7 §5.7).

### Acceptance (demo script)

1. [ ] #72 setting stored + enforced here (canonical owner)
2. [ ] Default Yes; No makes the student's self-study questions invisible to ALL teacher-facing roles
3. [ ] Aggregate-anonymous signals flow regardless of #72
4. [ ] Setting hidden entirely for independent students
5. [ ] Mid-session toggle tags subsequent events private; history retained

### Out of scope
- Flow 7's consumption of the flag (already built, M-16)

---

## T-221 — Permissions + i18n + notifications + tenant differences

**Layer:** 6
**Milestone:** M-17
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §4 (permissions matrix), §3.13 (tenant differences), §7 (notifications)

### ARCH source
- `ARCHITECTURE.md` §6.19 (permissions), §9.21 (`self_study` + `system` namespaces), §3.16 (tenant routing), §13 (i18n), §14.10 (audit)

### Depends on
- T-209 through T-220

### What this ticket builds

**Backend:** Enforce the Flow 8 permissions matrix + the §3.13 tenant differences (independent locked to self-study, no mode switcher, #72 hidden, exam-syllabus overlay; school cross-grade overlay, #72 visible). Notifications in the `self_study` namespace (reminders, adherence alerts) + `system` (admin). Audit plan create/archive, privacy toggles, admin overrides. i18n — all self-study surfaces in en/ur/sd/ps (RTL); no `__TODO__`.

### Acceptance (demo script)

1. [ ] Permissions matrix + tenant differences enforced
2. [ ] Notifications in correct namespaces; 4 languages
3. [ ] Plan/privacy/override actions audit-logged
4. [ ] Independent vs school behaviour matches §3.13 table
5. [ ] No `__TODO__` strings

### Out of scope
- Anything beyond M-17 scope

---

## T-222 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-17
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-8-self-study.md` §3.1-§3.13

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-209 through T-221

### What this ticket builds

**Test + PR:** Automated E2E (LLM / OCR / embeddings mocked; Celery beats time-warped; FCM/SMS/email + Google-Calendar env-unset so they no-op; no live network) — independent student opens straight into self-study → sets a goal (steers session + shows on panel) → uploads a prep book (PaddleOCR) + reference book → categorises → plan-gen blocked then unblocked → topics extracted (weighted) → 5-question conversational plan → refinement regenerates affected items → calendar renders + `.ics` exports → reminder scheduled 30 min before → adherence beat: 2 misses → student alert + `self_study.adherence_updated` emitted → school student sets #72=No → self-study questions invisible to teacher surfaces. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais; merge-commit to `staging`; tickets = commits).

### Acceptance (demo script)

1. [ ] E2E green (LLM/OCR/embeddings mocked; beats time-warped; channels no-op; no live network)
2. [ ] Asserts upload→categorise→gate→extract→plan→refine→calendar/.ics→reminder→adherence
3. [ ] Asserts independent lock + school toggle + #72 inviolate
4. [ ] Asserts emitted Flow-9 signals (goal, adherence) without computing them here
5. [ ] PR `milestone/M-17-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; merged

### Out of scope
- Anything beyond the M-17 ticket set

---

## Milestone notes

- **Self-study mode — the primary independent-tenant surface** (independents are locked here per Flow 4 v3 §3.2); school students toggle in via #53.
- **Reuses Flow 6 wholesale** — widget #57, panel #59, adaptation #61, pipeline #60 are not re-implemented (T-210). Consumes M-14's daily-goal metric (#69, T-211) and M-08's adaptation hook (session side).
- **Corrected flashcard boundary:** Flow 8 *surfaces* due cards; **py-fsrs scheduling + question queue #76 are Flow 9 / M-18** (BLOCKED-HOOK in T-210). This corrects M-15's note that called the deck an M-17 build — M-15's `flashcard.created` is ultimately consumed by the Flow 9 scheduler.
- **Four BLOCKED-HOOKs:** (T-210) py-fsrs flashcard scheduling → Flow 9 / M-18; (T-211) daily-goal signal → Cognitive DNA, Flow 9 / M-18; (T-219) adherence % → pass probability #85, Flow 9 / M-18; (T-219) parent adherence alert → Flow 10 / M-19.
- **Forward (non-blocked) dep:** subscription tier caps (active plans / monthly uploads) → Flow 13 / M-23; present as a no-op placeholder (schema only) at launch.
- **Stack:** PaddleOCR (not Google Vision), FullCalendar built-in (Google Calendar OAuth env-gated, degrades to `.ics`), FCM/Brevo/Jazz+Telenor (not SendGrid/Twilio) — all per STACK_LOCK; the Google-Calendar item flagged in the change-log resolves as "integration, not GCP managed-service dependency."
- **#72 canonical owner** — the privacy setting's storage + enforcement live here; inviolate when set to No; hidden for independents; aggregate-anonymous flows regardless.
- **Open questions:** built to the spec's launch recommendations (Google-Calendar position Q1; flashcard boundary Q10; granularity bands; cost ceilings), treated as decided per standing instruction.
- **Source flow:** Flow 8 v1 §3.1-§3.13 — drafted; relevant open questions have adopted launch recommendations (none blocking).

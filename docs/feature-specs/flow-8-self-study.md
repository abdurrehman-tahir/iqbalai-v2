# Flow 8 — Student Self-Study Mode

**Status:** draft (v1)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-20
**Related ARCHITECTURE sections:** §3 (multi-tenancy — BOTH tenants), §3.16 (independent tenant), §3.17 (subscription gating placeholder), §3.18 (Grade/Section/Subject — school students), §3.19 (Exam Framework — drives plan target), §4 (DB), §4.21 (dual Alembic heads — this flow writes to BOTH schemas), §5 (API), §6.19 (permission inheritance), §7 (RAG — Pattern P personal-pool retrieval), §7.21 (cross-grade unidirectional retrieval — school students), §8 (LLM, esp. §8.6 typed prompts), §8.22 (vision-LLM routing for image questions), §9 (NATS), §9.21 (notification namespaces), §10 (Celery), §10.6 (beat schedule), §11.19 (upload profiles — `student_material`, `student_question_image`), §13 (i18n), §14.10 (audit log)
**Related feature specs:** `flow-4-student-onboarding.md` (mode switcher #53, diagnostic #51, exam date #52, independent lock to self-study), `flow-6-student-studies-lecture.md` (reuses hybrid widget #57, live panel #59, NATS #60, per-session adaptation #61), `flow-7-next-day-review.md` (school self-study questions feed the teacher review when #72=share), `flow-9-ai-intelligence.md` (future — owns question bank, spaced repetition scheduling, cognitive DNA, pass probability; adherence + self-study signals feed it), `flow-13-subscriptions.md` (future — tier caps on uploads / plan regeneration)
**v2 doc features covered:** #62, #63, #64, #65, #66, #67, #68, #69, #70, #72

---

## 1. Purpose

A student studies on their own — uploads their own material, sets a daily goal, and works through an AI-generated study plan calibrated to a real exam date. This is the **only** mode independent students have, and an **opt-in mode** school students toggle into alongside their teacher's lectures.

This flow owns the arc from **"student enters self-study"** through **"AI builds a study plan from the student's own prep book"** to **"daily adherence is tracked and fed into the student's pass probability."**

Critical foundations:

- **Daily goal setting** (#69) — student writes today's goal in their own words; AI uses it to steer the session
- **4-type material upload** (#62) — PDF / camera photo / gallery photo / typed question, each routed appropriately (PaddleOCR for images)
- **Book categorisation + prep-book gate** (#63) — at least one "Prep Question Book" required before a study plan can generate (hard validation)
- **Question-to-topic extraction** (#64) — NLP scans the prep book, weights topics by exam frequency
- **Conversational study plan creation** (#65) — AI chats to build the plan; student refines naturally
- **Study plan granularity** (#66) — day-by-day for short plans, weekly milestones for long ones
- **Built-in calendar + optional external sync** (#67) — FullCalendar primary; .ics / Google Calendar export secondary
- **Reminders** (#68) — push (FCM) + email (Brevo) + SMS (Jazz/Telenor), 30 min before each session
- **Plan adherence tracking** (#70) — daily check; miss 2 consecutive days → alert student + parent; adherence feeds pass probability
- **Self-study privacy setting** (#72) — canonical owner; controls whether a school student's self-study activity is visible to their teacher (Flow 7)

**This flow is genuinely dual-tenant.** Most prior flows treated independent users as a variant. Here, independent students are first-class: self-study IS their entire product. Every section below explicitly states school vs independent behaviour.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Student** | Toggles into Self-Study Mode (#53, Flow 4) alongside Lecture Mode. Uploads own material, builds study plans, sets goals. Self-study activity visibility to teacher controlled by #72. |
| **Independent Student** | LOCKED to Self-Study Mode (Flow 4 v3 §3.2). No teacher, no Lecture Mode, no #72 setting (nothing to share with). Self-study is their whole experience. |
| **School Teacher** | Indirect — sees a school student's self-study questions in Flow 7 review ONLY when #72=share. No direct surface in this flow. |
| **Coordinator / School Admin** | Per §6.19: aggregate-only view of self-study adherence metrics for students in scope (school tenant). No access to individual self-study content. |
| **Parent (linked)** | Receives adherence alerts (#70) when child misses 2 consecutive days, IF parent alert enabled (default on). Per Flow 10 read-only. |
| **District / Platform Admin** | Per §6.19: inherit aggregate metrics in scope. Platform Admin monitors reminder-delivery + plan-generation pipeline health. |

---

## 3. Lifecycle

### 3.1 Entering self-study mode (#53-ref, tenant-dependent)

```
   SCHOOL STUDENT                          INDEPENDENT STUDENT
   ─────────────                           ──────────────────
   logged in (Lecture Mode default)        logged in (locked Self-Study)
       ↓ taps "Self Study" toggle (#53)        ↓ (no toggle — only mode)
   MODE=self_study                         MODE=self_study (permanent)
       ↓                                       ↓
   restores last self-study state          restores last self-study state
       ↓                                       ↓
            ┌──────────────────────────────────────┐
            │  SELF-STUDY HOME                       │
            │  - Today's goal (#69)                  │
            │  - Material library (#62)              │
            │  - Active study plan calendar (#67)    │
            │  - Quick upload (#62)                  │
            └──────────────────────────────────────┘
```

**Locked rules:**

- **School students:** mode switcher (#53) is owned by Flow 4. This flow consumes its `mode=self_study` state. Switching modes preserves where they left off in each (Flow 4 §x mode-state persistence).
- **Independent students:** no mode switcher rendered. The app opens directly into self-study. Any attempt to reach a Lecture Mode route → redirect to self-study home.
- **State persistence:** last goal, last opened material, last plan view persist per `user_settings` (per tenant schema).
- **Subscription gate (placeholder):** per §3.17, a future free-tier cap on number of active study plans / monthly uploads. At launch the gate is a no-op (schema only). Hooks present, limits unset.

### 3.2 Daily goal setting (#69)

```
   SELF_STUDY_HOME
       ↓ start of session (or "set goal" prompt)
   GOAL_PROMPT            ("What's your goal today?" — free text via #57 widget)
       ↓ student types/speaks goal
   GOAL_SET              (e.g. "Understand Newton's Laws chapter 5")
       ↓ injected into session AI context
   SESSION_GUIDED        (AI references goal; live panel #59 shows it)
       ↓ end of session
   GOAL_CHECK            ("Did you achieve your goal today?")
       ↓ student responds
   GOAL_LOGGED           (student_goals: goal_text, achieved bool, date)
```

**Locked rules:**

- Goal is **free-text in the student's own words**, entered via the hybrid widget #57 (text or voice). No dropdown, no template.
- Goal is **injected as context** into the session's AI system prompt (per §8.6 typed prompt `self_study_session_v1.py`). The AI steers explanations toward the stated goal.
- The live feedback panel (#59, Flow 6) **displays the active goal** during the session.
- **One goal per day per student.** Editable until end of day. If a student sets a goal mid-day after already having one, it replaces (with confirmation).
- **End-of-session check** ("Did you achieve your goal?") fires once per day, when the student leaves an active self-study session of >5 minutes. Response stored. Skippable.
- Goal data **feeds Cognitive DNA (Flow 9)** as a signal (self-awareness / goal-achievement pattern). This flow only emits the event; Flow 9 consumes.
- **Both tenants** identical behaviour.

### 3.3 Material upload — 4 types (#62)

```
   UPLOAD_INITIATED      (student taps "Upload" — 4 tabs)
       ├─→ [ PDF file ]        → direct ingest (Pattern P personal-pool RAG)
       ├─→ [ Camera photo ]    → PaddleOCR → text → ingest
       ├─→ [ Gallery photo ]   → PaddleOCR → text → ingest
       └─→ [ Type a question ] → embed directly (no file)
       ↓ after upload
   POST_UPLOAD_CHOICE    ("Instant Answer" OR "Add to Study Library")
       ├─→ INSTANT_ANSWER      → one-shot RAG answer, not persisted to library
       └─→ ADD_TO_LIBRARY      → persisted to student's personal pool; book categorisation (#63) follows
```

**Locked rules:**

- **Four input methods:** PDF upload, device camera, gallery picker, typed query. The frontend uses the hybrid widget #57 for the typed path; native file/camera/gallery pickers for the others.
- **OCR is PaddleOCR** (STACK_LOCK §OCR primary — multilingual incl. Urdu), Tesseract 5 fallback for simple typed text. **NOT Google Vision** (v2 doc was wrong on this).
- **Image upload profile:** `student_material` for full-page document photos; `student_question_image` (per §11.19, max 3 images, 5 MB each, EXIF stripped) for question-attached images routed to vision-LLM (§8.22).
- **Two distinct RAG flows** per the post-upload choice:
  - **Instant Answer:** ephemeral. The uploaded content is embedded, queried once, answered, NOT added to the persistent personal pool. (Still emits a NATS interaction event for Cognitive DNA.)
  - **Add to Study Library:** persisted to the **Student Personal Pool** (private to student, per tenant schema). Triggers book categorisation (#63).
- **Personal pool is private.** Per the data-access model: a student's uploaded material is visible ONLY to that student. Not to teacher, not to coordinator, not to other students. (Distinct from the school Library which teachers manage.)
- **Storage:** MinIO, scoped per tenant + per user. Retention: indefinite while account active; purged on account deletion (per §14 retention).
- **Max file size:** per §11.19 upload profiles (PDF up to the document profile cap; images 5 MB each).
- **Both tenants** identical, EXCEPT: school students' uploaded material can optionally be cross-referenced against their Grade-Subject curriculum (§7.21 unidirectional retrieval) when answering; independent students' material is answered purely from their own pool + AI knowledge (no curriculum overlay unless they selected an exam syllabus during signup).

### 3.4 Book categorisation + prep-book gate (#63)

```
   ADD_TO_LIBRARY        (a book/document is being added)
       ↓ categorisation prompt
   CATEGORISE            ("Is this a Prep Question Book or a Content Book?")
       ├─→ prep_questions      (past papers / practice questions)
       └─→ reference_content   (notes / textbook / reference)
       ↓ persisted with book_type
   CATEGORISED
       ↓ study-plan generation attempted later
   PLAN_GATE_CHECK       (does the student have ≥1 prep_questions book?)
       ├─→ YES → plan generation allowed (§3.6)
       └─→ NO  → HARD BLOCK: "Please upload a prep question book to generate a study plan."
```

**Locked rules:**

- Every library-added book is categorised: `book_type ENUM[prep_questions, reference_content]`.
- **Hard validation:** study-plan generation (#65) is BLOCKED unless the student has at least one `prep_questions` book. Error message exact: "Please upload a prep question book to generate a study plan." Not a soft warning — a blocker.
- **Rationale:** the study plan is exam-driven; without past-paper / practice questions, topic prioritisation (#64) has nothing to weight against.
- Re-categorisation allowed (student mis-tagged a book). Changing the last prep book to reference re-triggers the gate.
- **Both tenants** identical.

### 3.5 Question-to-topic extraction (#64)

```
   PREP_BOOK_ADDED       (book_type=prep_questions)
       ↓ background Celery task `self_study.extract_topics`
   QUESTIONS_EXTRACTED   (parse all questions from the prep book)
       ↓ LLM batch: "What topic does this question test?"
   TOPICS_TAGGED         (per-question topic via §8.6 `question_topic_extract_v1.py`)
       ↓ cluster + deduplicate
   TOPICS_CLUSTERED
       ↓ weight by frequency
   WEIGHTED_TOPIC_LIST   (more questions on a topic → higher weight → earlier in plan)
       ↓ cached for plan generation
   READY_FOR_PLAN
```

**Locked rules:**

- Runs as a **background Celery task** (`@tenant_task`) on prep-book add — not blocking the upload UX.
- LLM batch-classifies each extracted question into a curriculum topic (mapped to the student's exam syllabus from §3.19 Exam Framework where available; free-text topic otherwise for independents without a syllabus).
- Output is a **weighted topic list**: `weight = question_count_for_topic / total_questions`. Higher weight = higher study-plan priority.
- Extraction failures (unparseable PDF, OCR garbage) → topic list built from whatever parsed; banner: "We couldn't read part of this book — plan may be incomplete."
- **Cost ceiling:** $0.25 per prep-book extraction (batched LLM calls). Cap at 500 questions per book; overflow flagged.
- **Both tenants** identical; school students additionally get curriculum-topic mapping via §3.19.

### 3.6 Conversational study plan creation (#65)

```
   PLAN_START            (gate passed — ≥1 prep book exists)
       ↓ AI chat (NOT a form) via #57 widget
   AI_ASKS_5_QUESTIONS   (sequential, conversational)
       1. "What exam are you preparing for?"   (pre-filled from #52 exam date / Exam Framework if set)
       2. "When is it?"                         (exam_date)
       3. "Which books do you have?"            (lists library; confirms prep + reference)
       4. "How many hours can you study daily?"
       5. "Which topics are you already strong in?"
       ↓ all answered
   PLAN_GENERATED        (weighted_topic_list + answers → study_plan + study_plan_items)
       ↓ student reviews calendar
   PLAN_REVIEW
       ↓ conversational refinement
   REFINE                ("Make Mondays lighter" → regenerate affected items)
       ↓ student accepts
   PLAN_ACTIVE           (saved; calendar populated; reminders scheduled)
```

**Locked rules:**

- **Conversational, not a form.** The AI asks the 5 guided questions one at a time via the hybrid widget #57 (text or voice). Pre-fills what it already knows (exam date from Flow 4 #52, books from library).
- **Refinement is natural language.** "Make Mondays lighter", "I have a wedding next week, skip those days", "more practice questions, less reading" → AI regenerates affected `study_plan_items` only, not the whole plan.
- **Plan target spec** captured: grade target, chapter/topic range, weak-topics-priority. Strong topics (Q5) get lighter coverage.
- **One active study plan per student per exam** at launch. A student with two upcoming exams can have two plans (subscription-gated in future per §3.17). Switching exams archives the prior plan.
- **Generation cost ceiling:** $0.50 per full plan generation; refinements $0.10 each.
- **Plan generation failure:** retries 3×; final failure → "Couldn't build your plan right now — try again shortly." Partial answers preserved so the student doesn't re-answer the 5 questions.
- **Both tenants** identical. Independent students' exam was chosen at signup (Flow 3/4 v3 independent path); school students' from Flow 4 onboarding.

### 3.7 Study plan granularity (#66)

```
   PLAN_DURATION_COMPUTED   (exam_date − today)
       ├─→ ≤ 14 days   → DAILY tasks
       ├─→ 15-90 days  → 3-DAY BLOCK tasks
       └─→ > 90 days   → WEEKLY milestones (daily detail only for current week)
```

**Locked rules:**

- Granularity auto-selected by plan duration (no user choice at launch):
  - ≤14 days → `granularity=day` (every day has explicit tasks)
  - 15–90 days → `granularity=3day` (3-day blocks)
  - >90 days → `granularity=week` (weekly milestones) + daily detail rendered only for the current week
- `study_plan_items(granularity ENUM[day,3day,week], start_date, tasks[], est_minutes)`.
- As the exam approaches, granularity **auto-refines**: a >90-day plan that crosses the 90-day threshold regenerates the now-current portion into 3-day blocks (nightly Celery task `self_study.refine_granularity`).
- **Both tenants** identical.

### 3.8 Built-in calendar + optional external sync (#67)

```
   PLAN_ACTIVE
       ↓ rendered in
   BUILTIN_CALENDAR      (FullCalendar — month/week toggle, colour-coded by subject)  ← PRIMARY
       ↓ optional export
   EXTERNAL_SYNC
       ├─→ [ Export .ics ]            (provider-neutral; downloads a calendar file)   ← always available
       └─→ [ Add to Google Calendar ] (Google Calendar API via user OAuth)            ← optional, env-gated
```

**Locked rules:**

- **Primary experience is IqbalAI's own calendar** — FullCalendar (STACK_LOCK §Calendar, MIT core only, no premium plugins). Month + week views, colour-coded by subject. Updates automatically when the plan regenerates.
- **External sync is secondary + optional:**
  - **.ics export** is always available (provider-neutral; works with Apple Calendar, Outlook, anything). No external dependency.
  - **"Add to Google Calendar"** uses the Google Calendar API via the student's own OAuth consent. **Env-gated** (`GOOGLE_CALENDAR_SYNC_ENABLED`); if not configured, the button is hidden and only .ics export shows. (Open question Q1 — confirm this doesn't violate STACK_LOCK's "no GCP managed services"; the position is that user-OAuth calendar export is an integration, not a managed-service dependency, and degrades gracefully.)
- **Each calendar event:** title = topic, duration = `est_minutes`, colour = subject.
- **No Apple Calendar API** — Apple sync is via .ics only (no native API integration).
- **Both tenants** identical.

### 3.9 Reminders — push + email + SMS (#68)

```
   PLAN_ACTIVE           (each scheduled session has a start time)
       ↓ Celery scheduled (per-session, 30 min before)
   REMINDER_FIRES        (30 min before scheduled session)
       ├─→ FCM push          (Firebase Cloud Messaging)
       ├─→ Email             (Brevo free tier default)
       └─→ SMS               (Jazz / Telenor direct API) ← critical for low-connectivity Pakistan
       ↓ student's channel preference respected
   DELIVERED
```

**Locked rules:**

- **Three channels** per STACK_LOCK §notifications:
  - **Push:** Firebase Cloud Messaging (FCM). `FCM_SERVER_KEY`, `FCM_PROJECT_ID`.
  - **Email:** Brevo free tier (default; Resend/Mailgun alternates). **NOT SendGrid** (v2 doc wrong; STACK_LOCK forbids SendGrid paid).
  - **SMS:** Jazz + Telenor direct APIs. **NOT Twilio** (v2 doc wrong; STACK_LOCK forbids Twilio). SMS is critical for Pakistani students with unreliable internet.
- **All three degrade silently** if their env vars are absent (per STACK_LOCK: "If env vars missing → code path bypassed silently. Full integration logic implemented regardless."). So in dev/staging without SMS keys, the SMS path no-ops without error.
- **Reminder timing:** 30 minutes before each scheduled study session.
- **Channel preference:** student chooses which channels in settings. Default: push + email on; SMS on (since it's the reliable channel in PK).
- **Missed task:** the next-day reminder includes the missed task ("Yesterday you missed Vectors practice — catch up today + today's task").
- **Both tenants** identical. Parent reminder copy (for adherence alerts) is separate — see §3.10.

### 3.10 Plan adherence tracking + alerts (#70)

```
   DAILY (Celery beat `self_study.check_adherence` ~22:00 Asia/Karachi)
       ↓ for each active plan
   CHECK_TODAY           (did the student complete today's scheduled tasks?)
       ↓ task marked complete on activity (study session logged, questions practised)
   ADHERENCE_COMPUTED    (study_plan_days: adherence_pct = completed_tasks / scheduled_tasks)
       ↓ consecutive-miss check
   MISS_CHECK
       ├─→ < 2 consecutive misses → no alert
       └─→ ≥ 2 consecutive misses → ALERT student (+ parent if enabled)
       ↓ adherence rate emitted as event
   FEEDS_PASS_PROBABILITY  (Flow 9 model input — this flow only emits the signal)
```

**Locked rules:**

- **Daily adherence check** runs as a Celery beat task ~22:00 Asia/Karachi (after the day's activity, before the next day). Env: `ADHERENCE_CHECK_HOUR_KARACHI` (default 22).
- **Task completion** is inferred from activity (a study session logged on the topic, practice questions attempted) — not a manual checkbox the student games.
- **2 consecutive missed days** → alert the student (`self_study.adherence_alert`). Parent alert is **configurable** (default ON; parent can disable in their settings per Flow 10).
- **Adherence percentage is a model input to pass probability (Flow 9 #85).** This flow computes and stores `adherence_pct`; it does NOT compute pass probability (that's Flow 9). It emits `self_study.adherence_updated` for Flow 9 to consume.
- **Both tenants:** school students' parent alerts route through linked parents (Flow 10); independent students may also have a linked parent (independent signup can include a guardian) — same mechanism. Independent students with no parent linked simply get no parent alert.

### 3.11 Self-study session interaction (reuses Flow 6 components)

```
   IN_SESSION            (student studying material / asking questions)
       ↓ uses
   - hybrid widget #57   (text / voice / image input — Flow 6 owned)
   - live feedback panel #59  (60s updates, 10-min stuck nudge — Flow 6 owned)
   - per-session adaptation #61 (2+ repeat Qs → angle switch — Flow 6 owned)
   - NATS pipeline #60   (every interaction emitted as event — Flow 6 owned)
       ↓ events flow to
   - Flow 7 (school only, #72=share)  — teacher next-day review
   - Flow 9 (both tenants)            — Cognitive DNA, mistake tracking
```

**Locked rules:**

- **No re-implementation.** The self-study session reuses the EXACT components Flow 6 built: widget #57, panel #59, adaptation #61, pipeline #60. This flow does not redefine them.
- **Events are tenant-tagged.** Self-study interaction events carry `tenant_type` + `mode=self_study`. School-student events (when #72=share) reach Flow 7; independent-student events never reach any teacher surface.
- **RAG retrieval pattern for self-study Q&A:** Pattern P (personal pool) as primary source; school students additionally get §7.21 cross-grade curriculum overlay; independent students get exam-syllabus overlay if they selected one, else AI knowledge.
- **Both tenants** use the same session UI; the difference is the retrieval sources and the event destinations.

### 3.12 Self-study privacy setting (#72) — canonical owner

```
   SETTINGS (school student only)
       ↓
   PRIVACY_TOGGLE        ("Share self-study activity with teacher: Yes / No"; default Yes)
       ├─→ YES → self-study questions flow to teacher's Flow 7 review
       └─→ NO  → teacher loses visibility of THIS student's self-study activity
       ↓ regardless of setting
   AGGREGATE_ANONYMOUS    (system-level AI improvement still receives anonymised signals)
```

**Locked rules:**

- **Flow 8 is the canonical OWNER of #72.** Flow 6 and Flow 7 reference it; the setting, its storage, and its enforcement live here.
- **Default = Yes (share).** Enables the Flow 7 next-day review value.
- **INVIOLATE** (per Flow 6 §4 + Flow 7 §4 lock): when set to No, NO role — not teacher, not coordinator, not school admin, not platform admin — can see that student's self-study questions in any teacher-facing surface.
- **Aggregate anonymous data flows regardless** of #72. System-level AI improvement (Flow 9 model training, platform-wide explanation-quality analysis) receives anonymised signals even when #72=No. This is disclosed to students in onboarding + the setting's help text.
- **#72 does NOT exist for independent students.** They have no teacher to share with. The setting is hidden entirely from their UI. Their self-study data flows only to their own Cognitive DNA (Flow 9) + aggregate anonymous improvement.
- **Mid-session toggle:** turning #72 OFF mid-session means events from that point are tagged private; the teacher's Flow 7 review excludes this student's questions going forward (historical questions already collected lawfully remain — per Flow 7 §5.7).

### 3.13 Tenant differences summary

| Aspect | School Student | Independent Student |
|---|---|---|
| Mode | Toggle into self-study (also has Lecture Mode) | Locked to self-study only |
| Mode switcher (#53) | Visible | Hidden |
| Privacy #72 | Visible, default share | Hidden (no teacher) |
| Curriculum overlay in RAG | Grade-Subject curriculum via §7.21 | Exam syllabus (if chosen at signup) else none |
| Self-study questions → Flow 7 | Yes, if #72=share | Never |
| Self-study signals → Flow 9 | Yes | Yes |
| Parent adherence alert | Linked parent (Flow 10) | Linked guardian if present, else none |
| Study plan, goals, uploads, reminders, calendar | Identical | Identical |
| Schema written to | `school` schema | `independent` schema |

---

## 4. Permissions matrix

Per §6.19 inheritance.

| Action | Student (own) | Parent (linked, RO) | Coordinator (scope) | School Admin (school) | (+District+Platform) |
|---|:---:|:---:|:---:|:---:|:---:|
| Set daily goal (#69) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Upload material (#62) | ✅ | ❌ | ❌ | ❌ | ❌ |
| View own personal pool | ✅ | view (RO, if #72/Flow 10 permits) | ❌ | ❌ | ❌ |
| Categorise book (#63) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Generate / refine study plan (#65) | ✅ | ❌ | ❌ | ❌ | ❌ |
| View own study plan calendar (#67) | ✅ | view (RO) | aggregate | aggregate | inherit |
| Export plan (.ics / Google) (#67) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Set reminder channel prefs (#68) | ✅ | ❌ | ❌ | ❌ | ❌ |
| View own adherence (#70) | ✅ | view (RO) | aggregate (scope) | aggregate (school) | inherit |
| Receive adherence alert (#70) | ✅ | ✅ (if enabled) | ❌ | ❌ | ❌ |
| Toggle privacy #72 (school only) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Override privacy #72 | ❌ | ❌ | ❌ | ❌ | ❌ |
| View individual self-study content | ✅ (own) | RO (own child, Flow 10) | ❌ | ❌ | ❌ |
| View aggregate self-study adherence metrics | own | own child | ✅ scope | ✅ school | inherit |

**Locked rules:**
- **Personal pool content is private to the student.** Parents get read-only via Flow 10 (own child only). No admin role sees individual self-study content — aggregate adherence only.
- **Privacy #72 inviolate** — no role overrides.
- **Independent student rows:** Parent/Coordinator/Admin columns mostly N/A (no school structure); a linked guardian gets the Parent column behaviour.

---

## 5. Edge cases

### 5.1 Entering mode (§3.1)
- **School student with no lectures assigned yet toggles self-study:** allowed; self-study is fully independent of lecture assignments.
- **Independent student tries to access a Lecture Mode URL:** redirect to self-study home (no error, just redirect).
- **Subscription cap reached (future):** at launch no-op; when enabled, "You've reached your plan limit — upgrade or archive an existing plan."

### 5.2 Daily goal (§3.2)
- **Student sets no goal:** session proceeds without goal context; live panel shows "set a goal" link; no end-of-day check fires.
- **Goal in mixed languages:** stored as-is; injected into AI context as-is (multilingual handling per §13).
- **Student sets multiple goals in one day:** latest replaces previous (with confirm). Only one `student_goals` row per day; updated in place.
- **End-of-session check after a <5-min session:** not fired (too short to assess).

### 5.3 Material upload (§3.3)
- **Camera/gallery photo with no readable text (blurry, non-text image):** PaddleOCR returns empty/low-confidence → "We couldn't read this image clearly — try a clearer photo or type your question."
- **Corrupt / password-protected PDF:** rejected with clear error; not added to pool.
- **Upload exceeds size cap:** rejected per §11.19 with the cap stated.
- **Typed question with "Instant Answer":** answered one-shot; nothing persisted to library (still emits Cognitive DNA event).
- **Duplicate upload (same file hash):** prompt "You already uploaded this — use existing or add anyway?"
- **OCR produces text in a script the student's UI isn't set to:** stored as-is; answer generated in the student's UI language with the source content referenced.
- **Independent student uploads copyrighted textbook:** out of scope to police at launch; ToS disclaimer covers user-uploaded content. Personal pool is private (not redistributed).

### 5.4 Book categorisation + gate (§3.4)
- **Student skips categorisation:** book added as `reference_content` by default with a nudge "Tag this as a prep book if it has practice questions."
- **All prep books deleted after a plan exists:** existing plan remains active; NEW plan generation blocked again until a prep book is re-added.
- **Book is genuinely both** (has notes AND practice questions): student picks the dominant type; topic extraction (#64) still scans for questions regardless of tag.

### 5.5 Topic extraction (§3.5)
- **Prep book has 0 detectable questions** (mis-tagged reference book): extraction yields empty weighted list; plan generation warns "We couldn't find practice questions in your prep book — plan will use general topic order."
- **Extraction exceeds 500-question cap:** processes first 500; banner notes truncation.
- **LLM unavailable during extraction:** task retries 3×; final failure → topics built from headings/structure heuristic; flagged as low-confidence.
- **Independent student with no exam syllabus selected:** topics are free-text clusters (no curriculum mapping); plan still generates.

### 5.6 Study plan creation (§3.6)
- **Student abandons mid-conversation (answered 3 of 5):** partial answers saved; resumes where left off next time; no orphan plan created.
- **Exam date in the past:** "That date has passed — set a new exam date" (links to Flow 4 #52). Plan blocked until fixed.
- **Exam date today or tomorrow:** plan generates an intensive ≤2-day cram plan (daily granularity); warns it's tight.
- **Daily hours unrealistic (e.g., 20 hrs/day):** accepted but AI gently flags "that's a lot — sustainable pace matters"; doesn't block.
- **Refinement request the AI can't parse** ("make it better"): AI asks a clarifying question rather than regenerating blindly.
- **Two plans for two exams:** allowed (subscription-gated future). Each independent.

### 5.7 Granularity (§3.7)
- **Plan crosses a granularity threshold overnight** (91→90 days): nightly `self_study.refine_granularity` regenerates the current portion into finer blocks; future portion unchanged.
- **Very long plan (>1 year):** weekly milestones only; daily detail for current week. No performance issue (items generated lazily per week).

### 5.8 Calendar + sync (§3.8)
- **Google Calendar sync env not configured:** "Add to Google Calendar" button hidden; only .ics export shows.
- **Student revokes Google OAuth after syncing:** sync stops silently; built-in calendar unaffected; no error.
- **Plan regenerates after external sync:** built-in calendar auto-updates; external calendars do NOT auto-update (one-time export); student re-exports if desired. UI notes this.
- **.ics with hundreds of events:** generated fine; standard calendar apps handle it.

### 5.9 Reminders (§3.9)
- **SMS env vars absent (dev/staging):** SMS path no-ops silently; push + email still attempt.
- **All channels disabled by student:** no reminders; in-app calendar still shows the schedule. Settings warn "you've disabled all reminders."
- **SMS gateway (Jazz/Telenor) returns failure:** logged; email + push still deliver; no retry storm (single attempt per channel per reminder).
- **Student in different timezone than Asia/Karachi** (rare — diaspora independent student): reminders use the student's stored timezone if set, else Asia/Karachi default.
- **Reminder for a session the student already completed early:** suppressed (no point reminding for a done task).

### 5.10 Adherence (§3.10)
- **Student completes tasks but doesn't mark them:** completion inferred from activity (session logged / questions practised), so no false "missed."
- **Student studies a DIFFERENT topic than scheduled:** counts as partial adherence (studied, but off-plan); `adherence_pct` reflects scheduled-task completion specifically.
- **2 consecutive missed days but student was sick / travelling:** alert still fires (system can't know); student can "pause plan" (future feature — TODO) to avoid nuisance alerts.
- **Parent alert enabled but no parent linked:** student alert fires; parent alert silently skipped.
- **Adherence event emitted but Flow 9 not yet shipped:** event queued/dropped gracefully; no error in this flow (Flow 9 is a consumer; absence doesn't break the producer).

### 5.11 Privacy #72 (§3.12)
- **School student toggles #72 OFF:** future events private; Flow 7 excludes them going forward; historical questions remain (lawfully collected).
- **Independent student somehow has a #72 value:** ignored (no teacher surface consumes it); setting not rendered.
- **Student migrates school→independent:** #72 becomes irrelevant; prior school-tenant data stays in school schema; new self-study data writes to independent schema.

---

## 6. Limits

### Material upload (§3.3)
- Input methods: 4 (PDF / camera / gallery / typed)
- OCR: PaddleOCR primary, Tesseract 5 fallback
- Image attachments per question: 3 max, 5 MB each (§11.19 `student_question_image`)
- Document photo / PDF: per `student_material` profile cap (§11.19)
- Personal pool: private per student; indefinite retention while active

### Topic extraction (§3.5)
- Max questions parsed per prep book: 500 (overflow flagged)
- Cost ceiling: $0.25 per extraction
- Runs as background `@tenant_task`

### Study plan (§3.6, §3.7)
- Active plans per student: 1 per exam at launch (multi-exam = multi-plan, subscription-gated future)
- Plan generation cost ceiling: $0.50; refinement: $0.10 each
- Granularity: ≤14d daily / 15-90d 3-day / >90d weekly
- 5 guided questions for conversational creation

### Reminders (§3.9)
- Channels: FCM push + Brevo email + Jazz/Telenor SMS
- Timing: 30 min before each session
- All channels degrade silently if env unconfigured

### Adherence (§3.10)
- Check cadence: daily ~22:00 Asia/Karachi (env `ADHERENCE_CHECK_HOUR_KARACHI`)
- Consecutive-miss alert threshold: 2 days
- Parent alert: configurable, default ON

### Privacy (§3.12)
- #72 default: share (school only); inviolate; hidden for independents

---

## 7. Notifications

Per §9.21 namespace conventions.

### Namespace: `self_study` (primary — per ledger naming)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Study session reminder (30 min before) | Student | Push + email + SMS (per prefs) | `self_study.session_reminder` |
| Missed task carried into next day | Student | Push + email | `self_study.missed_task_reminder` |
| 2 consecutive days missed | Student | Push + email + SMS | `self_study.adherence_alert_student` |
| 2 consecutive days missed (parent alert) | Linked parent (if enabled) | Push + email + SMS | `self_study.adherence_alert_parent` |
| Study plan generated / regenerated | Student | In-app | `self_study.plan_ready` |
| Topic extraction complete (prep book processed) | Student | In-app | `self_study.prep_book_processed` |
| Exam date approaching (30/14/7/1 day — per Flow 4 #52) | Student (+ parent) | Push + email + SMS | `self_study.exam_countdown` |

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Reminder delivery failure rate > threshold | Platform Admin | In-app + email | `system.reminder_delivery_failure_rate` |
| Plan-generation pipeline failure spike | Platform Admin | In-app | `system.plan_generation_failure_rate` |
| Topic-extraction cost ceiling breached in aggregate | Platform Admin | In-app | `system.extraction_cost_alert` |

**Notifications cannot be turned off** per Flow 1 Q13 — BUT reminder *channel* selection (#68) is a student preference (which channels, not whether critical alerts fire). Adherence + exam-countdown alerts always fire on at least one available channel.

---

## 8. Open questions

1. **Google Calendar API vs STACK_LOCK "no GCP managed services":** Recommendation — user-OAuth calendar export is an integration, not a managed-service dependency, and is fully env-gated + degrades to .ics-only. Position: allowed. **Needs Abd. confirmation** since it brushes the forbidden line. If rejected → .ics export only, drop the Google button.

2. **Personal pool storage cap per student (free tier):** Recommendation — unbounded at launch; subscription tiers (§3.17) add caps later. Tracked under Flow 13.

3. **"Pause plan" for sick/travel days** (avoid nuisance adherence alerts): Recommendation — Phase 2. At launch, alerts fire regardless; student tolerates or completes a token task. TODO `phase-2-pause-study-plan`.

4. **Multiple active plans (multi-exam) at launch:** Recommendation — allow technically (data model supports it) but UI surfaces one "primary" plan; full multi-plan UX deferred. Confirm whether to expose multi-plan now or hide behind subscription.

5. **Independent student copyrighted-material uploads:** Recommendation — ToS disclaimer covers it; personal pool is private (no redistribution). No active policing at launch. Confirm legal comfort with Awais/Mufti.

6. **Adherence inference accuracy** — "studied but off-plan" counting: Recommendation — scheduled-task completion is the adherence metric; off-plan study logged separately as "bonus activity," doesn't inflate adherence. Confirm this is the desired behaviour (vs counting any study as adherence).

7. **SMS cost control** (Jazz/Telenor are paid per message): Recommendation — SMS only for high-value alerts (session reminders if student opts in, adherence alerts, exam countdown) — NOT for every notification. Daily SMS cap per student (env `SMS_DAILY_CAP_PER_USER`, default 5). Confirm cap.

8. **End-of-session goal check frequency:** once per day feels right; confirm it shouldn't be per-session (could annoy on multi-session days). Recommendation — once per day, on the last session.

9. **Diaspora independent students (non-PK timezone):** Recommendation — store per-user timezone; default Asia/Karachi. Confirm whether to even support non-PK timezones at launch or assume all PK.

10. **Flashcard deck ownership** (#58 auto-flashcards from Flow 6 highlights → spaced repetition): Recommendation — the deck (collection) is referenced here as part of self-study materials, but the **scheduling algorithm (py-fsrs)** and the question queue (#76) are **Flow 9**. This flow surfaces "due flashcards" but doesn't compute the schedule. Confirm the boundary so Flow 9 owns scheduling cleanly.

11. **#73 Anonymised Class Comparison** ("Top 35% of your Physics class"): NOT claimed by this flow — it's a comparison/analytics display, likely Flow 9 or Flow 11. Confirm it's out of Flow 8 scope. (Currently treated as out of scope here.)

12. **Strong-topics handling** (Q5 of plan creation): Recommendation — strong topics get lighter coverage but NOT zero (light review still scheduled). Confirm vs fully excluding them.

---

## 9. Out of scope (for now)

- **Spaced repetition scheduling + flashcard timing** (py-fsrs, question queue #76). Flow 9 owns; this flow only references "due cards." (Flow 9)
- **Question bank** (#74), **Bloom's tagging** (#75), **mistake tracking** (#81), **cognitive DNA** (#83), **pass probability** (#85), **forgetting curve** (#94). All Flow 9.
- **Anonymised class comparison** (#73). **Resolved: Flow 11** (renders the student-facing rank; Flow 9 produces the ranking data).
- **Pause / freeze study plan** for sick/travel. (TODO `phase-2-pause-study-plan`)
- **Multiple simultaneous active plans full UX.** Single primary plan at launch. (TODO `phase-2-multi-exam-plans`)
- **Personal pool storage caps / subscription tiers.** Unbounded at launch. (Flow 13)
- **Apple Calendar native API sync.** .ics export only. (TODO `phase-3-apple-calendar-api`)
- **Plan templates / shareable plans** (student shares a plan with a friend). Private only at launch. (TODO `phase-3-shareable-plans`)
- **Auto-import of school timetable** into self-study plan (avoid clashes with school hours). (TODO `phase-2-timetable-aware-plans`)
- **Group self-study** (studying the same plan together). Flow 11 territory.
- **Offline mode** (study plan / material available without internet). (TODO `phase-3-offline-self-study`)
- **Voice-driven plan creation entirely hands-free** (full STS loop for the 5 questions). Text+voice widget at launch; full STS deferred. (TODO `phase-2-voice-plan-creation`)
- **Adherence gamification** (streaks, badges beyond basic). (TODO `phase-3-adherence-gamification`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy; this flow writes to BOTH `school` and `independent` schemas
- **§3.16** — Independent tenant (self-study is their whole product)
- **§3.17** — Subscription gating placeholder (plan/upload caps, no-op at launch)
- **§3.18** — Grade/Section/Subject (school students' curriculum overlay)
- **§3.19** — Exam Framework (drives study-plan target + topic mapping)
- **§4.2-4.8** — DB mixins; **§4.12** migrations; **§4.21** dual Alembic heads (writes to both schemas)
- **§5** — API design; **§5.9** idempotency (upload, plan generation); **§5.11** bulk (study_plan_items creation)
- **§6.19** — Permission inheritance (defining rule for §4 matrix)
- **§7.3-7.10** — Pattern P personal-pool RAG (self-study Q&A primary source)
- **§7.21** — Cross-grade unidirectional retrieval (school students' curriculum overlay)
- **§8.6** — Typed prompts: `self_study_session_v1.py`, `question_topic_extract_v1.py`, `study_plan_create_v1.py`, `study_plan_refine_v1.py`, `goal_guidance_v1.py`
- **§8.22** — Vision-LLM routing (image questions via `student_question_image`)
- **§9** — NATS events: `self_study.session_started`, `self_study.goal_set`, `self_study.material_uploaded`, `self_study.prep_book_added`, `self_study.plan_generated`, `self_study.plan_refined`, `self_study.adherence_updated`, `self_study.privacy_changed`
- **§9.21** — Notification namespaces (`self_study`, `system`)
- **§10.3-10.5** — Celery `@tenant_task`: `self_study.extract_topics`, `self_study.generate_plan`, `self_study.refine_granularity`, `self_study.check_adherence`, `self_study.send_session_reminders`
- **§10.6** — Beat schedule: `self_study.check_adherence` (daily ~22:00), `self_study.refine_granularity` (nightly), `self_study.send_session_reminders` (rolling, 30-min-before computation)
- **§11.19** — Upload profiles: `student_material` (PDFs + document photos), `student_question_image` (question attachments)
- **§13** — i18n (4 languages; goal/plan/reminders localised; OCR multilingual via PaddleOCR)
- **§14.10** — Audit log: privacy #72 changes; plan deletions

### Data model sketch

```
# Written to BOTH `school` and `independent` schemas (tenant-routed):

student_materials               (personal pool)
  id (uuidv7), tenant_type, student_user_id (FK), title,
  source_type (enum: pdf, camera, gallery, typed),
  book_type (enum: prep_questions, reference_content, nullable for typed),
  storage_key (MinIO), ocr_text (text, nullable), file_hash,
  added_to_library (bool), created_at, deleted_at

student_goals
  id (uuidv7), tenant_type, student_user_id (FK), goal_date (date),
  goal_text, achieved (bool, nullable), achieved_response_at (nullable),
  created_at, updated_at
  -- unique(student_user_id, goal_date)

prep_book_topics                (weighted topic list from #64)
  id (uuidv7), tenant_type, student_material_id (FK), topic_label,
  curriculum_topic_id (FK, nullable — school/syllabus mapping),
  question_count, weight (float), extracted_at

study_plans
  id (uuidv7), tenant_type, student_user_id (FK),
  exam_type_id (FK, nullable), exam_date (date),
  daily_hours (int), strong_topics (text[]),
  status (enum: active, archived), granularity_current (enum: day,3day,week),
  created_at, updated_at, archived_at

study_plan_items
  id (uuidv7), study_plan_id (FK), granularity (enum: day,3day,week),
  start_date (date), end_date (date), tasks_jsonb, est_minutes (int),
  subject_color, created_at

study_plan_days                 (adherence tracking, #70)
  id (uuidv7), study_plan_id (FK), day_date (date),
  scheduled_tasks_jsonb, completed_tasks_jsonb, adherence_pct (float),
  consecutive_miss_count (int), alerted_at (nullable)

student_self_study_privacy      (#72 — school students only; column on user_settings is acceptable too)
  student_user_id (FK), share_with_teacher (bool, default true), updated_at

reminder_preferences            (#68)
  student_user_id (FK), push_enabled, email_enabled, sms_enabled,
  timezone (default Asia/Karachi), updated_at
```

---

## 11. Acceptance criteria

### Daily goal (#69)
- ✅ Free-text goal via hybrid widget #57 (text or voice)
- ✅ Goal injected into session AI context; shown in live panel #59
- ✅ One goal per day; end-of-session "did you achieve it?" check (last session, >5 min)
- ✅ Goal emits Cognitive DNA signal (Flow 9 consumes)

### Material upload (#62)
- ✅ 4 input methods: PDF / camera / gallery / typed
- ✅ Images OCR'd via PaddleOCR (Tesseract fallback); NOT Google Vision
- ✅ Post-upload choice: Instant Answer (ephemeral) vs Add to Library (persisted)
- ✅ Personal pool private to student; MinIO scoped per tenant + user
- ✅ Two distinct RAG flows (instant vs library)
- ✅ Both tenants; school adds §7.21 curriculum overlay

### Book categorisation + gate (#63)
- ✅ `book_type ENUM[prep_questions, reference_content]`
- ✅ HARD BLOCK on plan generation without ≥1 prep book; exact error message
- ✅ Re-categorisation re-triggers gate

### Topic extraction (#64)
- ✅ Background `@tenant_task` on prep-book add
- ✅ LLM batch topic classification; weighted by question frequency
- ✅ Curriculum-topic mapping for school (§3.19); free-text for independents
- ✅ 500-question cap; $0.25 cost ceiling

### Study plan creation (#65)
- ✅ Conversational (5 guided questions via #57), NOT a form
- ✅ Pre-fills exam date (#52) + library books
- ✅ Natural-language refinement regenerates affected items only
- ✅ Resumable if abandoned mid-conversation
- ✅ $0.50 generation / $0.10 refinement cost ceilings

### Granularity (#66)
- ✅ Auto-selected: ≤14d daily / 15-90d 3-day / >90d weekly
- ✅ Nightly `refine_granularity` upgrades current portion as exam approaches

### Calendar + sync (#67)
- ✅ FullCalendar built-in (month/week, colour-coded) — PRIMARY
- ✅ .ics export always available (provider-neutral)
- ✅ Google Calendar API export env-gated; hidden if unconfigured (pending Q1)
- ✅ Built-in auto-updates on plan regenerate; external is one-time export

### Reminders (#68)
- ✅ FCM push + Brevo email + Jazz/Telenor SMS; NOT SendGrid, NOT Twilio
- ✅ 30 min before each session; channel prefs respected
- ✅ All channels degrade silently if env unconfigured
- ✅ Missed task carried into next-day reminder

### Adherence (#70)
- ✅ Daily Celery beat ~22:00 Asia/Karachi
- ✅ Completion inferred from activity (not gameable checkbox)
- ✅ 2 consecutive misses → student alert (+ parent if enabled, default on)
- ✅ `adherence_pct` emitted as Flow 9 pass-probability input

### Privacy #72
- ✅ Flow 8 is canonical owner; default share (school only)
- ✅ INVIOLATE — no role overrides
- ✅ Hidden entirely for independent students
- ✅ Aggregate anonymous data flows regardless of setting
- ✅ Mid-session toggle excludes future questions from Flow 7

### Dual-tenant
- ✅ School: toggle into self-study; #72 visible; curriculum overlay; questions → Flow 7 if shared
- ✅ Independent: locked to self-study; #72 hidden; no teacher surface; writes to independent schema
- ✅ Both: identical plan/goal/upload/reminder/calendar UX

### i18n
- ✅ All UI in en/ur/sd/ps; RTL handled
- ✅ PaddleOCR multilingual incl. Urdu; goals/plans in student's language

### Audit
- ✅ #72 changes logged per §14.10
- ✅ Plan deletions logged

---

**Last reviewed:** 2026-05-20
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1:** Initial draft. Covers 10 features (#62, #63, #64, #65, #66, #67, #68, #69, #70, #72). First genuinely dual-tenant core flow (school toggle-in + independent locked-in). Aligned with:
- Flow 4 v3 (mode switcher #53, exam date #52, diagnostic #51, independent self-study lock)
- Flow 6 v2 (reuses #57 widget, #59 live panel, #60 NATS, #61 adaptation — does not re-implement)
- Flow 7 (school self-study questions feed teacher review when #72=share; #72 owned HERE)
- Flow 9 future (adherence + self-study signals feed pass probability + cognitive DNA; spaced repetition/question bank explicitly NOT owned here)
- STACK_LOCK corrections vs v2 doc: PaddleOCR (not Google Vision), Jazz/Telenor SMS (not Twilio), Brevo email (not SendGrid), FullCalendar (built-in calendar), py-fsrs (deck referenced, scheduling is Flow 9)
- §10.6 beat schedule (new tasks: check_adherence daily 22:00, refine_granularity nightly, send_session_reminders rolling)

**Open for Awais review:**
- Google Calendar API vs STACK_LOCK forbidden-GCP line (Q1) — needs Abd. ruling
- SMS cost cap per student (Q7)
- Adherence inference: scheduled-task completion vs any-study (Q6)
- Copyrighted material upload policy (Q5) — legal comfort
- Flashcard deck / spaced-repetition boundary with Flow 9 (Q10)
- #73 anonymised comparison placement (Q11)

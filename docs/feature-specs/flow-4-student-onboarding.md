# Flow 4 — Student Onboarding

**Status:** draft (v3 — incorporates feedback round 2: profile mandatory trim, independent student diagnostic, Exam Framework as AI-generated study plan, 6-month read-only graduation window with auto-migration to independent)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy, esp. §3.16 independent tenant model, §3.19 exam framework engine NEW), §4, §6 (esp. §6.13 ParentChildLink, §6.19 inheritance, §6.20 independent signup), §7 (RAG + Pattern A web research for frameworks), §8 (LLM, esp. §8.21 quarterly framework refresh agent NEW), §10 (Celery beat for refresh + migration), §13 (i18n), §14.10 (audit log)
**Related feature specs:** `flow-1-platform-setup.md`, `flow-2-admin-coordinator-setup.md`, `flow-3-teacher-onboarding.md`, `flow-6-student-studies-lecture.md` (future), `flow-8-self-study.md` (future), `flow-10-parent-monitoring.md`, `flow-11-group-study-dashboards.md`
**v2 doc features covered:** #10, #15, #51, #52, #53 (#19, #20, #22 retired per Q17; Exam Framework is a NEW concept extending #52)

---

## 1. Purpose

A student goes through multi-phase onboarding before they can study effectively. Two distinct types:

1. **School-onboarded students** — created by Coordinator via bulk import or individual addition in Flow 2 (Grade/Section enrollment model). Activate via invite link, complete profile, optionally pick an exam framework, optionally take diagnostic, pick a mode.
2. **Independent students** — sign up themselves via the public signup flow. Belong to the `independent` tenant. **Locked to Self-Study Mode only.** They typically have a clear exam target and use the platform for personal exam prep.

This flow also owns **parent onboarding** (#10 — school students only) and the **Exam Framework engine** — an AI-driven research and study-plan generation system that produces living, quarterly-refreshed study plans for specific exam targets (Matric Punjab, O-Level Cambridge, MDCAT, etc.).

Critical foundations established here that downstream flows depend on:

- **Two tenant types** at the student layer (school vs. independent)
- **Mode selection** (#53) — Lecture + Self-Study for school students; Self-Study only for independent
- **Exam Framework** — an AI-generated study plan that overlays in Lecture Mode (as exam-prep augmentation) and drives Self-Study Mode (as the primary structure)
- **Diagnostic** (#51) — seeds the Cognitive DNA (Flow 9) for BOTH school and independent students (per v3 feedback)
- **Graduation lifecycle** — 6-month read-only window in school tenant, then auto-migration to independent tenant with full data continuity

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Student** | Created in Flow 2 (Coordinator-driven Grade+Section enrollment). Activates via invite, sets minimal profile, picks exam framework + date, optionally takes diagnostic, picks mode. Teachers are automatic via Grade enrollment. |
| **Independent Student** | Self-signs-up via public signup page. Self-Study Mode only. Picks exam framework + grade level + exam date at signup. Takes diagnostic per their exam framework. Uploads own materials. |
| **Parent (of school student)** | Registers independently. Initiates link request; student approves. Read-only monitoring once linked. **No parent linking for independent students at launch.** |
| **Coordinator** | Per Flow 2 v3: enrolls students into Grade/Section, initiates promotion requests. Sees onboarding status in own assigned scope. |
| **School Admin** | Per Flow 2: oversees school enrollment, approves promotion requests, can override unenrollment. Approves AI-generated framework study plans if delegated by Platform Admin (TBD, deferred — Platform Admin owns approval at launch). |
| **Platform Admin** | Creates Exam Framework definitions, triggers AI research, **approves AI-generated study plans before publication**, triggers quarterly refreshes. |
| **Teacher** | Sees students in assigned Grade-Subject offerings via Flow 2. Does NOT approve connections (connections are automatic via enrollment). |
| **District Admin** | Per §6.19, inherits permissions of lower roles in scope. |

---

## 3. Lifecycle

### 3.1 School Student onboarding lifecycle (mandatory fields trimmed)

```
   ACCOUNT_CREATED         (Flow 2 — Coordinator enrolled student into Grade + Section)
       ↓ Coordinator sends invite (email)
   INVITED                 (invite link active 7 days)
       ↓ student clicks link, sets password
   PROFILE_BASIC           (forced: confirm name, set language preference, accept ToS)
       ↓ above 3 mandatory fields complete
   PROFILE_COMPLETE        (other profile fields go into a deferrable "complete your profile" prompt)
       ↓ optionally select exam framework + date (#52)
   FRAMEWORK_SET (or SKIPPED)
       ↓ optionally take diagnostic (#51)
   DIAGNOSTIC_DONE (or SKIPPED)
       ↓ student picks Lecture Mode or Self-Study Mode (#53)
   MODE_SELECTED
       ↓ (Grade enrollment → Teacher assignments → automatic)
   READY_TO_STUDY
       ↓ year-end promotion (Flow 2 workflow)
   PROMOTED OR HELD_BACK
       ↓ ... continues until final grade reached
   GRADUATED — SCHOOL READ-ONLY  (Grade 12 / FSc 2 / final grade)
       ↓ 6 months pass (GRADUATION_GRACE_DAYS env var)
   AUTO_MIGRATED_TO_INDEPENDENT
```

**Locked rules:**

- **Mandatory fields at PROFILE_BASIC:** name (confirmation of pre-populated value from Flow 2 enrollment), language preference, ToS acceptance. NOTHING ELSE. Grade is auto-set from enrollment, exam framework + date are NOT required to advance.
- **Deferrable fields** (promoted but skippable, surfaced in "complete your profile" persistent banner): DOB, avatar, exam framework + date, diagnostic. Student can fill any time.
- Mode selection (#53) IS mandatory before READY_TO_STUDY — student must pick at least one mode.
- Lecture Mode requires Grade enrollment (automatic from Flow 2).
- Self-Study Mode requires only MODE_SELECTED — works even without exam framework (uses defaults).
- Diagnostic results (when taken) seed Cognitive DNA (Flow 9 #83).

### 3.2 Independent Student onboarding lifecycle

```
   SIGNUP_INITIATED        (public signup at /independent/signup:
                            email + password + name + language + grade level + exam framework
                            — exam framework REQUIRED for independent students)
       ↓ email verification (Authentik)
   PROFILE_BASIC           (first login: confirm fields, set exam date)
       ↓
   PROFILE_COMPLETE
       ↓ optionally take diagnostic (#51) — independent students DO get diagnostic at launch
   DIAGNOSTIC_DONE (or SKIPPED)
       ↓
   READY_TO_STUDY          (Self-Study Mode only)
```

**Locked rules:**
- Lives in `independent` Postgres schema per §3.16.
- Auth via Authentik at `/independent/signup`; JWT claim `tenant_type=independent`.
- **Exam framework is REQUIRED at signup for independents** (their primary use case is exam prep; no school structure to fall back on).
- **Self-Study Mode ONLY** — no Mode Switcher UI.
- **Diagnostic IS available** (per v3 feedback Q3). Independent diagnostic uses the student's selected exam framework as the test calibration source.
- No parent linking at launch.

### 3.3 Parent registration & linking lifecycle (#10, school students only)

```
   PARENT_REGISTERED       (public parent signup: email + password + name + language)
       ↓ email verification
   PARENT_ACTIVE_UNLINKED  (logged in, no children linked)
       ↓ initiates link via student email
   LINK_PENDING            (student approval required, §6.13 opt-in)
       ↓ student approves
   LINKED                  (read-only access per Flow 10)
       ↓ student or parent revokes / student graduates + 6mo
   UNLINKED                (access removed; data history preserved)
```

**Locked rules:**
- Parent can link to multiple school students; school student can have multiple parents.
- Link approval is from student side — explicit consent (§6.13).
- Revocation one-click from either side, immediate.
- **Parents cannot link to independent students at launch.**
- 90-day auto-suspend of unlinked parent accounts; resumable on next login.
- **Parent link auto-severs when student auto-migrates to independent** (after 6-month graduation window).

### 3.4 Mode selection lifecycle (#53)

```
School Students:
   MODE_NONE
       ↓ student picks
   LECTURE_MODE  OR  SELF_STUDY_MODE
       ↓ free toggle anytime via Mode Switcher
   (switches as needed; both modes coexist concurrently)

Independent Students:
   (Locked to SELF_STUDY_MODE; no switcher shown)
```

**Locked rules (School Students):**
- Switching instant, no data loss.
- AI personalization adapts per Flow 6 #61.
- Dashboard mode-conditional (Lecture section hidden in Self-Study Mode).

**Locked rules (Independent Students):**
- No Mode Switcher UI; backend rejects mode-switch API calls with 404.

### 3.5 Exam Framework lifecycle (NEW per v3 feedback Q5)

An **Exam Framework** is a platform-level, AI-generated, quarterly-refreshed study plan for a specific exam target. Examples: "Matric Punjab Board," "O-Level Cambridge," "MDCAT," "FSc Punjab Pre-Engineering," "A-Level Cambridge."

#### 3.5.1 Framework definition lifecycle

```
   DRAFT                   (Platform Admin creates definition: name, exam name, region, target grade range)
       ↓ Platform Admin triggers initial AI research
   RESEARCHING             (Pattern-A LLM agent runs web research via SearXNG; gathers past papers, study guides, official syllabus, expert tips)
       ↓ AI synthesizes findings into a study plan structure
   PENDING_APPROVAL        (study plan v1 awaiting Platform Admin review)
       ↓ Platform Admin approves
   PUBLISHED v1            (visible to students; selectable in onboarding)
       ↓ Platform Admin edits OR 90-day refresh cycle fires
   REFRESHING              (AI re-runs research; produces v2)
       ↓ Platform Admin approves
   PUBLISHED v2            (students offered to upgrade; existing students pinned to v1 unless they opt in)
       ↓ Platform Admin deprecates
   DEPRECATED              (no longer offered to new students; existing students grandfathered)
```

**Locked rules:**

- **AI research workflow:** the Pattern-A LLM agent (per ARCHITECTURE §7.12, §8.21) executes a tool chain:
  1. Web search via SearXNG for past papers / study guides / expert tips / official syllabus
  2. Fetch top-N relevant pages via web_fetch (10-20 sources typically)
  3. Synthesize content with LLM into structured study plan (see §3.5.2 for content structure)
  4. Output JSONB content + cited sources list
  5. Mark `pending_approval`
- **Manual approval gate:** Platform Admin reviews plan content + cited sources before publishing. SLA: 72 hours. If unapproved at 7 days → reminder notification. If unapproved at 14 days → escalation; plan stays in `pending_approval`; students see "framework being prepared" message.
- **Quarterly refresh:** Celery beat task `framework.refresh_quarterly` triggers re-research every 90 days. Same Platform Admin approval flow applies.
- **Versioning:** each refresh produces a new version. Students pinned to v1 see banner "Your framework has been updated to v2 — review changes / switch?" Switching is opt-in (per Q6 confirmation).
- **Past paper sourcing:** AI sources publicly available samples + summarizes patterns + generates similar practice problems. Direct republishing of copyrighted past papers is NOT permitted. (Legal review per TODO; AI cites sources for transparency.)
- **Region scoping:** each framework has a `region` field (e.g., "Punjab," "Sindh," "International"). Students see frameworks matching their region OR marked "any."
- **Refresh cost:** ~$3-10 per framework refresh in LLM tokens. ~10 active frameworks × 4 refreshes/year = ~$120-400/year operational cost.

#### 3.5.2 Study plan content structure (Q4 confirmation, AI must intelligently source from past papers etc.)

The AI-generated plan content (stored as JSONB) includes:

```
{
  "version": 1,
  "framework_name": "Matric Punjab Board — Physics",
  "region": "Punjab",
  "target_grade_range": [9, 10],
  "sources_cited": [{"url": "...", "title": "..."}, ...],
  "generated_at": "2026-05-14T...",
  "topics": [
    {
      "topic_name": "Newton's Laws of Motion",
      "priority_weight": 0.9,            // how heavily this is tested in past papers
      "exam_frequency": "every_year",    // past-paper frequency analysis
      "recommended_hours": 6,
      "key_concepts": ["...", "..."],
      "common_pitfalls": ["...", "..."],
      "past_paper_patterns": "MCQs typically test...",  // patterns AI extracts
      "practice_problems_generated": [...],             // AI-generated similar problems
      "expert_tips": ["...", "..."]
    },
    ...
  ],
  "weekly_pacing": [
    {"week_from_exam": 12, "focus_topics": ["..."], "hours_estimated": 10},
    ...
  ],
  "exam_strategy": {
    "time_allocation": "...",
    "scoring_strategy": "...",
    "common_mistakes": ["..."]
  }
}
```

The frontend renders this structure into a learnable study plan UI.

#### 3.5.3 Student framework selection lifecycle

```
   NOT_SELECTED           (school student; optional)
       ↓ student selects a framework
   ACTIVE                 (pinned to current published version)
       ↓ student switches to refreshed version OR drops
   ACTIVE on new version  OR  ABANDONED
```

**Locked rules:**
- **Multiple frameworks per student allowed** (Q3 = yes per recommendation). E.g., student preparing for Matric AND a separate scholarship test (NTS) selects both.
- Each framework contributes to the student's self-study plan structure.
- Student can switch / drop frameworks anytime; historical progress retained.
- For school students: framework selection is **optional**, surfaced after MODE_SELECTED.
- For independent students: framework selection is **mandatory** at signup.

#### 3.5.4 How Exam Framework interacts with the two modes (Q5 critical clarification)

**Self-Study Mode** — framework drives the structure. The student's daily study plan = their framework's topics + pacing + materials, personalized by their Cognitive DNA (Flow 9). Their dashboard's primary view is the framework-driven plan.

**Lecture Mode** (school students only) — framework overlays as a SECONDARY "exam prep track." The student's primary structure is still their school's curriculum-driven lessons (set by their teacher per Flow 5). Framework adds a "your school is on Chapter 5; for your Matric Punjab target, also focus on these supplementary topics, past-paper patterns, etc." tab. **Framework does NOT replace teacher curriculum; it AUGMENTS.**

A school student who has selected a framework in Lecture Mode sees both:
- "Today's Lecture" (from teacher's curriculum) — primary
- "Exam Prep Track" (from framework) — supplementary tab

The AI's per-session adaptation (Flow 6 #61) considers both sources when responding to student questions.

### 3.6 Diagnostic test lifecycle (#51) — extended to independent students per v3 feedback Q3

```
   NOT_TAKEN
       ↓ student starts (per subject for school students; per framework for independent students)
   IN_PROGRESS             (questions answered; can save and resume within 7 days)
       ↓ all questions answered or timeout
   COMPLETED               (results seed Cognitive DNA per Flow 9 #83)
       ↓ student retakes (30-day cooldown)
   RETAKEN
```

**Locked rules:**

- For **school students:** diagnostic is per-subject. A Grade 9 Physics + Math student can take diagnostics for both. Question source: Question Bank (Flow 9 #74) where available, LLM fallback elsewhere.
- For **independent students** (NEW per v3): diagnostic is per-exam-framework. The framework's topic priorities calibrate the question selection. Question source: Question Bank entries tagged with the exam framework, or LLM fallback using the framework's content as context.
- 15-25 questions per diagnostic, calibrated to grade + exam framework + subject.
- Results NEVER shown as grades — only "areas to focus on" per coaching principle.
- Retake allowed at most once per 30 days.
- For independent students, the diagnostic explicitly contributes to their Cognitive DNA in the `independent` schema (separate from school students' DNA storage).

### 3.7 Exam date lifecycle (#52)

```
   NOT_SET
       ↓ student selects exam framework, sets exam date
   EXAM_SET                (date pinned)
       ↓ time passes
   EXAM_APPROACHING        (within 30 days)
       ↓ date passes
   EXAM_PASSED             (prompts student to set new exam)
   OR student changes manually
```

**Locked rules:**
- Past dates rejected.
- > 5-year future dates allowed with warning.
- 30-day approach triggers notifications.
- Exam date drives the framework's weekly pacing structure.

### 3.8 Data rights lifecycle (#15)

```
   STANDARD_ACCESS
       ↓ student requests export
   EXPORT_REQUESTED (async job)
       ↓ completes ≤ 24 hours
   EXPORT_READY (downloadable 7 days)
       ↓ student requests deletion
   DELETION_REQUESTED (30-day grace; account suspended; cancellable)
       ↓ 30 days pass OR cancelled
   DELETED  OR  GRACE_CANCELLED
```

**Locked rules:**
- Export: ZIP with JSON + PDF summary + CSVs (account data, all AI messages, notes, highlights, flashcards, interaction logs).
- Deletion is GDPR-style erasure of personal data; anonymized analytics retained.
- 30-day grace period, cancellable.
- Applies to both school and independent students (each in their schema).
- Linked parents auto-unlinked on student deletion.

### 3.9 Graduation lifecycle (REWRITTEN per v3 feedback)

```
   ENROLLED_IN_FINAL_GRADE  (Grade 12 / FSc 2)
       ↓ Coordinator includes student in graduating cohort (Flow 2 promotion request)
       ↓ School Admin approves
   GRADUATED — SCHOOL_READ_ONLY
       • Lecture Mode visible but READ-ONLY (past lectures viewable; no new lectures, no new questions to teachers)
       • Self-Study Mode FULLY ACCESSIBLE
       • All AI personalization, Cognitive DNA, exam framework selections, study materials intact
       • Linked parents retain access during this window
       ↓ 6 months pass (GRADUATION_GRACE_DAYS env var, default 180)
   AUTO_MIGRATING (Celery task fires)
       ↓ atomic migration transaction
   AUTO_MIGRATED_TO_INDEPENDENT
       • Account moved to independent tenant (tenant_type=independent)
       • Lecture Mode UI disappears
       • All learning data, AI model state, framework selections, self-study materials migrated
       • Connection to original school severed
       • Linked parents auto-unlinked
       • One-way migration (no return to school tenant)
```

**Locked rules:**

- **6-month window** is the grace period in school-read-only state. Configurable via env var `GRADUATION_GRACE_DAYS` (default 180).
- **Auto-migration** uses the same Authentik user; updates JWT claim `tenant_type` from `school` → `independent`. Email + password unchanged.
- **Migration is atomic.** Single Celery task transaction: copy data from school schema → independent schema, then update auth, then mark school records as `migrated_out`. If task fails mid-flight, automatic retry with exponential backoff (5 attempts). If still failing after 5 attempts → Platform Admin notification; student stays in read-only state until manually resolved. NEVER produce a half-migrated state.
- **What migrates** (per Q-FB2 = my recommendation):
  - ✅ Account record (email, password hash, language, profile)
  - ✅ Learning data (Cognitive DNA, mistake history, spaced-repetition state, predictions, all Flow 9 outputs)
  - ✅ Self-study materials uploaded
  - ✅ Notes, highlights, flashcards
  - ✅ Exam framework selections + progress against them
  - ✅ AI conversation history (student's chats with LLM)
  - ✅ Quiz attempt history + diagnostic history
  - ❌ Parent linking history (auto-severed)
  - ❌ Teacher-attributed records (e.g., "Teacher X reviewed Student Y's question") — these stay in school schema as historical attribution; student's COPY of the answer (what they saw) migrates with them
- **School records preserved as alumni** per Q-FB3: school's Flow 11 dashboards see graduated/migrated students in an "Alumni" status. Anonymized appropriately for reporting; full data remains in school schema for 7-year audit retention.
- **Student communication** per Q-FB5:
  - At graduation: "You've graduated! For 6 months you can still use Self-Study mode in your school account. After that, your account will move to Independent mode."
  - 30 days before migration: reminder
  - 7 days before migration: reminder + "export your data if you want"
  - On migration day: confirmation + new login flow note (same credentials, different tenant)

---

## 4. Permissions matrix

Per §6.19 inheritance: every action available to a role is available to all roles above in scope.

**For School Student resources:**

| Action | Student (self) | Parent (linked) | Teacher (assigned) | Coordinator (scoped) | School Admin | (+District+Platform Admin per inheritance) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Edit own profile | ✅ | view | view | view | view | inherit ✅ |
| Select / change exam framework (#52) | ✅ | view | view | view | view | inherit ✅ |
| Take diagnostic (#51) | ✅ | view results | view results | view results | view results | inherit ✅ |
| Switch mode (#53) | ✅ | view current | view | view | view | inherit ✅ |
| Bulk enroll into Grade/Section | n/a | n/a | n/a | ✅ (own scope) | ✅ | inherit ✅ |
| Individual enroll | n/a | n/a | n/a | ✅ (own scope) | ✅ | inherit ✅ |
| Initiate promotion request (Flow 2) | n/a | n/a | n/a | ✅ (own scope) | n/a | inherit ✅ |
| Approve promotion request (Flow 2) | n/a | n/a | n/a | n/a | ✅ | inherit ✅ |
| Initiate parent link request (#10) | n/a | ✅ | n/a | n/a | n/a | ✅ |
| Approve / reject parent link | ✅ | n/a | n/a | n/a | n/a | inherit ✅ |
| Revoke linked parent | ✅ | ✅ (own link) | n/a | n/a | override ✅ (audit) | inherit ✅ |
| Request data export (#15) | ✅ | n/a | n/a | n/a | n/a | inherit ✅ |
| Request account deletion (#15) | ✅ | n/a | n/a | n/a | n/a | inherit ✅ |
| Cancel deletion in grace | ✅ | n/a | n/a | n/a | ✅ | inherit ✅ |
| View own dashboard | ✅ | view | view (own students) | view (own scope) | view (own school) | inherit ✅ |

**For Independent Student resources:**

| Action | Independent Student (self) | Platform Admin |
|---|:---:|:---:|
| Edit own profile | ✅ | ✅ |
| Change exam framework / grade level | ✅ | ✅ |
| Take diagnostic | ✅ | view results |
| Upload to private pool | ✅ | ✅ (support/troubleshooting) |
| Request data export (#15) | ✅ | ✅ |
| Request account deletion (#15) | ✅ | ✅ |
| View own dashboard | ✅ | ✅ |

**For Exam Framework resources (platform-level):**

| Action | Platform Admin | All other roles |
|---|:---:|:---:|
| Create framework definition | ✅ | ❌ |
| Trigger initial AI research | ✅ | ❌ |
| Approve / reject AI-generated study plan | ✅ | ❌ |
| Trigger quarterly refresh manually | ✅ | ❌ |
| Edit framework metadata (region, target grade) | ✅ | ❌ |
| Manually edit AI-generated content | ✅ | ❌ |
| Deprecate framework | ✅ | ❌ |
| View / select published frameworks | (yes — own platform) | ✅ (students) |
| View framework content | ✅ | ✅ (students who selected it) |

**Locked rule:** parent access via `require_parent_of(student_id)` per §6.13. Independent student endpoints route to independent schema repository.

---

## 5. Edge cases

### 5.1 Profile & onboarding sequencing
- **School student tries to skip profile → mode and access study features:** redirected to profile completion; PROFILE_BASIC is the gate.
- **PROFILE_BASIC complete but no exam framework / diagnostic:** student CAN reach READY_TO_STUDY. Frameworks and diagnostic are optional for school students.
- **Independent student tries to skip exam framework at signup:** blocked at signup form. Framework is required.
- **Independent student tries Mode Switcher via direct URL hack:** returns 404; UI never offered switcher.
- **Profile language change after enrollment:** allowed; all subsequent AI interactions in new language; existing notes/lectures preserved in original.
- **Student deletes themselves while in school read-only graduation window:** standard 30-day grace deletion; migration cancelled.

### 5.2 Parent linking (#10)
- **Parent links to student in different school:** allowed — parent identity school-agnostic.
- **Parent enters wrong student email:** no system feedback (don't leak existence). Request times out after 7 days.
- **Student rejects parent link:** parent gets notification (no PII); can re-attempt after 7 days. 3+ rejections → 30-day block.
- **Both parents linked, one revokes:** only that parent's access removed.
- **Student suspended:** linked parent's access suspended.
- **Student deactivated/deleted:** parent link auto-broken.
- **Parent attempts link to independent student:** blocked at API (cross-schema not supported at launch).
- **Unlinked parent 90 days:** account auto-suspended; resumable on next login.
- **Student auto-migrates to independent:** all linked parents auto-severed with email notification.

### 5.3 Grade enrollment (replaces #19/#20)
- **Coordinator enrolls into Grade:** student auto-gets all Grade's teacher assignments via Flow 2 v3 model.
- **Coordinator unenrolls mid-session:** teacher relationships removed; historical data preserved (read-only).
- **Student attempts to send connection request to teacher:** API doesn't exist (#19/#20 removed). Returns 404.
- **Student wants different teacher than Grade-assigned:** must go through Coordinator (cross-section transfer); deferred to Phase 2.

### 5.4 Exam Framework (NEW per v3)
- **Platform Admin creates framework, AI research fails (web search returns 0 useful results):** framework lands in `RESEARCH_FAILED` status. Platform Admin gets notification with the failure reason. Can retry or manually input content.
- **AI generates plagiarized content (verbatim from a copyrighted past paper):** during Platform Admin approval review, this should be caught. The AI output cites all sources. Approval workflow should reject and request regeneration with stronger paraphrasing prompt.
- **Quarterly refresh proposes a substantially different plan from v1:** Platform Admin reviews changes; can approve or reject. If approved, students see banner. Old v1 retained for grandfathered students.
- **Student switches from v1 to v2 mid-study:** their progress data is preserved (Cognitive DNA, mistakes, etc.); their topic-pacing recalibrates against v2 structure. Phase 2 may add visual change-set diff.
- **Multiple frameworks selected by one student:** their dashboard aggregates topics across frameworks; overlapping topics deduplicated. Pacing combines the earliest exam date as the driver.
- **Student selects framework not yet published:** UI shows "framework being prepared by AI — check back later." Notification fires when published.
- **Framework deprecated while student is active on it:** student keeps v1; new selections of this framework blocked. Banner suggests an alternative if Platform Admin specifies one.
- **AI research cost exceeds $10 budget per framework:** task halts; Platform Admin notified to review.
- **Region mismatch:** student in Sindh tries to select a Punjab-region framework. UI warns but allows (some students prepare for cross-region exams).

### 5.5 Diagnostic (#51) — extended for independent students
- **School student starts diagnostic, abandons:** saved IN_PROGRESS; resume within 7 days.
- **Independent student diagnostic without selected framework:** blocked — independent diagnostic requires framework for calibration.
- **Diagnostic LLM call fails:** retry; persistent failure → user sees "try again later"; onboarding continues without diagnostic.
- **Severe gap detection:** results frame as "let's focus here first" — coaching language, never grades.

### 5.6 Exam date (#52)
- **Past date:** rejected.
- **> 5-year future:** allowed with warning.
- **Date passes:** prompt to set new exam (recurring use case).
- **Date changed mid-year:** framework pacing recalibrates.

### 5.7 Data rights (#15)
- Standard rules — applies to both types in respective schemas.

### 5.8 Mode switching (#53)
- **School student mid-lecture switches to Self-Study:** active session preserved; home screen changes; AI adapts.
- **Independent attempts switch:** 404 (no API endpoint).

### 5.9 Graduation (REWRITTEN per v3)
- **Coordinator includes student in graduating cohort during Grade 12 promotion request; School Admin approves:** student → GRADUATED state immediately. 6-month timer starts.
- **Graduated student tries to create new lecture content:** blocked; UI shows "Your school account is read-only. Self-Study Mode is fully available."
- **Graduated student tries to send new question to teacher:** blocked; teacher endpoints return 404 (teacher assignment retained for historical attribution but `is_active=false`).
- **6-month timer expires:** Celery beat task `graduation.migrate_eligible_students` runs daily; identifies eligible students; fires migration Celery task per student.
- **Migration task succeeds:** student's school account is `migrated_out=true`; new login flows to independent tenant.
- **Migration task fails 5x:** Platform Admin notified; student stays in school read-only state until manually resolved.
- **Linked parent during graduation 6-month window:** parent still has access.
- **Linked parent at migration moment:** auto-severed; email notification "Your student has moved to Independent mode; parent monitoring is no longer available for their new account."
- **Held-back student (excluded from graduating cohort):** stays in Grade 12 for new session; never enters graduation lifecycle until included in a future cohort.
- **Student manually requests deletion during 6-month window:** deletion request takes precedence; migration cancelled.
- **Migration mid-flight, student tries to log in:** session blocked with "Migration in progress, please try again in a few minutes." Auth temporarily 503's for that user only.

### 5.10 Cross-tenant
- **School student tries to view another student's data:** 404 per §3.13.
- **School student tries to view independent student data:** 404.
- **Independent student tries to access school endpoints:** 404.
- **Parent tries to view non-linked student:** 404.
- **Teacher tries to view student not in assigned Grade-Subject:** 404.

---

## 6. Limits

### Account
- **Profile mandatory fields:** name (auto-set, confirmable), language preference, ToS acceptance. THAT'S IT (per v3 trim).
- **Profile optional fields:** grade (auto-set for school students; required at signup for independent), DOB, avatar (2 MB max).

### Parent linking (#10)
- Max parents per school student: 5.
- Max students per parent: 10.
- Pending link request TTL: 7 days.
- 3-rejection block: 30 days.
- Unlinked parent auto-suspend: 90 days.

### Exam Framework (NEW)
- Max published frameworks platform-wide at launch: ~10 (Matric Punjab, Matric Sindh, O-Level Cambridge, A-Level Cambridge, FSc Punjab Pre-Engineering, FSc Punjab Pre-Medical, MDCAT, ECAT, NTS, scholarship exams).
- Initial launch set (Q-EF10 = recommendation): Matric Punjab Board, FSc Punjab, O-Level Cambridge, A-Level Cambridge. Others Phase 2 / on-demand.
- Max framework selections per student: 5.
- AI research cost ceiling per refresh: $10 (hard cap; halts task and notifies admin).
- AI research timeout: 30 minutes Celery `soft_time_limit`.
- Quarterly refresh cadence: every 90 days (configurable per framework; default 90).
- Platform Admin approval SLA: 72 hours target; 7-day reminder; 14-day escalation.

### Diagnostic (#51)
- Questions per diagnostic: 15-25 (adaptive per subject/framework, capped at 25).
- Retake cooldown: 30 days.
- Resume window: 7 days.

### Exam date (#52)
- Min: today. Max: today + 5 years (warning beyond).

### Data rights (#15)
- Export SLA: ≤ 24 hours.
- Download window: 7 days after ready.
- Deletion grace: 30 days.
- Export size cap: 1 GB.

### Graduation
- Read-only window: 6 months (180 days, env var `GRADUATION_GRACE_DAYS`).
- Migration task retry: 5 attempts with exponential backoff.

### Independent students
- Free at launch.
- No rate limits beyond §15.11 default anti-abuse.

---

## 7. Notifications

Per ARCHITECTURE §9.21 namespace conventions. Global panel shows aggregate counts only.

### Namespace: `account`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| First-login onboarding complete | Student | In-app | `account.onboarding_complete` |
| PROFILE_BASIC milestone reached | Student | In-app | `account.profile_basic_complete` |
| Optional fields prompt reminder | Student | In-app | `account.profile_complete_prompt` |
| Account suspended | Student | Login banner | `account.suspended` |
| Account reactivated | Student | Email + in-app | `account.reactivated` |
| Data export ready | Student | In-app + email | `account.export_ready` |
| Deletion grace started | Student | Email | `account.deletion_grace_started` |
| Deletion completed | Student | Email (final) | `account.deletion_completed` |
| Parent registration confirmed | Parent | Email | `account.parent_welcome` |
| Unlinked parent 90-day auto-suspend | Parent | Email | `account.parent_auto_suspended` |

### Namespace: `connections` (parent linking)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Parent sends link request | Student | In-app + push | `connections.parent_link_pending` |
| Student approves parent link | Parent | In-app + push | `connections.parent_link_approved` |
| Student rejects parent link | Parent | In-app | `connections.parent_link_rejected` |
| Linked parent revokes | Student | In-app | `connections.parent_link_revoked_by_parent` |
| Linked student revokes | Parent | In-app | `connections.parent_link_revoked_by_student` |
| Parent link auto-broken (student deleted/migrated) | Parent | Email | `connections.parent_link_orphaned` |

### Namespace: `lectures` (school students only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Coordinator enrolls into Grade | Student + parents | In-app + push | `lectures.enrolled` |
| Coordinator unenrolls | Student + parents | In-app + push | `lectures.unenrolled` |
| Promotion approved | Student + parents | In-app + push | `lectures.promoted` |
| Promotion held back | Student + parents | In-app + push | `lectures.held_back` |
| Graduated to read-only state | Student + parents | In-app + push + email | `lectures.graduated_read_only` |
| Migration 30-day reminder | Student + parents | In-app + email | `lectures.migration_reminder_30d` |
| Migration 7-day reminder + data export prompt | Student + parents | In-app + email | `lectures.migration_reminder_7d` |
| Migration complete (account moved to independent) | Student + parents | Email | `lectures.migration_complete` |

### Namespace: `self_study`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Diagnostic completed | Student | In-app | `self_study.diagnostic_completed` |
| Exam date 30 days out | Student + linked parents | In-app + push + email | `self_study.exam_approaching` |
| Exam date passed | Student | In-app | `self_study.exam_passed` |
| Framework selected | Student | In-app | `self_study.framework_selected` |
| Framework upgraded available (v2 published) | Students on v1 | In-app | `self_study.framework_upgrade_available` |
| Framework deprecated | Students on deprecated version | In-app | `self_study.framework_deprecated` |
| Framework preparing (selected unpublished framework) | Student | In-app | `self_study.framework_preparing` |

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| AI framework research completed (pending approval) | Platform Admin | In-app + push | `system.framework_research_complete` |
| AI framework research failed | Platform Admin | In-app + email | `system.framework_research_failed` |
| AI framework research cost ceiling exceeded | Platform Admin | In-app + email | `system.framework_research_cost_exceeded` |
| Framework approval SLA breach (7 days unapproved) | Platform Admin | In-app + email | `system.framework_approval_overdue` |
| Migration task failed 5x (student stuck) | Platform Admin | In-app + email | `system.migration_failed_manual_required` |

**Notifications cannot be turned off** per Flow 1 Q13.

---

## 8. Open questions

1. **Profile fields beyond PROFILE_BASIC minimum.** v3 trims mandatory to name + language + ToS. **Question:** what optional fields are surfaced in the "complete your profile" persistent banner? Recommendation: DOB (for age-appropriate content moderation), avatar (personalization), region (analytics).

2. **Independent student data after auto-migration.** All learning data migrates. **Question:** does the school still see the alumnus in their reporting, or are they fully anonymized post-migration? Recommendation: school sees the alumnus as "Migrated to Independent" status — name/email anonymized to hash, aggregate data retained (test scores, grade history) for 7 years for reporting. The student themselves are no longer reachable through the school.

3. **Exam framework selection at signup mandatory for independent.** Q-EF1 set this. **Sub-question:** can an independent student have NO framework at any point (e.g., they're studying for general knowledge, not a specific exam)? Recommendation: NO at launch — independent product is exam-prep-positioned. "Just learning" users get a generic "self-study" framework auto-assigned (Platform Admin maintains this as a fallback default framework).

4. **Diagnostic for independent students — framework-driven vs subject-driven.** v3 confirms independents get diagnostic. **Question:** is the diagnostic per-subject (like school) or per-framework? Recommendation: per-framework. Each framework has its tested subjects baked in; the diagnostic samples across those.

5. **Multi-framework student diagnostic overhead.** A student with 3 frameworks (Matric + MDCAT + scholarship): do they take 3 diagnostics? Recommendation: yes, one per framework — independent topic coverage and exam pacing differ.

6. **Framework regional defaults for students.** A new school student in Punjab: do we auto-suggest "Matric Punjab Board"? Recommendation: yes, show suggested framework based on student's school region + grade. Suggestion banner, not auto-selection.

7. **Framework AI research approval delegation.** At launch, only Platform Admin approves. **Question:** Phase 2, could this be delegated to a specialized "Content Admin" role? Add to TODO.

8. **Past paper copyright handling.** AI cites sources but generates paraphrased content. **Question:** what's the legal review SLA for the first AI-generated framework? Recommendation: 14-day legal review for first 1-2 frameworks; subsequent frameworks fast-tracked once template is established.

9. **Framework cost overflow handling.** $10 per refresh; 4x per year. **Question:** what's the absolute max framework count we can support? Recommendation: at $400/year operational cost for 10 frameworks, scaling to 25 frameworks = $1000/year. Soft cap at 25; beyond requires explicit budget approval.

10. **Migration mid-flight user-facing UX.** **Question:** how long is "few minutes" for a migration? Recommendation: <5 minutes for a single student migration. Display estimated time in 503 response.

11. **Graduation grace window — student-configurable?** **Question:** can a student opt to migrate earlier (e.g., immediately after graduation)? Recommendation: yes — "Migrate me to Independent now" button visible after GRADUATED, but with explicit confirmation step (one-way action). Useful for students who want to declutter / move on.

12. **Held-back students — what happens to their data?** A Grade 12 student excluded from the graduating cohort and held back. **Question:** their school data continues as normal? Recommendation: yes — they re-enroll in Grade 12 for the new session; old data attributed to previous session.

13. **Migration of Phase 6 ML model state.** Cognitive DNA + predictions + spaced-rep state migrate. **Question:** does the ML training scope include independent tenant after migration (Phase 2 ML per TODO)? Recommendation: yes — independent tenant Cognitive DNA contributes to ML training when Phase 2 happens, with appropriate consent.

14. **Audit trail of migration.** **Question:** is the migration event audit-logged? Recommendation: YES — student account migration is a state-changing event with PII implications; audit log retains for 7 years per §14.10.

---

## 9. Out of scope (for now)

- **Teacher discovery / connection request flow (#19, #20).** Removed for school students. (TODO: `phase-2-cross-grade-teacher-discovery`)
- **Multi-teacher dashboard (#22) as separate feature.** Subsumed by general dashboard. (TODO: not needed.)
- **Cross-school teacher-student connections.** (TODO: `phase-2-cross-school-connections`)
- **Self-service parent-initiated child deletion.** (TODO: `phase-2-parent-controlled-deletion`)
- **Independent student parent linking.** (TODO: `phase-2-independent-student-parent-linking`)
- **School → Independent migration on student's voluntary request before graduation.** (TODO: `phase-2-voluntary-migration`)
- **Student → student direct messaging.** Group study (Flow 11) only.
- **Sophisticated recommendation ML.** Discovery removed entirely.
- **Auto-deactivation of stale bulk-imported students.** (TODO: `phase-2-stale-account-cleanup`)
- **Adaptive question difficulty (CAT) for diagnostic.** (TODO: `phase-2-cat-diagnostic`)
- **Multi-script names.** (TODO: `phase-2-multi-script-names`)
- **Student ID verification.** Trust-based at launch. (TODO: `phase-2-id-verification`)
- **Visual change-set diff for framework v1 → v2.** (TODO: `phase-2-framework-version-diff`)
- **Content Admin role for framework approval.** Platform Admin only at launch. (TODO: `phase-2-content-admin-role`)
- **Custom school-level exam frameworks.** Platform-level only at launch. (TODO: `phase-2-custom-school-frameworks`)
- **Framework auto-selection by AI based on student behavior.** Manual selection at launch. (TODO: `phase-3-auto-framework-suggestion`)
- **Region-weighted recommendation algorithm for teachers / frameworks.** Static at launch.
- **Independent student diagnostic framework requirement bypass** ("Just learning" mode). (TODO: `phase-2-no-framework-independent`)
- **Subscription-tier caps on frameworks.** Schema only. (TODO: per Flow 13.)
- **Parent dashboard / parent view.** Lives in Flow 10.

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy
- **§3.16** — Independent users tenant model
- **§3.17** — Subscription cross-cutting attribute
- **§3.19** (NEW) — Exam Framework engine: Platform-level content, AI-research pipeline, quarterly refresh, approval workflow
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations
- **§4.21** — Dual Alembic heads
- **§5.1-5.7, §5.9, §5.10** — API design + Idempotency + If-Match
- **§5.11** — Bulk export endpoints
- **§6.7** — Dependency primitives
- **§6.13** — ParentChildLink opt-in pattern
- **§6.19** — Permission inheritance
- **§6.20** — Independent user signup
- **§7.12** — Pattern A agentic RAG (used by Exam Framework research agent)
- **§8.21** (NEW) — Exam Framework quarterly refresh agent: web search via SearXNG + LLM synthesis + Platform Admin approval gate
- **§9** — NATS events: `student.onboarded`, `parent.linked`, `parent.revoked`, `student.enrolled`, `student.unenrolled`, `student.graduated`, `student.migrated_to_independent`, `diagnostic.completed`, `framework.research_complete`, `framework.published`, `framework.deprecated`, `mode.changed`, `data_export.ready`, `deletion.requested`, `deletion.completed`
- **§9.21** — Notification namespaces (`account`, `connections`, `lectures`, `self_study`, `system`)
- **§10.3-10.5** — Celery tasks: data export, delayed deletion (30 days), graduation migration, framework refresh
- **§10.6** — Beat schedule: `framework.refresh_quarterly` (per framework), `graduation.migrate_eligible_students` (daily check), `parent_link.expire_sweep` (daily), `unlinked_parent.auto_suspend_sweep` (daily)
- **§13** — i18n for all onboarding text + notification templates
- **§14.10** — Audit log for: parent link state, mode changes, data export, deletion requests, graduation events, migration events, framework approval events

### Data model sketch

```
# In school schema:
student_profiles
  user_id (PK, FK), name, grade (auto-set from enrollment), language_preference,
  dob (nullable), avatar_key (nullable), onboarding_state (enum),
  is_graduated (bool, default false), graduated_at (nullable),
  migrated_out (bool, default false), migrated_at (nullable),
  created_at, updated_at, deleted_at

parent_profiles
  user_id (PK, FK), name, language_preference,
  is_email_verified (bool), unlinked_since (nullable),
  created_at, updated_at

parent_child_links
  id (uuidv7), parent_user_id (FK), student_user_id (FK),
  status (enum), requested_at, approved_at, revoked_at, rejected_count
  UNIQUE (parent_user_id, student_user_id)

student_framework_selections
  id (uuidv7), student_user_id (FK), framework_id (FK to platform table),
  selected_version (FK to framework_study_plans), selected_at, dropped_at,
  status (enum: active/dropped)

exam_selections
  id (uuidv7), student_user_id (FK), exam_date,
  primary_framework_id (nullable FK; redundant with framework_selections for fast lookup),
  created_at, updated_at

mode_selections
  id (uuidv7), student_user_id (FK), mode (enum: lecture/self_study),
  switched_at, prev_mode

diagnostic_attempts
  id (uuidv7), student_user_id (FK), subject_id (nullable FK, for school students),
  framework_id (nullable FK, for independent students),
  status (enum), started_at, completed_at, question_ids_jsonb, results_jsonb,
  contributes_to_cognitive_dna (bool)

data_rights_requests
  id (uuidv7), user_id (FK), type (enum: export/deletion),
  status (enum), requested_at, ready_at, expires_at, deletion_scheduled_at,
  completed_at, file_key (nullable MinIO)

graduation_migration_log
  id (uuidv7), student_user_id (FK), graduated_at, migration_scheduled_at,
  migration_attempts (int), migration_status (enum: pending/in_progress/succeeded/failed),
  last_error (nullable text), migrated_at (nullable)

# Platform-level tables (in school schema; visible to all schools):
exam_frameworks
  id (uuidv7), name, exam_target_name, region, target_grade_range (int[]),
  language, created_by_platform_admin_id, status (enum: draft/researching/pending_approval/published/refreshing/deprecated),
  current_version_id (nullable FK), created_at, updated_at, deprecated_at

framework_study_plans (versioned)
  id (uuidv7), framework_id (FK), version_number,
  content_jsonb (the full plan: topics, pacing, strategy, sources),
  sources_cited_jsonb, ai_generation_cost_usd, ai_model_used,
  status (enum: generating/pending_approval/approved/rejected/deprecated),
  generated_at, approved_at, approved_by_user_id, deprecated_at

framework_research_jobs
  id (uuidv7), framework_id (FK), version_target,
  status (enum), started_at, completed_at, cost_usd, sources_found,
  error_message (nullable)

# In independent schema:
independent_student_profiles
  user_id (PK, FK), name, grade_level (self-set), language_preference,
  primary_framework_id (FK to platform exam_frameworks table — shared platform data),
  dob (nullable), is_profile_complete (bool),
  is_migrated_from_school (bool, default false), migrated_from_school_id (nullable),
  created_at, updated_at, deleted_at

# (independent versions of: student_framework_selections, exam_selections,
#  diagnostic_attempts, data_rights_requests — same structure)
```

---

## 11. Acceptance criteria

### School Student onboarding
- ✅ First login → forced through PROFILE_BASIC (name + language + ToS only)
- ✅ Optional fields surface in "complete your profile" banner; can be deferred
- ✅ Mode selection mandatory before READY_TO_STUDY
- ✅ Exam framework + diagnostic optional for school students
- ✅ Onboarding renders in all 4 languages with RTL
- ✅ No teacher discovery UI (#19/#20 removed)
- ✅ Bulk-imported students hit same onboarding flow on first login

### Independent Student onboarding
- ✅ Public signup at `/independent/signup` creates user in `independent` tenant
- ✅ Authentik property mapper assigns `tenant_type=independent`
- ✅ Email verification before login
- ✅ Exam framework REQUIRED at signup (not deferrable)
- ✅ First login → minimal profile (confirm name + language)
- ✅ JWT routes to independent schema repository
- ✅ Independent cannot access school endpoints (404)
- ✅ Mode Switcher UI not exposed; locked to Self-Study
- ✅ Diagnostic available (per-framework)

### Parent linking (#10)
- ✅ Parent self-registration creates PARENT_REGISTERED user
- ✅ Email verification required
- ✅ Parent → student link request requires student approval (§6.13 opt-in)
- ✅ Both can revoke; access removed immediately
- ✅ 7-day TTL on pending; 3-rejection → 30-day block
- ✅ Cross-tenant denial: parent reads non-linked student → 404
- ✅ Parent attempts link to independent student → blocked
- ✅ Unlinked parent 90-day auto-suspend
- ✅ Parent auto-severed at student migration → email notification
- ✅ NATS events `parent.linked`, `parent.revoked` published

### Grade enrollment & teacher visibility
- ✅ Student enrolled into Grade auto-gets Grade's teacher assignments
- ✅ Dashboard renders teachers without student initiating discovery
- ✅ Coordinator unenrolls → relationships removed; historical retained
- ✅ Student API for "send connection request" returns 404

### Exam Framework (NEW)
- ✅ Platform Admin creates framework definition; status starts DRAFT
- ✅ Trigger AI research → research_job runs Pattern A agent (web search + LLM synthesis)
- ✅ AI completes → framework.research_complete event + Platform Admin notification (`system.framework_research_complete`)
- ✅ Platform Admin approves → status PUBLISHED v1; visible to students
- ✅ Platform Admin rejects → status RESEARCH_FAILED; option to regenerate
- ✅ Quarterly refresh task `framework.refresh_quarterly` fires per framework at 90-day intervals
- ✅ v2 generated; pending approval; students on v1 get banner on approval
- ✅ Student switches v1 → v2: progress retained, pacing recalibrates
- ✅ Deprecated framework: existing students grandfathered; new selections blocked
- ✅ AI research cost ceiling ($10) enforced: task halts + admin notified
- ✅ Multi-framework student: dashboard aggregates topics; overlaps deduplicated
- ✅ Region-mismatch warning shown but allowed
- ✅ Framework selection contributes to AI personalization (Flow 6 #61, Flow 9)

### Diagnostic (#51) — both types per v3
- ✅ School student: per-subject diagnostic (15-25 Q)
- ✅ Independent student: per-framework diagnostic (15-25 Q, framework-calibrated)
- ✅ Question source: Question Bank where available (Flow 9 dependency), LLM fallback
- ✅ Resume within 7 days; retake blocked within 30 days
- ✅ Results framed as coaching language (no grades)
- ✅ Completion seeds Cognitive DNA (Flow 9 #83)
- ✅ NATS event `diagnostic.completed` published
- ✅ Independent diagnostic stored in independent schema

### Exam date (#52)
- ✅ Past rejected; > 5-year warning
- ✅ 30-days-out reminder to student + parents
- ✅ Passed: prompt to set new

### Mode switching (#53)
- ✅ School student mode switch instant
- ✅ AI personalization adapts (Flow 6 #61)
- ✅ Independent: no switcher; locked
- ✅ NATS event `mode.changed` for school students

### Data rights (#15) — both types
- ✅ Export ≤ 24 hours; ZIP with JSON + PDF + CSV
- ✅ Deletion 30-day grace; cancellable
- ✅ Deletion preserves anonymized analytics; purges PII
- ✅ Audit log retains hashed identifier + action + date for 7 years
- ✅ Linked parents auto-unlinked on student deletion
- ✅ Works in both schemas

### Graduation lifecycle (REWRITTEN per v3)
- ✅ Grade 12 promotion via Flow 2 approval → student flagged GRADUATED
- ✅ Graduated student: school-mode-readonly; self-study-mode-fully-accessible
- ✅ Linked parents retain access during 6-month window
- ✅ 30-day pre-migration reminder + 7-day reminder + data export prompt
- ✅ Celery beat `graduation.migrate_eligible_students` runs daily
- ✅ Per-student migration task: atomic transaction; copies data → independent schema; updates auth claim; marks school records migrated_out
- ✅ Migration completes: student logs into independent tenant with same credentials
- ✅ Lecture Mode UI disappears post-migration
- ✅ Parent links auto-severed at migration; parents notified
- ✅ School Flow 11 dashboards show alumnus in "Migrated" status with anonymized name
- ✅ Migration task failure 5x → Platform Admin notified; student stays in read-only state
- ✅ Migration mid-flight login attempts: 503 with "Migration in progress" message
- ✅ Audit log entry per migration with hashed identifiers per §14.10
- ✅ Student-initiated early migration: explicit confirmation, same atomic flow
- ✅ NATS event `student.migrated_to_independent` published

### Permissions
- ✅ `require_parent_of(student_id)` rejects unlinked parent (404)
- ✅ Cross-tenant student reads return 404
- ✅ Framework operations restricted to Platform Admin
- ✅ District / Platform Admin inherit per §6.19

### Notifications
- ✅ Template keys in correct namespaces (`account`, `connections`, `lectures`, `self_study`, `system`)
- ✅ Per-feature notification boards; global panel shows aggregates
- ✅ All 4 languages; no `__TODO__` in production
- ✅ Cannot be turned off

### i18n
- ✅ All onboarding + notifications in en/ur/sd/ps
- ✅ RTL renders correctly

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v2 → v3:**
- Profile mandatory fields trimmed to name + language + ToS (per v3 feedback Q1)
- Independent students get diagnostic at launch (per v3 feedback Q3)
- **NEW: Exam Framework as AI-generated study plan engine** (per v3 feedback Q5). Pattern-A agentic LLM workflow does web research → produces study plan → Platform Admin approval → published. Quarterly refresh. Multi-framework support. Layered on Self-Study Mode primarily; supplemental in Lecture Mode.
- **REWRITTEN graduation lifecycle**: GRADUATED → 6-month read-only school window → auto-migrate to independent tenant with full data continuity (per v3 feedback graduation rewrite). Configurable via `GRADUATION_GRACE_DAYS` env var.
- Independent student diagnostic added; calibrated per-framework
- Parent links auto-severed at graduation migration
- New ARCHITECTURE refs: §3.19 (framework engine), §8.21 (refresh agent)
- New Celery beat tasks: `framework.refresh_quarterly`, `graduation.migrate_eligible_students`
- New env var: `GRADUATION_GRACE_DAYS` (default 180)

**Change log v1 → v2:** (retained for reference)
- Independent students added, locked to Self-Study Mode
- #19/#20/#22 removed for school students; replaced by automatic Grade enrollment
- Permission inheritance §6.19 applied throughout
- Notification namespaces per Flow 1 Q13
- Parent linking limited to school students at launch
- Bulk import moved to Coordinator

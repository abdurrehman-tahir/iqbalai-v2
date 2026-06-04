# M-16 — Next-Day Review Loop

**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-195 through T-208
**Spec source:** `flow-7-next-day-review.md` v1 §3.1-§3.8, features #39, #40, #44, #45, #46, #47, #48, #49

## Goal

Closes the teaching loop. Overnight, the system aggregates the questions students asked while studying a lecture (the events M-12 emits and M-14 stores), clusters them per Grade-Subject offering, classifies which clusters are high-frequency or critical, generates a targeted **mini-lecture** for each qualifying cluster, and delivers the teacher a single **review card** at 06:00 with an AI summary, a coaching reflective prompt, drill-downs, and action buttons. The teacher can publish the mini-lecture to exactly the students who struggled, edit the main lecture, reply to students, or dismiss. Each review is a permanent child record of its lecture.

**This milestone consumes hooks from earlier flows** (surfaced by the pre-draft audit): M-09's `lecture_type='mini'` + `parent_lecture_id` (data model ready), M-10's `teacher_ai_memory.category` (extended here with `reflective_response_pattern`), M-12's content-element-tagged + misconception/knowledge_gap-classified questions, and the M-14 `student_events` analytics store (the aggregator reads it).

**Scope boundary:** the nightly pipeline + the teacher review surface + targeted distribution + child-record. It **reuses** the Flow 5 generation (T-116) and scoring (T-134) pipelines as a `mini` variant — it does **not** rebuild them.

**Three BLOCKED-HOOKs** (deferrals to still-blocked flows — see tickets):
- "Schedule Group Study" action button → Flow 11 / M-20 (present but disabled until Flow 11 ships).
- Parent notification on mini-lecture assignment → Flow 10 / M-19 (recipients notified now; parent read-only notification when Flow 10 ships).
- Review clusters feed Cognitive DNA → Flow 9 / M-18 (clusters persisted; the DNA consumer reads them when Flow 9 ships).

**Demo at milestone end:**
- At 23:00 Karachi the `review.aggregate_nightly` beat fires one isolated task per active school; a slow school doesn't block others
- The task reads the day's questions (privacy #72 excludes opted-out students), clusters them (cosine ≥0.80) within lecture/paragraph/source-chunk buckets, and classifies each cluster by frequency (≥3 students or 25% of roster) + LLM criticality (0-10, threshold 7)
- Each qualifying cluster gets a mini-lecture (Flow 5 pipeline, `lecture_type=mini`, web-fallback off, 800-1200 words, ≤$0.50), scored on the 7 dimensions with Depth+Alignment ×1.5
- By 05:00 all reviews are built (breach → Platform-Admin alert); at 06:00 the teacher is notified
- Teacher opens a single review card: AI summary, a reflective coaching question (voice/text), High-Frequency + Critical cluster tabs, mini-lecture preview, action buttons
- Drill-down shows each student's exact wording (teacher-only); teacher replies to a cluster, skips another, then publishes the mini-lecture → it goes ONLY to the students who triggered it
- The review appears permanently on the lecture's "Reviews" tab

---

## T-195 — Review data model + `teacher_ai_memory` reflective extension

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.1, §3.6, §3.8 (tables: `lecture_reviews`, `review_replies`, `skipped_clusters`, `review_classification_failures` DLQ)

### ARCH source
- `ARCHITECTURE.md` §4 (DB), §3.16 (school-tenant only), §4.12 (migrations)

### Depends on
- T-113 (`lectures`, `lecture_type`, `parent_lecture_id`, M-09), T-129 (`teacher_ai_memory`, M-10)

### What this ticket builds

**Backend:** Migrations (school schema; mini-lectures excluded from independent tenant): `lecture_reviews {id, lecture_id, gso_id, review_date, ai_summary, reflective_prompt, status, pending_action bool, dismissed_at, acted_actions jsonb, mini_lecture_id, created_at}`; `review_replies {id, review_id, cluster_id, student_user_id, body, created_at}`; `skipped_clusters {id, review_id, cluster_ref, skipped_at}`; `review_classification_failures {id, school_id, gso_id, cluster_ref, error, failed_at}` (DLQ). Extend `teacher_ai_memory` with the `reflective_response_pattern` category (the column is already extensible from M-10 T-129).

### Acceptance (demo script)

1. [ ] All four tables exist (school schema), tenant-tagged
2. [ ] `lecture_reviews.acted_actions` is an array (multiple actions per review)
3. [ ] `lecture_reviews` links to parent lecture via `lecture_id`
4. [ ] `teacher_ai_memory` accepts the `reflective_response_pattern` category (no schema change needed beyond the enum value)
5. [ ] DLQ table ready for cluster-level failures

### Out of scope
- The pipeline (T-196+)

### Notes / known gotchas
- BLOCKED-HOOK: review clusters / `lecture_reviews` feed Cognitive DNA → Flow 9 / M-18 (clusters + reviews persisted here; the DNA consumer reads them when Flow 9 ships — same DNA path as the M-14 `student_events` hook).

---

## T-196 — Overnight aggregation beat + per-school task (#40, #44)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.1 (23:00 Karachi beat; one isolated task per active school; reads day's questions; privacy #72 filter)

### ARCH source
- `ARCHITECTURE.md` §10 (Celery beat `review.aggregate_nightly`), §4 (`student_events`), §3.16 (school-tenant), §9 (event source)

### Depends on
- T-195 (review model), T-174 (`student_events` store, M-14), T-156 (content-element-tagged questions, M-12)

### What this ticket builds

**Backend:** The `review.aggregate_nightly` Celery beat at 23:00 Asia/Karachi. Fans out **one isolated task per active school** (a slow/failing school never blocks others). Each task reads the day's questions from `student_events` filtered to `tenant_type='school'`, the teacher's Grade-Subject offerings, `student_self_study_privacy='share'`, and **excludes #72 opted-out students**. Produces the per-(lecture, paragraph, source_chunk) question buckets that clustering (T-197) consumes.

### Acceptance (demo script)

1. [ ] Beat fires at 23:00 Asia/Karachi; one task per active school
2. [ ] A failing school's task doesn't block other schools
3. [ ] Reads the day's questions from `student_events`, scoped to school + teacher GSOs
4. [ ] #72 opted-out students excluded from aggregation
5. [ ] Buckets keyed by (lecture, paragraph, source_chunk)

### Out of scope
- Clustering/classification (T-197)

---

## T-197 — Cluster + classify + DLQ (#40, #44)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.1 (cluster cosine ≥0.80; frequency ≥3 students or 25% roster; criticality LLM 0-10 threshold 7; cluster-level failure → DLQ)

### ARCH source
- `ARCHITECTURE.md` §7.3 (BGE-M3 embeddings for cosine), §8.6 (criticality classifier typed prompt), §4 (DLQ table)

### Depends on
- T-196 (question buckets)

### What this ticket builds

**Backend:** Within each bucket, cluster questions by embedding cosine **≥0.80**. Classify each cluster: **frequency** (`freq_score`; qualifies at ≥3 students OR 25% of the GSO roster) and **criticality** (LLM-scored 0-10, threshold 7). Clusters qualifying on either dimension proceed to mini-lecture generation. A cluster that fails classification writes to the `review_classification_failures` DLQ — the rest of the review still ships (graceful degradation).

### Acceptance (demo script)

1. [ ] Questions cluster at cosine ≥0.80 within their bucket
2. [ ] Frequency qualifies at ≥3 students or 25% roster
3. [ ] Criticality LLM-scored 0-10; threshold 7
4. [ ] A cluster-level failure → DLQ row; review still ships
5. [ ] Qualifying clusters flagged for mini-lecture generation

### Out of scope
- Mini-lecture generation (T-198)

---

## T-198 — Mini-lecture generation (#40)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.4 (reuse Flow 5 pipeline; `lecture_type=mini`; web-fallback DISABLED; 800-1200 words; $0.50 ceiling; `mini_lecture.generated` event)

### ARCH source
- `ARCHITECTURE.md` §7 (Flow 5 generation pipeline — reuse), §8.6 (shorter mini prompt), §9 (`mini_lecture.generated`)

### Depends on
- T-197 (qualifying clusters), T-116 (Flow 5 generation pipeline, M-09)

### What this ticket builds

**Backend:** Generate one mini-lecture per qualifying cluster by **reusing the Flow 5 generation pipeline** (T-116) with `lecture_type=mini`: a shorter prompt, per-paragraph source attribution preserved, **web-search fallback disabled** (mini-lectures stay anchored to in-scope curriculum + references). Word target 800-1200; hard cost ceiling $0.50/mini-lecture. Sets `parent_lecture_id` to the source lecture. Publishes `mini_lecture.generated`.

### Acceptance (demo script)

1. [ ] One mini-lecture per qualifying cluster, `lecture_type=mini`, `parent_lecture_id` set
2. [ ] Reuses Flow 5 pipeline (not a new generator)
3. [ ] Web-search fallback disabled; source attribution preserved
4. [ ] 800-1200 words; cost ≤ $0.50 (enforced)
5. [ ] `mini_lecture.generated` emitted

### Out of scope
- Scoring (T-199); distribution (T-204)

---

## T-199 — Mini-lecture scoring (#39)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.5 (Flow 5 §3.6 7-dim scoring, Depth + Alignment ×1.5, max 60; originality vs global incl. other mini-lectures; excluded from independent tenant)

### ARCH source
- `ARCHITECTURE.md` §7.10 (`SCORING_MODEL`), §7.15 (originality), §4 (`lecture_versions.scores_jsonb`)

### Depends on
- T-198 (mini-lecture), T-134 (7-dim scoring, M-10), T-135 (originality, M-10)

### What this ticket builds

**Backend:** Run the same 7-dimension Flow 5 scoring (T-134) on each mini-lecture, with **Depth and Alignment weighted 1.5×** (max 60 vs a main lecture's 55). Store in `lecture_versions.scores_jsonb`; the admin dashboard distinguishes mini from main via `lecture_type`. Originality (T-135) runs against the global corpus including other mini-lectures. Mini-lectures are excluded from the independent tenant.

### Acceptance (demo script)

1. [ ] 7-dim scoring runs; Depth + Alignment ×1.5; max 60
2. [ ] Scores stored in `lecture_versions.scores_jsonb`; admin distinguishes via `lecture_type`
3. [ ] Originality runs vs global corpus incl. mini-lectures
4. [ ] Reuses the M-10 scoring pipeline (not new)
5. [ ] Independent tenant excluded

### Out of scope
- Changing the M-10 scoring dimensions

---

## T-200 — Review card assembly + SLA + 06:00 notify

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.1 (assemble per-GSO card; 05:00 SLA breach → admin alert; 06:00 notify never earlier)

### ARCH source
- `ARCHITECTURE.md` §8.6 (AI summary + reflective prompt prompts), §9.21 (`lectures.next_day_review_ready`, `system` SLA alert), §10 (scheduled notify)

### Depends on
- T-197 (classified clusters), T-198/T-199 (mini-lecture + score)

### What this ticket builds

**Backend:** Assemble one `lecture_reviews` row per Grade-Subject offering: AI summary (2-3 sentences), the reflective prompt (generated in T-202), High-Frequency + Critical cluster lists, and the mini-lecture reference. **SLA:** all schools complete by 05:00 Asia/Karachi; a breach raises a Platform-Admin alert (`system` namespace). The teacher notification (`lectures.next_day_review_ready`) is scheduled for **06:00 Karachi — never earlier**.

### Acceptance (demo script)

1. [ ] One review row per GSO with summary + cluster lists + mini-lecture ref
2. [ ] 05:00 SLA breach → Platform-Admin alert
3. [ ] Teacher notified at 06:00, never earlier
4. [ ] Review built even if some clusters hit the DLQ
5. [ ] `pending_action` set until the teacher engages

### Out of scope
- The card UI (T-201); reflective-prompt generation internals (T-202)

---

## T-201 — Review card UI (#45)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.2, §3.3 (locked card layout)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §13 (i18n/RTL), §6.19 (teacher access)

### Depends on
- T-200 (assembled review)

### What this ticket builds

**Frontend:** The review card at the locked layout — header (Grade/Subject/topic + generated timestamp), AI summary, reflective question block (with text + voice response inputs), three columns (High Frequency / Critical / Mini-Lecture Preview with first ~200 chars + Open-full-draft + Regenerate), and the action-button row. Reached from Teacher Dashboard → Reviews tab or a deep link. RTL-aware.

### Acceptance (demo script)

1. [ ] Card renders the locked layout (summary, reflective Q, 3 columns, actions)
2. [ ] Mini-lecture preview shows first ~200 chars + open-full + regenerate
3. [ ] Reachable from Reviews tab + deep link
4. [ ] RTL-correct, i18n
5. [ ] Closing sets/keeps `pending_action` if untouched

### Out of scope
- Drill-down (T-203); action wiring (T-205)

---

## T-202 — Reflective prompt (#49)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.3 + #49 (LLM coaching question about the teacher's own practice; never grading; voice/text response → `teacher_ai_memory` reflective_response_pattern)

### ARCH source
- `ARCHITECTURE.md` §8.6 (reflective-prompt typed prompt), §4 (`teacher_ai_memory`), STACK_LOCK §4 (faster-whisper for voice)

### Depends on
- T-200 (review), T-201 (card), T-195 (`teacher_ai_memory` category)

### What this ticket builds

**Backend + frontend:** Generate the reflective question — an LLM coaching prompt about the teacher's *own teaching practice* (e.g. "would a worked example with everyday objects make the action-reaction pair more concrete?"), strictly framed as **coaching, never grading** (CXO rule). The teacher answers by text or voice (faster-whisper); the response + pattern are written to `teacher_ai_memory` under the `reflective_response_pattern` category, informing future coaching (the M-10 Innovation Record loop).

### Acceptance (demo script)

1. [ ] Reflective question generated per review, grounded in that review's clusters
2. [ ] Framing is coaching, never grading/evaluative
3. [ ] Teacher answers by text or voice
4. [ ] Response stored in `teacher_ai_memory` as `reflective_response_pattern`
5. [ ] Feeds future coaching (M-10 Innovation Record)

### Out of scope
- Surfacing reflection analytics (Phase 2)

---

## T-203 — Drill-down modal + reply + skip (#45, #46)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.6 (per-cluster modal: aggregated + per-student exact wording, teacher-only names; reply via hybrid widget → `review_replies`; skip → `skipped_clusters`)

### ARCH source
- `ARCHITECTURE.md` §6.19 (teacher-only student names; Coordinator/Admin aggregate), §12 (hybrid widget #57 reuse), §4 (replies/skips tables)

### Depends on
- T-201 (card), T-197 (clusters), T-155 (hybrid widget, M-12)

### What this ticket builds

**Frontend + backend:** A per-cluster drill-down modal — aggregated wording, each student's exact wording, and a link to the content element. **Student names visible to the teacher only**; Coordinator/Admin see aggregate-only (§6.19). From the modal the teacher can reply to specific students (creates `review_replies`, reusing the hybrid widget T-155) or skip a cluster (writes `skipped_clusters`, excluding it from mini-lecture regeneration).

### Acceptance (demo script)

1. [ ] Modal shows aggregated + per-student exact wording + content-element link
2. [ ] Student names teacher-only; Coordinator/Admin aggregate-only
3. [ ] Reply creates `review_replies` via the hybrid widget
4. [ ] Skip writes `skipped_clusters` + excludes from regeneration
5. [ ] i18n / RTL

### Out of scope
- Action buttons (T-205)

---

## T-204 — Targeted distribution (#47)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.7 (recipients = union of triggering students; `lecture_assignments` per recipient; `lectures.mini_lecture_assigned`; no auto-quiz; cross-grade blocked; all-unenrolled → `PRECONDITION_FAILED`; parents per Flow 10)

### ARCH source
- `ARCHITECTURE.md` §5 (API), §9.21 (`lectures.mini_lecture_assigned`), §3.18 (enrollment)

### Depends on
- T-198 (mini-lecture), T-197 (cluster→student mapping)

### What this ticket builds

**Backend:** At publish time, compute the recipient set as the **union of students whose questions triggered the published clusters** (never broadcast). Create a `lecture_assignments` row per recipient; notify recipients via `lectures.mini_lecture_assigned`. **Auto-quiz is NOT generated** for mini-lectures (Flow 5 #23b skipped). **Cross-grade linking is blocked** at the API for mini-lectures. If all recipients are unenrolled → block with `PRECONDITION_FAILED`.

### Acceptance (demo script)

1. [ ] Recipients = union of triggering students only (no broadcast)
2. [ ] `lecture_assignments` per recipient; `lectures.mini_lecture_assigned` fired
3. [ ] No auto-quiz generated for mini-lectures
4. [ ] Cross-grade linking blocked at API for mini-lectures
5. [ ] All-unenrolled → `PRECONDITION_FAILED`

### Out of scope
- Parent notification (BLOCKED-HOOK below); action-button wiring (T-205)

### Notes / known gotchas
- BLOCKED-HOOK: parent notification on mini-lecture assignment → Flow 10 / M-19 (recipients notified now; parent read-only notification wired when Flow 10 ships).

---

## T-205 — Action buttons (#46)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.6 (Publish Mini-Lecture → §3.7; Edit Main Lecture → Flow 5 edit + banner; Schedule Group Study → Flow 11 (disabled); Dismiss → recoverable; `acted_actions[]`)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), Flow 5 edit mode (M-10)

### Depends on
- T-201 (card), T-204 (distribution), T-130 (Flow 5 edit mode, M-10)

### What this ticket builds

**Frontend + backend:** Wire the action buttons, each pre-filled with context. **Publish Mini-Lecture** → T-204 targeted distribution. **Edit Main Lecture** → opens Flow 5 edit mode (T-130) with a context banner. **Schedule Group Study** → opens the Flow 11 scheduler pre-filled, **disabled until Flow 11 ships**. **Dismiss without action** → recoverable (`dismissed_at` set, re-openable). Multiple actions allowed per review (`acted_actions[]` array).

### Acceptance (demo script)

1. [ ] Publish → targeted distribution (T-204)
2. [ ] Edit Main Lecture → Flow 5 edit with context banner
3. [ ] Schedule Group Study → present but disabled (Flow 11 pending)
4. [ ] Dismiss → recoverable (`dismissed_at`, re-openable)
5. [ ] Multiple actions recorded in `acted_actions[]`

### Out of scope
- Building the Flow 11 scheduler

### Notes / known gotchas
- BLOCKED-HOOK: "Schedule Group Study" action → Flow 11 / M-20 (button present but disabled until the Flow 11 scheduler exists).

---

## T-206 — Review-as-child-record (#48)

**Layer:** 6
**Milestone:** M-16
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.8 (review = child record of lecture; Reviews tab chronological all-time; never expire; feeds #38 admin metrics)

### ARCH source
- `ARCHITECTURE.md` §4 (`lecture_reviews.lecture_id`), §12 (Reviews tab), Flow 5 #38 (admin dashboard, M-10)

### Depends on
- T-195 (`lecture_reviews`), T-200 (assembled reviews)

### What this ticket builds

**Frontend + backend:** The lecture's "Reviews" tab — full chronological history (all time) of that lecture's reviews; reviews never expire; archived parent lectures retain reviews as read-only. Aggregate metrics ("pending reviews per teacher", "days to act") feed the Flow 5 #38 admin dashboard (T-139).

### Acceptance (demo script)

1. [ ] Lecture "Reviews" tab shows full chronological history
2. [ ] Reviews never expire; archived lecture keeps them read-only
3. [ ] "Pending reviews per teacher" + "days to act" feed the #38 admin dashboard
4. [ ] Child-record linkage via `lecture_id`
5. [ ] Permissions per §6.19

### Out of scope
- New admin dashboard views (reuses M-10 #38)

---

## T-207 — Permissions + privacy + notifications + i18n

**Layer:** 6
**Milestone:** M-16
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §4 (permissions matrix), §7 (notifications)

### ARCH source
- `ARCHITECTURE.md` §6.19 (permissions), §9.21 (`lectures` + `system` namespaces), §14.10 (audit), §13 (i18n)

### Depends on
- T-195 through T-206

### What this ticket builds

**Backend:** Enforce the Flow 7 permissions matrix (teacher sees student names; Coordinator/Admin aggregate; #72 throughout). Notifications: `lectures.next_day_review_ready`, `lectures.mini_lecture_assigned`, and the `system` SLA-breach + DLQ alerts. Audit dismiss/publish/skip + admin overrides. i18n — review card, reflective prompt, mini-lecture, notifications in en/ur/sd/ps (RTL); no `__TODO__`.

### Acceptance (demo script)

1. [ ] Permissions matrix enforced (teacher-only names; aggregate for higher roles)
2. [ ] All notifications in correct namespaces, 4 languages
3. [ ] SLA breach + DLQ alerts to Platform Admin
4. [ ] Dismiss/publish/skip + overrides audit-logged
5. [ ] No `__TODO__` strings

### Out of scope
- Anything beyond M-16 scope

---

## T-208 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-16
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-7-next-day-review.md` §3.1-§3.8

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-195 through T-207

### What this ticket builds

**Test + PR:** Automated E2E (LLM / embeddings mocked; Celery beat time-warped; no live network) — seed a day of student questions across students → run `review.aggregate_nightly` for a school → cluster (cosine) + classify (freq + criticality) → a failing cluster → DLQ, review still ships → mini-lecture generated (`lecture_type=mini`, web-fallback off, cost cap) + scored (Depth/Alignment ×1.5, max 60) → review card assembled, 05:00 SLA + 06:00 notify asserted → teacher drills down (names teacher-only), replies, skips a cluster → publishes → targeted distribution to triggering students only (no auto-quiz, cross-grade blocked) → review on the lecture's Reviews tab. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais; merge-commit to `staging`; tickets = commits).

### Acceptance (demo script)

1. [ ] E2E green (LLM/embeddings mocked; beat time-warped; no live network)
2. [ ] Asserts cluster + classify + DLQ-graceful-degradation
3. [ ] Asserts mini-lecture gen (mini flags, cost cap) + scoring (×1.5, max 60)
4. [ ] Asserts SLA/notify timing + teacher-only names + targeted distribution
5. [ ] PR `milestone/M-16-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; merged

### Out of scope
- Anything beyond the M-16 ticket set

---

## Milestone notes

- **Closes the teaching loop** — consumes the M-12-emitted / M-14-stored student events + M-12 question classifications, and reuses the Flow 5 generation (T-116) + scoring (T-134) pipelines as a `mini` variant (no rebuild).
- **Consumes earlier hooks:** M-09 `lecture_type='mini'`/`parent_lecture_id`; M-10 `teacher_ai_memory` (+`reflective_response_pattern`); M-12 content-element tagging + classification; M-14 `student_events` store.
- **Overnight pipeline is per-school-isolated** (a slow school can't block others), DLQ-graceful (a failed cluster doesn't sink the review), SLA-bounded (05:00 build, 06:00 notify never earlier).
- **Mini-lecture discipline:** Flow 5 pipeline reused, web-fallback OFF, 800-1200 words, ≤$0.50, scored Depth/Alignment ×1.5 (max 60), no auto-quiz, cross-grade blocked, independent tenant excluded.
- **Targeted, never broadcast** — recipients are exactly the students whose questions triggered the published clusters.
- **Coaching, never grading** — the reflective prompt is about the teacher's practice, framed as coaching (CXO rule); student names teacher-only; reviews never used to rank.
- **Three BLOCKED-HOOKs:** (T-205) Schedule Group Study → Flow 11 / M-20; (T-204) parent notification on assignment → Flow 10 / M-19; (T-195/T-206) review clusters feed Cognitive DNA → Flow 9 / M-18 (clusters persisted; DNA reads later).
- **Open questions:** built to the spec's launch recommendations (cosine 0.80, freq ≥3/25%, criticality threshold 7, 05:00/06:00 SLA), treated as decided per standing instruction.
- **Source flow:** Flow 7 v1 §3.1-§3.8 — drafted; relevant open questions have adopted launch recommendations (none blocking).

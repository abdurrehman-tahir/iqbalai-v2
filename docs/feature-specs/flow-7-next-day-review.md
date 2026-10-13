# Flow 7 — Next-Day Review Loop

**Status:** draft (v1)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-20
**Related ARCHITECTURE sections:** §3 (multi-tenancy — SCHOOL tenant only), §3.18 (Grade/Section/Subject — review unit is the Grade-Subject offering), §4 (DB), §4.21 (dual Alembic heads — writes to school schema only), §5 (API), §6.19 (permission inheritance), §7 (RAG — reuses Flow 5 Pattern S generation for the mini-lecture), §8 (LLM, esp. §8.6 typed prompts; clustering + criticality classification + reflective-prompt generation), §9 (NATS), §9.21 (notification namespaces), §10 (Celery), §10.6 (beat schedule — new task `review.aggregate_nightly`), §13 (i18n), §14.10 (audit log)
**Related feature specs:** `flow-5-teacher-creates-lecture.md` (mini-lecture is a `lecture_type=mini` variant reusing the main generation + 7-dimension scoring pipeline; "Edit Main Lecture" re-enters Flow 5 edit mode), `flow-6-student-studies-lecture.md` (the questions students ask there are the raw input to this review), `flow-8-self-study.md` (school self-study questions feed this review ONLY when student privacy #72=share), `flow-4-student-onboarding.md` (independent students excluded at the tenant filter), `flow-2-admin-coordinator-setup.md` (per-Grade-Subject offering as the review unit), `flow-9-ai-intelligence.md` (future — owns question bank, mistake tracking, spaced repetition; the clusters surfaced here feed it)
**v2 doc features covered:** #39, #40, #44, #45, #46, #47, #48, #49

---

## 1. Purpose

Overnight, the platform reads every question students asked their lectures that day, clusters them, and hands each teacher a single "Daily Review" card the next morning: *here's what your class struggled with, here's a ready-to-publish mini-lecture for it, and here's a coaching prompt to reflect on your teaching.* The teacher acts on it in minutes — publish the mini-lecture to just the students who need it, edit the main lecture, schedule a group study, or dismiss.

This flow owns the arc from **"the day's questions are aggregated at 23:00"** through **"the teacher is notified at 06:00 with a review card"** to **"a targeted mini-lecture is published to the triggering students."**

Critical foundations:

- **Overnight aggregation pipeline** (#40, #44) — Celery beat `review.aggregate_nightly` at 23:00 Asia/Karachi, one isolated task per active school; clusters the day's questions per Grade-Subject offering
- **Mini-lecture generation** (#40) — reuses the Flow 5 generation pipeline as a `lecture_type=mini` variant (shorter prompt, web-search fallback disabled)
- **Mini-lecture scoring** (#39) — the same Flow 5 §3.6 7-dimension scoring, with Depth + Alignment weighted 1.5×
- **Review card delivery** (#45, #49) — one card per Grade-Subject offering per school day; AI summary + reflective prompt + High-Frequency tab + Critical tab + mini-lecture preview + action buttons
- **Reflective prompt** (#49) — an LLM-generated coaching question about the teacher's own practice, framed as coaching, **never grading** (CXO rule); answerable by voice or text
- **Drill-down** (#45) — per-cluster modal showing aggregated wording + per-student exact wording; student names visible to the teacher only
- **Action buttons** (#46) — Publish Mini-Lecture / Edit Main Lecture / Schedule Group Study / Dismiss, each pre-filled with context
- **Targeted distribution** (#47) — the mini-lecture goes ONLY to the students whose questions triggered the cluster; never broadcast
- **Review-as-child-record** (#48) — each review is a permanent child record of its lecture, visible chronologically on the lecture's "Reviews" tab

**This flow is school-tenant only.** Independent students have no teacher, so there is no review loop; they are excluded at the tenant filter. Independent students' self-study questions never enter this pipeline.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Teacher** | The primary actor. Receives the daily review card per Grade-Subject offering, drills into clusters (sees individual student names), responds to the reflective prompt, and acts (publish mini-lecture, edit main lecture, schedule group study, dismiss). |
| **Coordinator (assigned scope)** | Per §6.19: view-only on review cards in scope, aggregate-only on cluster drill-down (no individual student names). Sees the aggregate "pending reviews" metric for scope. |
| **School Admin (own school)** | Per §6.19: view-only on review cards (school), aggregate-only drill-down. May override-publish / override-edit / re-trigger regeneration (all audit-logged). Sees the school-level "pending reviews" metric. |
| **District / Platform Admin** | Per §6.19: inherit aggregate review metrics in scope. Platform Admin monitors the overnight pipeline health + SLA (alerted on breach). |
| **Student (school)** | Indirect — their questions (from Flow 6 lectures, and Flow 8 self-study when #72=share) are the raw input. They receive the targeted mini-lecture if their question triggered it. No direct review surface. |
| **Independent Student / Teacher** | Excluded entirely — this flow's surfaces are unreachable for the independent tenant. |

---

## 3. Lifecycle

### 3.1 Overnight aggregation pipeline (#40, #44)

```
   23:00_KARACHI               (Celery beat `review.aggregate_nightly` fires)
       ↓ one isolated task per ACTIVE school (slow school never blocks others)
   AGGREGATING                 (read the day's questions; filter:
                                tenant_type='school', student_self_study_privacy='share',
                                current teacher's Grade-Subject offerings; privacy #72 excludes opted-out)
       ↓ cluster within (lecture, paragraph, source_chunk) buckets, cosine ≥ 0.80
   CLUSTERED
       ↓ classify each cluster
   CLASSIFIED                  (frequency: freq_score, ≥3 students or 25% of GSO roster;
                                criticality: LLM-scored 0-10, threshold 7)
       ↓ generate one mini-lecture per qualifying cluster (lecture_type=mini)
   MINI_LECTURE_READY          (reuses Flow 5 pipeline; scored per #39)
       ↓ assemble the review card per Grade-Subject offering
   REVIEW_BUILT
       ↓ (SLA: all schools complete by 05:00 Asia/Karachi; breach → Platform Admin alert)
   06:00_KARACHI               (scheduled notification fires — never earlier)
   TEACHER_NOTIFIED            (push + in-app per `lectures.next_day_review_ready`)
```

A per-school task that fails at the cluster level writes to the `review_classification_failures` DLQ table; the rest of the review still ships.

### 3.2 The teacher's review surface

```
   TEACHER_NOTIFIED            (push + in-app per `lectures.next_day_review_ready`)
       ↓ teacher opens review surface
   REVIEW_OPENED               (Teacher Dashboard → Reviews tab OR direct deep link)
   REVIEW_CARD_VISIBLE         (single card layout — see below)
       ↓ teacher reads + interacts
   ENGAGED                     (teacher drills down, takes actions per §3.6,
                                responds to reflection per #49)
       ↓ teacher closes
   CLOSED                      (review remains accessible from lecture's Reviews
                                tab per §3.8; pending_action flag set if untouched)
```

### 3.3 Locked layout of the review card

```
┌──────────────────────────────────────────────────────────┐
│ Daily Review — Grade 9 Physics (Newton's 3rd Law)          │
│ Generated 06:00, 20 May 2026                               │
├──────────────────────────────────────────────────────────┤
│ AI Summary (2-3 sentences)                                 │
│ Yesterday, 8 of 32 students struggled with the action-     │
│ reaction distinction in the rocket-propulsion example. 3   │
│ students asked critical questions revealing a foundational │
│ misconception about Newton's 3rd Law. A mini-lecture is    │
│ ready for review.                                          │
├──────────────────────────────────────────────────────────┤
│ ⓘ Reflective Question                                      │
│ "8 students struggled with the same diagram — would a      │
│  worked example with everyday objects (a person pushing a  │
│  wall) make the action-reaction pair more concrete?"       │
│ [ Type response ]  [ 🎤 Voice response ]                   │
├───────────────────┬───────────────────┬────────────────────┤
│ High Frequency     │ Critical          │ Mini-Lecture       │
│ (8 questions)      │ (3 questions)     │ Preview            │
│ [ Cluster 1 ▸ ]    │ [ Cluster A ▸ ]   │ [ first 200 chars  │
│ [ Cluster 2 ▸ ]    │ [ Cluster B ▸ ]   │  of mini-lecture ] │
│ [ Cluster 3 ▸ ]    │ [ Cluster C ▸ ]   │ [ Open full draft ]│
│ ...                │                   │ [ Regenerate ]     │
├──────────────────────────────────────────────────────────┤
│ Action Buttons                                             │
│ [ Publish Mini-Lecture ]  [ Edit Main Lecture ]            │
│ [ Schedule Group Study ]  [ Dismiss without action ]       │
└──────────────────────────────────────────────────────────┘
```

### 3.4 Mini-lecture generation (#40)

Reuses the Flow 5 generation pipeline; the only differences are the `lecture_type=mini` flag and a shorter prompt. Per-paragraph source attribution is preserved; web-search fallback is **disabled** (a mini-lecture must stay anchored to the curriculum + references already in scope). Word target 800-1200; cost ceiling $0.50 per mini-lecture. A `mini_lecture.generated` NATS event is published.

### 3.5 Mini-lecture scoring (#39)

The same 7-dimension Flow 5 §3.6 scoring pipeline runs, with **Depth and Alignment weighted 1.5×** (max score 60 vs a main lecture's 55). Scores are stored in the same `lecture_versions.scores_jsonb`; the admin dashboard distinguishes mini from main via `lecture_type`. The originality check (#33) runs against the global corpus, including other mini-lectures. Mini-lectures are excluded from the independent teacher tenant.

### 3.6 Drill-down + actions (#45, #46)

A per-cluster modal shows the aggregated wording, each student's exact wording, and a link to the content element. Student names are visible to the **teacher only**; Coordinator and Admin see aggregate-only. From the card the teacher can reply to specific students in a cluster (creates `review_replies` rows, uses the hybrid widget #57), or skip a cluster (writes `skipped_clusters`, excludes it from mini-lecture regeneration). Action buttons carry pre-filled context: "Publish Mini-Lecture" → §3.7 targeted distribution; "Edit Main Lecture" → opens Flow 5 edit mode with a context banner; "Schedule Group Study" → opens the Flow 11 scheduler pre-filled (disabled until Flow 11 ships); "Dismiss without action" → recoverable (`dismissed_at` set, re-openable). Multiple actions are allowed per review (`acted_actions[]` is an array).

### 3.7 Targeted distribution (#47)

The recipient set is the **union of the students whose questions triggered the published clusters**, computed at publish-time. A `lecture_assignments` row is created per recipient; recipients are notified via `lectures.mini_lecture_assigned`; parents of recipients are notified per Flow 10 (read-only). Auto-quiz is **not** generated for mini-lectures (Flow 5 #23b skipped). Cross-grade linking is **blocked** at the API for mini-lectures. If all recipients are unenrolled, publish is blocked with `PRECONDITION_FAILED`.

### 3.8 Review-as-child-record (#48)

Each review is a `lecture_reviews` row, linked to its parent lecture via `lecture_id`. The lecture's "Reviews" tab shows the full chronological history (all time). Reviews never expire; archived parent lectures retain their reviews as read-only. Aggregate metrics ("pending reviews per teacher", "days to act") feed the Flow 5 #38 admin dashboard.

---

## 4. Permissions matrix

Per §6.19 inheritance.

| Action | Teacher (own GSO) | Coordinator (assigned scope) | School Admin (own school) | (+District+Platform per inheritance) |
|---|:---:|:---:|:---:|:---:|
| View own daily review cards | ✅ | view-only (own scope) | view-only (school) | inherit ✅ |
| Drill down on cluster (see individual student names) | ✅ | aggregate only (no names) | aggregate only (no names) | inherit aggregate |
| Respond to reflective prompt | ✅ (own) | ❌ | ❌ | ❌ |
| Edit auto-generated mini-lecture draft | ✅ (own) | ❌ | override (audit) | inherit |
| Publish mini-lecture (targeted distribution) | ✅ (own) | ❌ | override-publish (audit) | inherit |
| Open Edit Main Lecture from review | ✅ (own) | ❌ | override (audit) | inherit |
| Open Schedule Group Study from review | ✅ (own) | ❌ | own school | inherit |
| Dismiss review without action | ✅ (own) | ❌ | override (audit) | inherit |
| View aggregate "pending reviews" metric | own only | ✅ scope | ✅ school | inherit |
| Skip a cluster (exclude from mini-lecture) | ✅ (own) | ❌ | ❌ | ❌ |
| Reply to specific students in a cluster (in-app) | ✅ (own) | ❌ | ❌ | ❌ |
| Re-trigger mini-lecture regeneration | ✅ (own) | ❌ | override (audit) | inherit |
| View "Reviews" tab on a lecture (chronological history) | ✅ (own) | ✅ scope | ✅ school | inherit |
| Override student privacy #72 | ❌ | ❌ | ❌ | ❌ |

**Locked rules:**
- **Student names are teacher-only.** Every other role sees aggregate-only drill-down. No exceptions.
- **Privacy #72 inviolate** — opted-out students are excluded from aggregation; no role overrides.
- **Admin override actions are audit-logged** per §14.10.

---

## 5. Edge cases

### 5.1 Aggregation (§3.1)
- **A school had zero questions yesterday:** no review card is generated; teacher sees "No review today" empty state.
- **A cluster fails LLM classification:** the failure is written to `review_classification_failures` (DLQ); the rest of the review still ships; Platform Admin sees the DLQ count.
- **One school's task is slow:** per-school task isolation — it never blocks other schools' reviews.
- **SLA breach (not done by 05:00):** Platform Admin alerted; partial reviews still deliver what completed.
- **Privacy #72 = private for some students:** those students' questions never enter the aggregation; if a cluster falls below the min-students threshold after exclusion, it doesn't surface.

### 5.2 Mini-lecture (§3.4, §3.5)
- **Cost ceiling hit mid-generation:** generation aborts; cluster surfaces without a ready mini-lecture; teacher can manually "Regenerate."
- **Originality check flags the mini-lecture:** surfaced to the teacher like a main lecture; teacher decides.
- **Independent tenant:** mini-lectures are never generated for independent teachers.

### 5.3 Review card + actions (§3.2, §3.6)
- **Teacher with multiple Grade-Subject offerings:** gets multiple separate review cards (one per GSO) — never combined.
- **Teacher never opens the review:** `pending_action` flag set; counts toward the "pending reviews" metric; review stays accessible indefinitely on the Reviews tab.
- **Two teachers share an offering (co-teaching):** each sees the same review; actions are recorded with actor identity; first publish wins, second sees "already published."
- **Reflective prompt generated with grading language:** the LLM call retries on bad phrasing (anti-grading safeguard); if it still fails, the prompt is omitted rather than shown.

### 5.4 Targeted distribution (§3.7)
- **A triggering student transfers out before publish:** excluded from the recipient set at publish-time.
- **All recipients unenrolled:** publish blocked with `PRECONDITION_FAILED`.
- **Teacher publishes, then regenerates:** a new mini-lecture version; already-distributed recipients keep the version they received unless re-published.

### 5.5 Review-as-child-record (§3.8)
- **Parent lecture archived:** reviews remain as read-only on the (archived) lecture's Reviews tab.
- **Parent lecture soft-deleted:** reviews retained for audit; not shown on active surfaces.

---

## 6. Limits

### Aggregation (§3.1)
- Clustering similarity: cosine ≥ 0.80 within (lecture, paragraph, source_chunk) buckets
- Frequency threshold: min 3 students OR 25% of the Grade-Subject offering roster
- Criticality threshold: LLM-scored 0-10, threshold 7
- Top 10 clusters per tab (High-Frequency / Critical); overflow collapses to "and N more"
- SLA: all schools complete by 05:00 Asia/Karachi
- Teacher notification scheduled at 06:00 Asia/Karachi — never earlier

### Mini-lecture (§3.4, §3.5)
- Word target: 800-1200
- Cost ceiling: $0.50 per mini-lecture
- Web-search fallback: disabled
- Scoring: Depth + Alignment weighted 1.5× (max 60)

### Review card (§3.2)
- One card per Grade-Subject offering per school day
- Reviews never expire; persist past 7+ days untouched
- `review_classification_failures` DLQ captures cluster-level LLM failures

---

## 7. Notifications

### Namespace: `lectures` (primary)

| Trigger | Recipient | Channel(s) | Template key |
|---|---|---|---|
| Daily review ready | Teacher (own GSO) | push + in-app, scheduled 06:00 Asia/Karachi | `lectures.next_day_review_ready` |
| Mini-lecture assigned | Triggering students (recipient set) | push + in-app | `lectures.mini_lecture_assigned` |
| Mini-lecture assigned (child) | Parents of recipients (Flow 10) | per Flow 10 | (Flow 10 namespace) |
| Critical-cluster alert | Teacher (own GSO) | push + in-app, real-time (respects quiet hours 22:00-06:00 for non-emergencies) | `lectures.review_critical_cluster` |

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel(s) | Template key |
|---|---|---|---|
| Aggregation SLA breach | Platform Admin | in-app + email | `system.review_sla_breach` |
| Classification DLQ entries | Platform Admin | in-app | `system.review_classification_failures` |

**Locked rules:** all templates in correct namespaces (`lectures` primary, `system` for SLA/failures); all 4 languages (en/ur/sd/ps), no `__TODO__` in production; critical-cluster alerts respect quiet hours 22:00-06:00 for non-emergencies.

---

## 8. Open questions

> A spec cannot merge with unresolved open questions. These are flagged **Open for Awais review** (carried from the v1 draft).

- [ ] **Q1 — Reflective prompt: optional or mandatory?** Should the teacher be required to respond to the reflective prompt before acting, or is it always skippable? (Leaning optional/skippable.)
- [ ] **Q2 — Cross-GSO aggregation deferred.** Currently strictly per-Grade-Subject offering. Should a teacher ever see a combined cross-offering review? (Deferred.)
- [ ] **Q3 — Two-shift school handling deferred.** Schools running morning/afternoon shifts — does each shift get its own review window? (Deferred.)
- [ ] **Q7 — Critical-alert quiet-hours behaviour.** Confirm critical-cluster alerts truly hold until 06:00, or whether a genuinely critical misconception may break quiet hours.
- [ ] **Q10 — Per-question privacy override deferred.** Whether a student can mark a single question private (vs the whole-self-study #72 toggle). (Deferred.)
- [ ] **Q11 — Coordinator visibility into individual replies.** Should a Coordinator ever see the teacher's per-student replies, or strictly aggregate? (Currently aggregate-only.)
- [ ] **Q15 — Anti-grading safeguard precision target.** What accuracy bar must the reflective-prompt anti-grading classifier hit before launch?

---

## 9. Out of scope (for now)

- **Group study scheduling.** The "Schedule Group Study" button opens the Flow 11 scheduler — disabled until Flow 11 ships. (TODO.md: flow-11-group-study)
- **Auto-quiz on mini-lectures.** Mini-lectures deliberately skip Flow 5 #23b auto-quiz generation. (Permanent decision, not deferred.)
- **Cross-grade linking for mini-lectures.** Blocked at the API. (Permanent.)
- **Review loop for independent students.** No teacher → no review. (Permanent — independent tenant excluded.)
- **AI intelligence consumption** (mistake tracking, spaced repetition, cognitive DNA). The clusters feed Flow 9 when it ships. (TODO.md: flow-9-ai-intelligence)

---

## 10. Related ARCHITECTURE sections

When implementing this flow, Claude Code reads these (in addition to §0):

- §3 (entire) — multi-tenancy; school tenant only, independent excluded at the filter
- §3.18 — Grade-Subject offering is the review unit
- §4 + §4.21 — DB patterns; school-schema Alembic head
- §5 — API design (review surfaces, drill-down, actions)
- §6.19 — permission inheritance (teacher names-visible; everyone else aggregate)
- §7 — Pattern S RAG reuse for the mini-lecture (`lecture_type=mini`)
- §8.6 — typed prompts (clustering, criticality classification, reflective-prompt generation, mini-lecture generation)
- §9 + §9.21 — NATS events (`mini_lecture.generated`, `lectures.mini_lecture_assigned`) + notification namespaces
- §10 + §10.6 — Celery + beat schedule (`review.aggregate_nightly`, daily 23:00 Asia/Karachi)
- §13 — i18n (4 languages, RTL)
- §14.10 — audit log (admin override-publish/edit/regenerate)

---

## 11. Acceptance criteria

### Overnight aggregation pipeline (#40, #44)
- ✅ Celery beat `review.aggregate_nightly` runs at 23:00 Asia/Karachi daily, one task per active school
- ✅ Pipeline filters by `tenant_type='school'`, `student_self_study_privacy='share'`, current teacher's GSOs
- ✅ Clustering uses embedding cosine ≥ 0.80 within (lecture, paragraph, source_chunk) buckets
- ✅ Frequency classifier: `freq_score`, min 3 students or 25% of GSO roster
- ✅ Criticality classifier: LLM-scored 0-10, threshold 7
- ✅ Top 10 clusters per tab (High Freq / Critical); overflow → "and N more"
- ✅ Per-school task isolated — a slow school doesn't block others
- ✅ SLA: all schools complete by 05:00 Asia/Karachi; breach → Platform Admin alert
- ✅ Teacher notification scheduled at 06:00 Asia/Karachi (never earlier)
- ✅ DLQ table `review_classification_failures` captures cluster-level LLM failures

### Mini-lecture generation (#40)
- ✅ Reuses Flow 5 generation pipeline; only difference is `lecture_type=mini` flag + shorter prompt
- ✅ Per-paragraph source attribution preserved
- ✅ Word target 800-1200; cost ceiling $0.50 per mini-lecture
- ✅ Web search fallback DISABLED
- ✅ NATS event `mini_lecture.generated` published

### Mini-lecture scoring (#39)
- ✅ Same 7-dimension Flow 5 §3.6 pipeline
- ✅ Depth and Alignment weighted 1.5× (max score 60 vs main lecture's 55)
- ✅ Stored in same `lecture_versions.scores_jsonb`; admin dashboard distinguishes via `lecture_type`
- ✅ Originality check (#33) runs against global corpus (including other mini-lectures)
- ✅ Mini-lectures excluded from independent teacher tenant

### Review card delivery (#45, #49)
- ✅ One card per Grade-Subject offering per school day
- ✅ Card sections: AI summary + Reflective prompt + High-Freq tab + Critical tab + Mini-lecture preview + Action buttons
- ✅ Reflective prompt LLM-generated with coaching tone (anti-grading safeguard, retries on bad phrasing)
- ✅ Voice or text response for reflective prompt; transcribed via faster-whisper
- ✅ Response feeds `teacher_ai_memory` (new category)
- ✅ Persistent until acted-on or dismissed; survives 7+ days untouched

### Drill-down (#45)
- ✅ Per-cluster modal shows aggregated wording + per-student exact wording + content element link
- ✅ Student names visible to teacher only; aggregate-only for Coordinator + Admin
- ✅ "Reply to students" creates `review_replies` rows; uses hybrid widget #57
- ✅ "Skip cluster" updates `skipped_clusters` and excludes from mini-lecture regen

### Action buttons (#46)
- ✅ Pre-filled context on all actions
- ✅ "Publish Mini-Lecture" → §3.7 targeted distribution
- ✅ "Edit Main Lecture" → opens Flow 5 edit mode with context banner
- ✅ "Schedule Group Study" → opens Flow 11 scheduler pre-filled (action disabled until Flow 11 ships)
- ✅ "Dismiss without action" → recoverable; `dismissed_at` set; can be re-opened
- ✅ Multiple actions allowed per review; `acted_actions[]` is an array

### Targeted distribution (#47)
- ✅ Recipient set = union of triggering students; computed at publish-time
- ✅ `lecture_assignments` rows created per recipient
- ✅ Recipients notified via `lectures.mini_lecture_assigned`
- ✅ Parents of recipients notified per Flow 10 read-only
- ✅ Auto-quiz NOT generated for mini-lectures (Flow 5 #23b skipped)
- ✅ Cross-grade linking BLOCKED at API for mini-lectures
- ✅ All recipients unenrolled → publish blocked with `PRECONDITION_FAILED`

### Review-as-child-record (#48)
- ✅ `lecture_reviews` row per review; parent linkage via `lecture_id`
- ✅ "Reviews" tab on lecture detail shows chronological history (all time)
- ✅ Reviews never expire; archived parents retain reviews as read-only
- ✅ Aggregate metrics ("pending reviews per teacher", "days to act") feed Flow 5 #38 admin dashboard

### Permissions
- ✅ Privacy #72 inviolate — opted-out students excluded; no role can override
- ✅ Teacher sees own students by name; everyone else aggregate only
- ✅ Admin override-publish audit-logged per §14.10
- ✅ Independent students/teachers cannot reach this flow's surfaces

### Notifications
- ✅ All templates in correct namespaces (`lectures` primary, `system` for SLA/failures)
- ✅ Critical-cluster alerts fire real-time, respecting quiet hours 22:00-06:00 for non-emergencies
- ✅ All 4 languages; no `__TODO__` in production

### i18n
- ✅ Review UI in en/ur/sd/ps; RTL handled
- ✅ AI summary + reflective prompt in teacher's UI language
- ✅ Question wording preserved in original language; aggregate canonicalization in teacher's UI language

### Audit
- ✅ Admin override-publish logged per §14.10
- ✅ Override-edit-mini-lecture logged
- ✅ Review pipeline SLA breaches logged for compliance

---

## Data model touched

```
# New tables (this flow):
lecture_reviews            (one row per review; FK lecture_id; pending_action,
                            dismissed_at, acted_actions[] (array), generated_at)
review_replies             (teacher replies to students in a cluster; hybrid widget #57)
skipped_clusters           (clusters the teacher excluded from mini-lecture regen)
review_classification_failures   (DLQ — cluster-level LLM failures:
                            retry_count, last_retry_at, resolved_at (nullable))

# Existing tables EXTENDED by this flow:
lectures           (Flow 5 — add columns)
  + lecture_type (enum: main / mini, default main)
  + parent_lecture_id (uuidv7, nullable FK to lectures.id — set when lecture_type=mini)

lecture_versions   (Flow 5)
  -- no schema change; same scoring scores_jsonb stores mini-lecture scores;
  -- mini-lecture-specific weights applied at scoring-task time, not in schema

lecture_assignments  (Flow 5)
  -- no schema change; mini-lecture recipients use the same table

teacher_ai_memory  (Flow 5 #36)
  -- gains a new category: 'reflective_response_pattern' — captures the teacher's
  -- engagement style with reflective prompts
```

---

**Last reviewed:** 2026-05-20
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1:** Initial draft. Covers 8 features (#39, #40, #44, #45, #46, #47, #48, #49). Aligned with:
- Flow 5 (mini-lecture is `lecture_type=mini` variant; same generation pipeline + scoring with adjusted weights)
- Flow 6 v2 (questions collected there feed this; privacy #72 enforced)
- Flow 4 v3 (independent students excluded at tenant filter)
- Flow 2 v3 (per-Grade-Subject offering as review unit)
- Ledger §6.19 (permission inheritance), §9.21 (notification namespaces), §3.16 (independent tenant exclusion)
- STACK_LOCK §4 (faster-whisper for reflective voice, Groq Llama for clustering + classification + mini-lecture generation)
- §10.6 beat schedule (new task: `review.aggregate_nightly` daily 23:00 Asia/Karachi)

# Flow 9 — AI Intelligence Layer / Cognitive DNA

**Status:** drafted (v1)
**v2 doc features covered:** #42, #43, #74, #75, #76, #77, #78, #79, #80, #81, #82, #83, #84, #85, #86, #87, #88, #89, #90, #91, #92, #93, #94, #95, #96, #97, #98, #99
**Related feature specs:** `flow-4-student-onboarding.md` (diagnostic #51 seeds DNA), `flow-5-teacher-creates-lecture.md` (quizzes #23b feed the question bank + mistakes), `flow-6-student-studies-lecture.md` (interaction events #60, flashcards #58, misconception classifier #57-area feed signals), `flow-7-next-day-review.md` (review clusters feed DNA), `flow-8-self-study.md` (goal + adherence signals; surfaces "due cards" Flow 9 schedules), `flow-10-parent-monitoring.md` (future — consumes pass-probability for proactive alerts), `flow-11-group-study-dashboards.md` (future — renders DNA aggregates, class comparison #73, learning record #105)

## Purpose

The platform-wide AI intelligence layer. It collects every question a student asks, banks and tags it, tracks mistakes over time, builds a per-student **Cognitive DNA** profile of *how* they learn, predicts exam outcomes (pass probability, predicted marks, readiness), schedules spaced revision against each student's own forgetting curve, and runs gap-recovery — and feeds all of this back to the teaching prompts so every other flow gets smarter. It is the consumer for the signals every prior flow has been emitting (diagnostics, session/question events, review clusters, goals, adherence, flashcards), and the producer the parent (Flow 10) and dashboard (Flow 11) flows read from.

**Heuristic-first (the governing scope rule).** Per STACK_LOCK §ML + ARCHITECTURE §C, **Phase 1 ships heuristic formulas only** — no trained models. Every predictive feature (#79 guess detection, #83 DNA, #85 pass probability, #89 SHAP, #90 predicted marks) is built in `app/services/ml/heuristic/` behind the **exact API contract** the future trained model will expose, so the Phase-2 swap is zero-caller-change. Trained models (scikit-learn / XGBoost / SHAP) are a **Phase-2 deferral**, not a separate flow. This flow spec describes the full behaviour; the milestone family builds the heuristic version and stubs the weekly retrain.

## Personas

- **Student** — sees their DNA positively framed (#84), their pass probability / predicted marks / recommendations, recovery mode, and micro-revisions.
- **Teacher** — sees raw DNA + at-risk signals for their students (dashboard rendering is Flow 11).
- **Coordinator / School Admin** — class/grade aggregates (rendering Flow 11).
- **Platform Admin** — district/platform aggregates; approves the weekly AI pedagogy templates (#99).
- **System (Celery)** — nightly recalculation, weekly retrain stub, precise-timing revision notifications.

Both tenants (school + independent) get the full intelligence layer; the difference is event source + who can see aggregates (independents have no teacher).

---

## 3. Lifecycle

### 3.1 Student question collection (#42)

```
   ANY student question (lecture mode OR self-study)
       ↓ emitted on the Flow 6 NATS pipeline (#60), mode-tagged
   COLLECTED            (student_questions: question_text, mode, content_element_ref, topic, tenant_type)
       ↓ tagged to the exact content element (page / paragraph / diagram / formula)
   FEEDS                (question bank candidate #74 + misconception detection #43 + DNA signals)
```

**Locked rules:**

- Collects **every** question across both modes (`mode ENUM[lecture, reference_self_study]`), tagged to the exact content element it came from (the M-12 content-element tagging is the source).
- Source is the existing NATS pipeline (#60, Flow 6 / M-14) + `student_events` store — **no new collection mechanism**; Flow 9 adds the consumer that persists structured `student_questions` for intelligence use.
- Privacy #72 applies: school-student questions only feed teacher-visible surfaces when `share`; **aggregate-anonymous always flows** (system improvement #99).
- Both tenants identical collection.

### 3.2 Misconception vs knowledge-gap detection (#43)

```
   COLLECTED question / wrong answer
       ↓ LLM classifies (§8.6 typed prompt)
   CLASSIFIED   ├─ misconception (wrong mental model)  → correct directly
                └─ knowledge_gap (never learned)        → teach from scratch
```

**Locked rules:**

- LLM classifies each difficulty signal as `misconception` vs `knowledge_gap`; the teaching response differs (correct vs teach-from-scratch).
- Flow 6 / M-12 T-157 built a **lightweight in-session classifier**; Flow 9 owns the **formal, persisted** detector that feeds DNA + gap analysis (#92). The two share the same `§8.6` prompt family — Flow 9 is the canonical owner.
- Result stored on the question/mistake record; drives error-type classification (#80) and recovery (#93).

### 3.3 Question Bank (#74) + Bloom's tagging (#75)

```
   QUESTION SOURCES  (quizzes #23b, collected student Qs #42, generated)
       ↓ tag
   BANKED            (question_bank: topic, difficulty, bloom_level, source, tenant scope)
       ↓ LLM Bloom's classification (6 levels)
   TAGGED            (Remember / Understand / Apply / Analyse / Evaluate / Create)
```

**Locked rules:**

- **Build this first** — the bank is the foundation for practice, mistake tracking, gap recovery, and spaced revision; nothing else in Flow 9 works without it (this drives the M-18a ordering).
- Every question tagged by **topic, difficulty, Bloom's level** (#75: LLM classifies into the 6 Bloom levels). Apply-level used for revision; Understand+Apply mixed for gap recovery.
- Bank scoped per tenant + curriculum; deduplicated; questions sourced from teacher quizzes (#23b, Flow 5), collected student questions (#42), and LLM generation.
- Replaces the M-08 "LLM-generated diagnostic questions for now" interim — the diagnostic (#51) now draws from the bank (satisfies the M-08 Question Bank hook).

### 3.4 Question scheduling queue (#76)

```
   QUEUE SOURCES
       ├─ gap recovery sets        (priority 1 — most urgent)
       ├─ wrong-answer repeats      (priority 2)
       ├─ spaced-repetition due     (priority 3, from FSRS #94)
       └─ daily practice            (priority 4)
       ↓ unified, priority-ordered
   student_question_queue(student_id, question_id, scheduled_for, priority, reason)
```

**Locked rules:**

- **One unified queue** for all question delivery; most urgent (gap recovery) always first.
- Consumes the M-15 / M-17 `flashcard.created` events (satisfies those hooks) — flashcards become queue entries; FSRS (#94) computes their `scheduled_for`.
- Surfaced by Flow 8's "due cards" view (Flow 8 renders; Flow 9 schedules).
- Both tenants identical.

### 3.5 Per-question signals — timer (#77) + confidence (#78) + guess detection (#79)

```
   QUESTION PRESENTED
       ↓ frontend captures
   TIMING (ms precision) + CONFIDENCE (1-5, asked before result) + ANSWER
       ↓ heuristic (Phase 1)  →  trained model (Phase 2)
   GUESS? (response_time_z, confidence-vs-accuracy mismatch, hard-right/easy-wrong, answer-switching)
       ↓ if guess → flagged + EXCLUDED from pass-probability model
```

**Locked rules:**

- **Per-question timer** at millisecond precision (#77) — fast answer on a hard question signals a guess; feeds DNA.
- **Confidence rating** (#78) captured 1-tap (1-5) **before** the result is shown; confidence-vs-accuracy gap reveals over/under-confidence.
- **Guess detection** (#79) is a **Phase-1 heuristic** (`app/services/ml/heuristic/guess_detection.py`) on `[response_time_z, confidence_accuracy_mismatch, difficulty_inversion, answer_switching]`; flagged guesses are **excluded from the pass-probability model**. Phase-2 swaps a trained classifier behind the same API.

### 3.6 Error-type classification (#80) + mistake tracking (#81) + similar-question engine (#82)

```
   WRONG ANSWER
       ↓ LLM classifies
   ERROR_TYPE  [careless | conceptual | misunderstanding]   → AI responds differently
       ↓ persist
   student_mistakes(student_id, topic, concept, error_type, count, last_seen)
       ↓ same mistake ≥3× on a topic
   ALERT ("You've made this mistake 4 times in Vectors") + auto-schedule similar Qs (#82)
       ↓ similar question = (embed wrong Q → cosine) OR (same concept, different wording)
   SURFACED  (prevents pattern memorisation)
```

**Locked rules:**

- Every wrong answer auto-classified (#80) into careless / conceptual / misunderstanding (LLM reads the student's answer + working).
- **Long-term mistake tracking** (#81): store every wrong answer across all sessions; ≥3 same-topic repeats → alert + auto-schedule recovery questions into the queue (#76).
- **Similar-question engine** (#82): on a wrong answer surface a *different* question testing the same concept (embedding cosine similarity primary; same-concept-different-wording fallback) — never just repeat the same item.
- Both tenants identical.

### 3.7 Cognitive DNA profile (#83) + visual & role visibility (#84)

```
   SIGNALS  (guess_rate, memorisation_vs_understanding, time-pressure response,
             error-type mix, retention, diagnostic seed #51, review clusters, goal/adherence)
       ↓ heuristic profile (Phase 1)  →  ML pipeline (Phase 2)
   cognitive_dna(student_id, dimensions_jsonb, updated_at)   ← improves every session
       ↓ render
   STUDENT: radar chart, positively phrased ("Great at recall — let's build application")
   TEACHER: raw dimensions     ADMIN: class/district aggregates (rendered in Flow 11)
       ↓ feeds
   PERSONALISED TEACHING (injected into §8.x prompts across flows)
```

**Locked rules:**

- `cognitive_dna` is the **schema extension hooked from M-08** (mistake history, predictions, spaced-repetition state, learning dimensions) — Flow 9 owns it.
- Profile improves every session by consuming: the M-08 diagnostic seed (#51), M-12 interaction signals, M-14 `student_events` (analytics consumer), M-16 review clusters, M-17 goal + adherence signals. **Each of these is a registered BLOCKED-HOOK that this section satisfies.**
- Phase 1 = heuristic dimensions; Phase 2 = ML pipeline (same API).
- **Role-scoped visibility** (#84): student sees a positively-phrased radar chart; teacher sees raw; coordinator/admin see aggregates. Rendering surfaces live in Flow 11; Flow 9 exposes the data + the role-scoped API.
- The DNA output is the source of the **mastery-estimate metric** the M-14 live panel left blocked.

### 3.8 Pass probability (#85) + nightly recalc (#86) + exam confidence (#87)

```
   NIGHTLY (Celery beat — ARCH Path C; handles 100k+ students < 10 min, vectorised)
       ↓ per student with an upcoming exam
   PASS_PROBABILITY (0-100%)   = heuristic (Phase 1) / gradient-boost (Phase 2)
       features: study_consistency, practice_performance, weak_topic_count, plan_adherence (Flow 8)
   DAYS_TO_FAIL                 = days until probability is unrecoverable
   EXAM_CONFIDENCE (0-100)      = readiness: topics_covered, quiz_accuracy, consistency, self-rating
       ↓ if pass_prob < 0.4 AND days_to_exam < 30
   EMIT low-probability signal  → Flow 10 proactive parent alert (#100)
```

**Locked rules:**

- **Pass probability** (#85) is a **Phase-1 heuristic** (`app/services/ml/heuristic/pass_probability.py`); **adherence % (Flow 8 #70) is a model input** — satisfies the M-17 adherence→pass-probability hook. Guess-flagged answers excluded (#79). Weekly retrain is a **stub** in Phase 1 (`retrain_models_weekly`).
- **Nightly batch** (#86) recalculates for every student with an upcoming exam — vectorised (pandas), **must handle 100,000+ students in < 10 minutes**; also computes `days_to_fail`. This is ARCH Path C.
- **Exam confidence** (#87) is a separate readiness composite, shown as a daily trend.
- The `pass_prob < 0.4 AND days_to_exam < 30` condition **emits the signal Flow 10 consumes** for the proactive parent alert (#100) — Flow 9 computes + emits; the parent alert itself is Flow 10.

### 3.9 2-future simulation (#88) + causal SHAP (#89) + predicted marks (#90)

**Locked rules:**

- **2-future simulation** (#88): on a probability drop, a side-by-side "if you continue → X marks, FAIL" vs "if you follow the plan → Y marks, PASS" — emotional, urgent (red/green cards, one CTA). Behaviour-driven.
- **Causal topic analysis** (#89): rank weak topics by their contribution to predicted failure. Phase 1 = a heuristic contribution ranking; Phase 2 = **SHAP** values on the trained model (same API).
- **Predicted marks** (#90): a marks *range* (e.g. "55-62/100"), from a **separate** regression model (Phase-1 heuristic → Phase-2 regression). Makes stakes concrete.

### 3.10 Recommendations (#91) + gap analysis (#92) + recovery bundle (#93)

```
   pass_prob < threshold
       ↓
   3 ACTIONS (#91)   exactly 3, ranked, each with est. +% ("Revise Newton's Laws Ch3 → +18%")
   ──────────────────────────────────────────────────────────────────
   10+ related Qs detected → ASK PERMISSION → GAP ANALYSIS (#92, root cause trace)
       ↓ gap found
   RECOVERY BUNDLE (#93)  full-screen: [real-life example] → [mini-lecture] → [5 questions]
       ↓ complete in order
   MILESTONE BADGE
```

**Locked rules:**

- **Exactly 3** ranked recommendations (#91), each concrete with an estimated improvement % — never "study more"; LLM-generated from the student's actual weak topics + DNA.
- **Gap analysis** (#92) triggers on 10+ related questions, **asks the student's permission** first, then traces to a root cause.
- **Recovery bundle** (#93): full-screen Recovery Mode — real-life example → mini-lecture (reuses Flow 5/Flow 7 mini-lecture generation) → 5 practice questions, completed **in order**; finishing earns a milestone badge.

### 3.11 Spaced repetition + forgetting curve (#94) + precise-timing notifications (#95)

```
   CONCEPT LEARNED
       ↓ py-fsrs (FSRS) — calibrated per student over time   [NOT SM-2]
   next_review_at computed
       ↓ enqueue Celery ETA task at the exact timestamp   [NOT Bull/cron]
   PRECISE NOTIFICATION fires (push/email/SMS via Flow 8 #68 channels) → micro-revision (#96)
```

**Locked rules:**

- **py-fsrs (FSRS algorithm)** per STACK_LOCK §ML — **replaces SM-2** (the v2 doc's "SM-2 base" is superseded; FSRS gives personalised forgetting curves, calibrated to each student's actual forgetting speed). Satisfies the M-15 / M-17 py-fsrs scheduling hooks.
- **Precise-timing** (#95) uses a **Celery ETA/delayed task on the Redis broker** (+ the ARCH "FSRS due-soon hot queue" in Redis) — **NOT Bull** (Node-only; forbidden) and **NOT a daily cron** (too coarse). Each reminder scheduled for an exact `next_review_at` timestamp.
- Reminders ride the Flow 8 #68 channels (FCM / Brevo / Jazz+Telenor), degrading silently.

### 3.12 Micro-revision context rotation (#96) + 30-second recall (#97) + retention rate (#98)

**Locked rules:**

- **Context rotation** (#96): each micro-revision explains the concept from a *different* angle than last time (real-world → story → exam-style → analogy → visual), tracked in `concept_review_history` — never repeat a framing.
- **30-second recall** (#97): each micro-revision opens with a 30s recall task — circular countdown (green→amber→red), auto-submit at 0, then show right/missed.
- **Retention rate** (#98): per-concept `correct_recalls / total_recalls` (last 30 days); colour-coded topic map (green = retaining, red = forgetting); shown as improvement over time.

### 3.13 System AI pedagogy improvement (#99)

```
   WEEKLY (Celery beat)
       ↓ aggregate platform-wide difficulty signals (anonymous, flows regardless of #72)
   FIND failing explanations (topics where AI explanations consistently fail students)
       ↓ AI generates better explanation templates
   ADMIN REVIEW → APPROVE → templates go live   (human approval gate — never auto-deploy)
```

**Locked rules:**

- Weekly batch finds platform-wide topics where AI explanations consistently fail; AI drafts improved templates; **a Platform Admin reviews + approves before anything goes live** (suggest-and-approve, never autonomous).
- Uses aggregate-anonymous signals (flows regardless of #72).

### 3.14 Heuristic-first → trained-model swap (cross-cutting)

**Locked rules:**

- Phase 1: all predictive features are heuristics in `app/services/ml/heuristic/` exposing the **same API** as the future model; routes in `app/routes/predictions.py`; nightly recalc live (`recalculate_predictions_nightly`), weekly retrain a **stub** (`retrain_models_weekly`).
- Phase 2 (deferred — NOT a separate flow): swap trained scikit-learn / XGBoost / SHAP models behind the identical API — **zero caller change**. This is a phase deferral recorded in TODO.md, not a BLOCKED-HOOK to another flow.

---

## 4. Permissions matrix

| Action | Student | Teacher | Coordinator | School Admin | Platform Admin | Parent |
|---|---|---|---|---|---|---|
| See own DNA (positive framing) | ✓ | — | — | — | — | via Flow 10 |
| See student raw DNA | own only | own students | aggregate | aggregate | aggregate | — |
| See own pass-prob / marks / recs | ✓ | — | — | — | — | via Flow 10 |
| See student pass-prob | own | own students | aggregate | aggregate | aggregate | own child (Flow 10) |
| Approve AI pedagogy templates (#99) | — | — | — | — | ✓ | — |
| Trigger gap analysis | consent only | — | — | — | — | — |

- #72 inviolate: a school student set to "No" is invisible to all teacher-facing DNA/risk surfaces; aggregate-anonymous still flows.
- Independent students: no teacher/coordinator visibility; their DNA is their own + aggregate-anonymous.

## 5. Edge cases

- New student, no data → DNA shows "still learning your style"; pass-prob withheld until a minimum signal threshold (no false precision).
- Guess-heavy session → guesses excluded from pass-prob; flagged for the student gently.
- Exam date passed / none set → pass-prob + nightly recalc skip that student.
- Recovery bundle abandoned mid-way → resumable; not marked complete; no badge.
- Mistake-count alert fatigue → cap one same-mistake alert per topic per day.

## 6. Limits

- Nightly batch: 100,000+ students < 10 minutes (vectorised; chunked per school for isolation).
- Pass-prob withheld below a minimum-signal threshold.
- Recommendations: **exactly 3**, ranked.
- Gap analysis: requires explicit student consent; triggers at 10+ related questions.
- Question bank generation cost-capped per batch; Bloom's tagging batched.
- Mistake alert: ≥3 repeats; max one alert/topic/day.

## 7. Notifications

- `intelligence.mistake_pattern` (≥3 repeats), `intelligence.probability_drop` (student-facing 2-future), `intelligence.revision_due` (precise-timing micro-revision), `intelligence.recovery_available`.
- `system.pedagogy_review_pending` (Platform Admin, #99), `system.ml_batch_lag` (nightly batch SLA breach).
- **Emitted for downstream:** low-probability signal → Flow 10 (#100 parent alert); DNA aggregates → Flow 11.

## 8. Open questions

(All built to launch recommendations per standing instruction.)
- **Q1 — minimum-signal threshold** for showing pass probability. Rec: withhold until ≥1 diagnostic + ≥20 answered questions. **Adopted.**
- **Q2 — heuristic formula weights** for pass-prob / guess detection. Rec: start with the ARCH heuristic weights; calibrate when real data exists (the deferred comprehensive cost/telemetry study). **Adopted.**
- **Q3 — #73 Anonymised Class Comparison placement.** **Resolved: Flow 11** (dashboard display); Flow 9 produces the ranking data only.
- **Q4 — pedagogy-template auto-vs-approve.** **Resolved: always admin-approved** (#99 locked rule; CXO no-autonomous-action rule).

## 9. Out of scope (for now)

- **Trained ML models** (scikit-learn / XGBoost / SHAP / regression) — Phase 2 swap behind the same API (TODO.md, not a flow hook).
- **DNA aggregate dashboards, class comparison #73, student learning record #105** — rendering is Flow 11 / M-20.
- **Proactive parent alert #100** — Flow 9 emits the low-probability signal; the alert is Flow 10 / M-19.
- **Group-study intelligence** (#101 AI-suggested groups uses DNA) — Flow 11 consumes Flow 9 output.

## 10. Related ARCHITECTURE sections

§C Path C (nightly batch: pass-prob, FSRS, parent-alert trigger), §7 (RAG / embeddings for similar-question + question bank), §8.6 (typed prompts: misconception, error-type, recommendations, pedagogy templates), §9 / §9.21 (`intelligence` + `system` namespaces), §10 (Celery beat: nightly recalc, weekly retrain stub, precise-timing ETA), §4 (`cognitive_dna`, `question_bank`, `student_questions`, `student_mistakes`, `student_question_queue`, `concept_review_history`, retention), STACK_LOCK §ML (scikit-learn/XGBoost/SHAP Phase 2, py-fsrs, heuristic-first), §3.16 (both tenants), §6.19 (role-scoped visibility), §13 (i18n).

## 11. Data model sketch

```
# Both school + independent schemas (tenant-routed):

student_questions      id, tenant_type, student_id, question_text, mode[lecture,reference_self_study],
                       content_element_ref, topic_id, classified[misconception,knowledge_gap], created_at
question_bank          id, tenant_scope, topic_id, difficulty, bloom_level, source[quiz,collected,generated],
                       question_text, answer, embedding_ref, created_at
student_question_queue id, student_id, question_id, scheduled_for, priority, reason[gap,repeat,spaced,daily]
student_mistakes       id, tenant_type, student_id, topic_id, concept_id, error_type[careless,conceptual,misunderstanding],
                       count, last_seen
cognitive_dna          student_id (PK), dimensions_jsonb, guess_rate, memorisation_index, time_pressure_index,
                       updated_at        # the M-08-hooked schema extension
predictions            student_id, exam_type_id, pass_prob, days_to_fail, predicted_marks_low, predicted_marks_high,
                       exam_confidence, computed_at        # nightly
concept_review_history id, student_id, concept_id, last_angle, tried_angles_jsonb, next_review_at, retention_rate
recovery_bundles       id, student_id, gap_concept_id, status[active,complete,abandoned], steps_jsonb, badge_awarded
pedagogy_templates     id, topic_id, draft_template, status[pending,approved,rejected], reviewed_by, reviewed_at
```

## 12. Acceptance criteria

1. Every student question collected + content-element-tagged across both modes (#42); misconception/gap classified (#43).
2. Question bank built + Bloom-tagged (#74/#75); diagnostic (#51) draws from it; unified priority queue delivers questions (#76).
3. Per-question timing + confidence captured; guess detection (heuristic) excludes guesses from pass-prob (#77/#78/#79).
4. Wrong answers classified (#80); ≥3 repeats alert + auto-schedule (#81); similar-question surfaced (#82).
5. Cognitive DNA built from all hooked signals (diagnostic, sessions, events, clusters, goals, adherence), role-scoped, positively framed for students (#83/#84); supplies the M-14 mastery metric.
6. Pass probability (heuristic) + nightly recalc <10min for 100k+ + days-to-fail + exam confidence (#85/#86/#87); adherence is an input; low-prob signal emitted for Flow 10.
7. 2-future simulation, causal ranking (heuristic), predicted-marks range (#88/#89/#90).
8. Exactly-3 recommendations; consented gap analysis; ordered recovery bundle + badge (#91/#92/#93).
9. py-fsrs scheduling (not SM-2) + Celery-ETA precise notifications (not Bull) (#94/#95); context-rotated micro-revision + 30s recall + retention map (#96/#97/#98).
10. Weekly pedagogy-improvement batch with mandatory admin approval (#99).
11. All predictive features built heuristic-first behind the model-swap API; weekly retrain stubbed (§3.14).
12. #72 inviolate throughout; both tenants; i18n (en/ur/sd/ps, RTL).

---

## Milestone split (M-18 family)

Flow 9 is ~28 features — too large for one milestone. M-18 becomes a contiguous, dependency-ordered family (ticket ranges assigned off T-222 at draft time):

- **M-18a — Question Bank + Collection foundation** (#42, #43, #74, #75, #76). *Build first* — everything downstream needs the bank + queue. Satisfies M-08 Question Bank hook.
- **M-18b — Cognitive DNA engine** (#77–#84). Signals, mistake tracking, similar-question, DNA profile + role visibility. Satisfies M-08 cognitive_dna schema + diagnostic consumer, M-11 calibration, M-12 interaction consumer, M-14 analytics consumer + mastery metric, M-16 clusters→DNA, M-17 goal signal.
- **M-18c — Prediction + recommendations** (#85–#93). Pass-prob, nightly recalc, exam confidence, 2-future, SHAP-heuristic, predicted marks, recommendations, gap analysis, recovery. Satisfies M-17 adherence→pass-prob; emits the Flow 10 #100 signal.
- **M-18d — Spaced repetition + retention + pedagogy** (#94–#99). FSRS scheduling, precise-timing, micro-revision, recall, retention, weekly pedagogy. Satisfies M-15 / M-17 py-fsrs scheduling hooks.

Order a → b → c → d (b needs the bank; c needs DNA; d needs the queue + DNA).

## Drafting completeness ledger

**v2 features covered (28):** #42, #43, #74-#99 (matches header). #73 → Flow 11 (resolved). #50 → Flow 6 label-fix (not Flow 9).

**BLOCKED-HOOKs consumed (satisfied by this spec):**
- M-08 T-102 `cognitive_dna` schema → §3.7 / M-18b
- M-08 T-104 Question Bank #74 → §3.3 / M-18a
- M-08 T-106 `student.diagnostic_completed` consumer → §3.7 / M-18b
- M-11 T-144 Cognitive DNA calibration → §3.7 / M-18b
- M-12 T-163 interaction-signal consumer → §3.7 / M-18b
- M-14 T-174 analytics consumer (reads `student_events`) → §3.7 / M-18b
- M-14 T-179 mastery-estimate metric → §3.7 / M-18b (DNA supplies it)
- M-15 T-187 py-fsrs scheduling + queue #76 → §3.4 (queue) + §3.11 (FSRS) / M-18a + M-18d
- M-16 T-195 review clusters → DNA → §3.7 / M-18b
- M-17 T-210 py-fsrs scheduling (due cards) → §3.4 + §3.11 / M-18a + M-18d
- M-17 T-211 daily-goal signal → DNA → §3.7 / M-18b
- M-17 T-219 adherence → pass-probability #85 → §3.8 / M-18c

**Cross-flow assertions honored:** Cognitive DNA + mistake tracking + spaced-repetition state + predictions (Flow 4/6/8 refs); pass probability #85 (Flow 8); Cognitive DNA seed #83 (Flow 4 diagnostic); mastery estimate (Flow 6/M-14).

**New BLOCKED-HOOKs this flow defers onward:**
- `BLOCKED-HOOK: proactive parent alert on low pass-probability (#100) → Flow 10 / M-19 (Flow 9 emits the pass_prob<0.4 & days<30 signal; Flow 10 sends the alert)`
- `BLOCKED-HOOK: DNA aggregate dashboards + class comparison #73 + student learning record #105 → Flow 11 / M-20 (Flow 9 exposes role-scoped data; Flow 11 renders)`
- `BLOCKED-HOOK: AI-suggested study groups (#101) consume DNA/performance → Flow 11 / M-20`

**Phase deferral (not a flow hook):** trained ML models (scikit-learn/XGBoost/SHAP/regression) → Phase 2, same-API swap (TODO.md).

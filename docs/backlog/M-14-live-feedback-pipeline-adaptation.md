# M-14 — Live Feedback Panel + NATS Event Pipeline + Per-Session Adaptation

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-173 through T-184
**Spec source:** `flow-6-student-studies-lecture.md` v1 §3.7 (live feedback panel #59), §3.8 (NATS JetStream event pipeline #60), §3.9 (per-session AI teaching adaptation #61)

## Goal

The third of four Flow 6 milestones, and the one that turns the events M-12 *emits* into working infrastructure. M-14 builds the **NATS JetStream event pipeline (#60)** — the cross-cutting real-time backbone with three independent consumers — then uses it to power a **live feedback panel (#59)** that updates the student every 60s and nudges them when stuck, and **per-session AI adaptation (#61)** that switches teaching angle when a student asks about the same sub-topic twice in a session.

**Scope boundary (Flow 6 split M-12→M-15):**
- M-12 (done): viewer #54, highlight #55, AI answer panel #56, hybrid widget text+voice #57; **emits** `student.lecture.*` events.
- M-13 (done): hybrid widget image + vision #57.
- **M-14 (this):** the NATS pipeline #60 + its 3 consumers, the live feedback panel #59, per-session adaptation #61.
- M-15: highlight persistence + flashcards #58, concept enrichment + career links + simulation #71, lecture rating.

**This milestone consumes earlier hooks** (surfaced by the pre-draft audit): the M-12 T-163 event emission (M-14 builds the consumer pipeline it feeds), the M-12 base-persona note (M-14 adds adaptive difficulty), and the M-08 T-108 per-session-adaptation read-hook (M-14 builds the full #61 adaptation).

**Demo at milestone end:**
- Student studies a lecture → interaction events (highlight, question, scroll, page-change, mode-switch) publish to NATS `student.lecture.*`; three consumers process them independently
- After 2 minutes, the live feedback panel appears bottom-right showing time-on-topic + questions-asked-this-session + daily-goal status, refreshing every 60s over WebSocket
- Student sits on one page >10 min with no questions → a one-time soft nudge appears ("Been here 10 min — need help?") with quick actions (rephrase / list key concepts / switch to voice)
- Student asks two questions about the same sub-topic → the AI's next answer switches angle (example → metaphor → analogy …), and respects any active Custom Persona
- A consumer lagging >30s raises a Platform-Admin alert (`system.event_pipeline_lag`)
- Independent-tenant events flow through the same pipeline, tagged `tenant_type=independent` (their surfaces are Flow 8, not this panel)

---

## T-173 — NATS JetStream stream + event envelope + subjects (#60 foundation)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.8 (subject pattern `student.lecture.{event_type}`; structured envelope; 7-day retention)

### ARCH source
- `ARCHITECTURE.md` §9 (NATS JetStream; event envelope; durable consumers), STACK_LOCK §4 / §9 (NATS locked, replaces Kafka)

### Depends on
- T-038-range (NATS infra, M-01), T-163 (M-12 emits `student.lecture.*`)

### What this ticket builds

**Backend:** The JetStream stream for `student.lecture.*` with the structured event envelope per §9 (tenant_id, tenant_type, user_id, session_id, lecture_id, timestamp, event_type, payload). Subject pattern `student.lecture.{event_type}` (question_asked, highlight_created, session_opened, session_closed, scroll, page_change, mode_switch). Stream retention = 7 days for live processing. Durable-consumer scaffolding so the three consumers (T-174/T-176/T-177) subscribe independently. This formalizes/validates the events M-12 T-163 already emits.

### Acceptance (demo script)

1. [ ] `student.lecture.*` JetStream stream exists with 7-day retention
2. [ ] Events carry the full §9 envelope (incl. tenant_id + tenant_type)
3. [ ] Subject pattern `student.lecture.{event_type}` for all M-12 event types
4. [ ] Durable consumer subscriptions can attach independently
5. [ ] M-12-emitted events land on the stream and are readable

### Out of scope
- The consumers themselves (T-174/T-176/T-177)

---

## T-174 — Analytics Consumer → `student_events` persistence (#60)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.8 (Analytics Consumer persists to Postgres `student_events` for long-term aggregation; read by Flow 7 + Flow 9 + Flow 11 nightly)

### ARCH source
- `ARCHITECTURE.md` §9 (durable consumer), §4 (`student_events` table — created M-00)

### Depends on
- T-173 (stream), T-001-range (`student_events` table, M-00)

### What this ticket builds

**Backend:** The Analytics Consumer — a durable JetStream subscription that persists every `student.lecture.*` event to the Postgres `student_events` table (created in M-00) for long-term aggregation. This is the event store the nightly aggregators read. M-14 builds the **writer**; the readers are: Flow 7 next-day review (M-16, drafted — normal forward dep), Flow 11 (M-20), and the **Cognitive DNA consumer (Flow 9 / M-18, blocked)**.

### Acceptance (demo script)

1. [ ] Every `student.lecture.*` event persisted to `student_events`
2. [ ] Durable subscription survives restart (no event loss; replays from last ack)
3. [ ] Events tenant-tagged in the store
4. [ ] Independent-tenant events routed to the independent event store
5. [ ] Runs independently of the other two consumers

### Out of scope
- The nightly aggregators that read this store (Flow 7/M-16, Flow 9/M-18)

### Notes / known gotchas
- BLOCKED-HOOK: Cognitive DNA analytics consumer (reads `student_events`) → Flow 9 / M-18 (M-14 builds the writer + event store; the DNA reader attaches when Flow 9 ships — same hook M-12 T-163 registered, M-14 now provides its source).

---

## T-175 — `session_difficulty_log` model + sub-topic tagging (#61 data)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.9 (sub-topic via `lecture_paragraphs.source_chunk_id` → curriculum topic_tree; `session_difficulty_log` accumulates; `tried_angles`)

### ARCH source
- `ARCHITECTURE.md` §4 (DB), §7 (topic_tree from Flow 3 #18), §3.18 (lecture↔GSO)

### Depends on
- T-151 (session, M-12), T-113 (lecture_paragraphs/source_chunk_id, M-09), T-057 (topic_tree, M-04)

### What this ticket builds

**Backend:** Migration for `session_difficulty_log {id, session_id, sub_topic_id, question_count, tried_angles jsonb, last_angle, updated_at, tenant_type}`. Sub-topic identification: map each question's `source_chunk_id` (from the highlight/answer in M-12) back to the curriculum `topic_tree` node (Flow 3 #18). Accumulate per (session, sub_topic) question counts — the signal the adaptation trigger (T-182) reads. `AI_ADAPT_QUESTION_THRESHOLD` (already in ENV_VARS, default 2) governs the threshold.

### Acceptance (demo script)

1. [ ] `session_difficulty_log` table exists (both schemas), tenant-tagged
2. [ ] Each question maps to a sub-topic via source_chunk_id → topic_tree
3. [ ] Per-(session, sub_topic) question counts accumulate
4. [ ] `tried_angles` + `last_angle` columns present for T-182
5. [ ] Threshold read from `AI_ADAPT_QUESTION_THRESHOLD`

### Out of scope
- The angle-switch logic (T-182); the consumer that writes it (T-176)

---

## T-176 — AI Session Context Consumer (#60 → #61)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.8 (AI Session Context Consumer updates per-session difficulty log for #61)

### ARCH source
- `ARCHITECTURE.md` §9 (durable consumer)

### Depends on
- T-173 (stream), T-175 (`session_difficulty_log`)

### What this ticket builds

**Backend:** The second durable consumer — subscribes to `student.lecture.question_asked`, resolves the question's sub-topic (T-175 mapping), and increments the `session_difficulty_log` for that (session, sub_topic). This is what keeps the adaptation signal live during a session. Independent of the analytics + live-feedback consumers (one slow consumer can't block the others).

### Acceptance (demo script)

1. [ ] `question_asked` events update `session_difficulty_log`
2. [ ] Sub-topic resolved + per-sub-topic count incremented
3. [ ] Runs as an independent durable subscription
4. [ ] Lag in this consumer doesn't block the other two
5. [ ] Independent-tenant questions update the independent store

### Out of scope
- The angle-switch decision (T-182)

---

## T-177 — Live Feedback Consumer → WebSocket push (#60 → #59)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.8 (Live Feedback Consumer pushes to WebSocket; powers #59), §3.7 (channel `student.live_feedback.{user_id}`, 60s cadence)

### ARCH source
- `ARCHITECTURE.md` §9 (durable consumer), §5 (WebSocket API)

### Depends on
- T-173 (stream), T-179 is downstream (metrics) — this ticket only pushes

### What this ticket builds

**Backend:** The third durable consumer — aggregates a student's recent `student.lecture.*` events and pushes a 60-second feedback tick to the WebSocket channel `student.live_feedback.{user_id}`. Handles connect/disconnect/reconnect; only the owning student may subscribe to their channel. The payload shape is the live-feedback metrics (computed in T-179).

### Acceptance (demo script)

1. [ ] Consumer pushes a tick to `student.live_feedback.{user_id}` every 60s during an active session
2. [ ] Only the owning student can subscribe to their channel
3. [ ] Reconnect resumes cleanly
4. [ ] Independent of the analytics + session-context consumers
5. [ ] No push after session ends

### Out of scope
- Metric computation (T-179); panel UI (T-180)

---

## T-178 — Pipeline backpressure + observability + independent routing (#60)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.8 (backpressure >30s lag → `system.event_pipeline_lag`; independent tagged + routed)

### ARCH source
- `ARCHITECTURE.md` §9.21 (`system` namespace alert), §3.16 (independent routing), §14 (observability)

### Depends on
- T-174, T-176, T-177 (the three consumers)

### What this ticket builds

**Backend:** Pipeline health — monitor each durable consumer's lag; if any lags >30s, raise `system.event_pipeline_lag` to Platform Admin. Confirm independent-tenant events are tagged `tenant_type=independent` and routed to the independent event store across all three consumers (the pipeline is cross-cutting infra — used by Flow 8 independent students even though Flow 6 surfaces are school-only). Pipeline health metrics exposed per §14.

### Acceptance (demo script)

1. [ ] Consumer lag >30s → `system.event_pipeline_lag` alert to Platform Admin
2. [ ] Independent events tagged + routed to the independent store on all 3 consumers
3. [ ] Per-consumer lag metrics observable
4. [ ] A deliberately stalled consumer triggers the alert in a test
5. [ ] School + independent events never cross stores

### Out of scope
- Flow 8 independent surfaces (M-17)

---

## T-179 — Live feedback metrics computation (#59 data)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.7 (metrics: time-on-topic, questions-asked, mastery estimate, daily-goal status)

### ARCH source
- `ARCHITECTURE.md` §4 (session metrics), §9 (consumer input)

### Depends on
- T-177 (live feedback consumer), T-151 (session, M-12), T-156 (questions, M-12)

### What this ticket builds

**Backend:** Compute the live-feedback metrics for the 60s tick: **time on this topic** (current lecture/chapter span) and **questions asked this session** (fully buildable from session + events). **Mastery estimate** and **daily-goal status** are dependency-gated (see hooks): until Flow 9 / Flow 8 ship, the panel shows the two available metrics and omits/greys the gated ones.

### Acceptance (demo script)

1. [ ] Time-on-topic + questions-asked computed per tick
2. [ ] Mastery estimate field present but null/hidden (Flow 9 dependency)
3. [ ] Daily-goal field present but null/hidden (Flow 8 dependency)
4. [ ] Metrics scoped to the current session only
5. [ ] Feeds the T-177 WebSocket payload

### Out of scope
- Panel UI (T-180)

### Notes / known gotchas
- BLOCKED-HOOK: live-feedback **mastery-estimate** metric → Flow 9 / M-18 (panel ships the other metrics now; mastery wired when Cognitive DNA exists).
- Forward dep (not blocked): **daily-goal status** → Flow 8 / M-17 (#69 daily goal); shown once Flow 8 ships. Flow 8 is drafted, so this is a normal forward dependency, not a BLOCKED-HOOK.

---

## T-180 — Live feedback panel UI (#59)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.7 (auto-show after 2 min; bottom-right collapsible; 60s WebSocket updates; collapse persists)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §13 (i18n/RTL), §5 (WebSocket)

### Depends on
- T-177 (WebSocket push), T-179 (metrics)

### What this ticket builds

**Frontend:** The live feedback panel — hidden until 2 minutes of activity, then appears bottom-right, collapsible (collapsed state persists for the session). Subscribes to `student.live_feedback.{user_id}` and re-renders every 60s with the available metrics. Gated metrics (mastery, daily goal) hidden until their flows ship. RTL-aware.

### Acceptance (demo script)

1. [ ] Panel auto-shows after 2 min activity, bottom-right
2. [ ] Updates every 60s from the WebSocket channel
3. [ ] Collapsible; collapsed state persists for the session
4. [ ] Only available metrics render (gated ones hidden)
5. [ ] RTL-correct

### Out of scope
- The stuck-nudge (T-181)

---

## T-181 — Stuck-nudge (#59)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.7 (>10 min same page + 0 questions → one-time nudge with quick actions)

### ARCH source
- `ARCHITECTURE.md` §9 (stuck signal from events), §12 (frontend)

### Depends on
- T-177 (event-driven), T-180 (panel)

### What this ticket builds

**Frontend + backend:** Detect the stuck condition — >10 minutes on the same page with 0 questions asked — and surface a soft nudge ("Been here 10 min — need help?") with quick-action buttons: rephrase last paragraph / list key concepts / switch to voice mode. Fires **once per stuck-session** (no repeat loop). Acknowledging, asking a question, or ignoring all dismiss it.

### Acceptance (demo script)

1. [ ] >10 min same page + 0 questions → nudge appears
2. [ ] Quick actions work (rephrase / list concepts / voice mode)
3. [ ] Fires at most once per stuck-session (no loop)
4. [ ] Asking a question before 10 min prevents the nudge
5. [ ] i18n (4 languages, RTL)

### Out of scope
- Adaptation (T-182)

---

## T-182 — Per-session angle-switch adaptation (#61)

**Layer:** 5
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.9 (2+ same sub-topic → angle switch; cycle angle types; persona co-exists; long-term DNA export is Flow 9)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompt — angle-switch context), §8.20 (Custom Persona prepended alongside)

### Depends on
- T-175 (`session_difficulty_log`), T-176 (session-context consumer), T-158 (answer pipeline, M-12)

### What this ticket builds

**Backend:** When `session_difficulty_log` shows ≥ `AI_ADAPT_QUESTION_THRESHOLD` (default 2) questions on the same sub-topic in a session, inject angle-switch context into the answer system prompt: "Student struggling with [X] — try a different angle." Cycle the angle types (example → metaphor → analogy → visual description → real-world application), tracking used ones in `tried_angles` to avoid repeating. If a Custom Persona (§8.20) is active, prepend it alongside the angle-switch context (adaptation respects persona tone/structure). This is session-local; the long-term difficulty export to Cognitive DNA is the Flow 9 analytics consumer's job (already a registered BLOCKED-HOOK).

### Acceptance (demo script)

1. [ ] 2nd question on same sub-topic → next answer switches angle
2. [ ] Angle types cycle; `tried_angles` prevents repeats within a session
3. [ ] Custom Persona, when active, prepended alongside angle-switch context
4. [ ] Threshold honors `AI_ADAPT_QUESTION_THRESHOLD`
5. [ ] In-session only — no Cognitive DNA dependency for the angle switch itself

### Out of scope
- Long-term DNA difficulty export (Flow 9 / M-18, via the T-174 analytics store)

---

## T-183 — Permissions + privacy + i18n + notifications

**Layer:** 5 / 6
**Milestone:** M-14
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.7-§3.9, §4 (permissions), §3.x privacy #72

### ARCH source
- `ARCHITECTURE.md` §6.19 (permissions), §9.21 (`system`/`lectures` namespaces), §14.10 (audit), §13 (i18n)

### Depends on
- T-173 through T-182

### What this ticket builds

**Backend:** Live-feedback + adaptation respect privacy #72 (student owns their feedback/difficulty data; parent read-only subject to #72 per §6.19); only the owning student subscribes to their WebSocket channel. Audit `system.event_pipeline_lag` alerts + any admin overrides. i18n — panel, nudge, and adapted answers in en/ur/sd/ps (RTL); no `__TODO__`. Notifications minimal (the pipeline-lag alert is the main `system`-namespace one).

### Acceptance (demo script)

1. [ ] Only the owning student accesses their live-feedback channel + difficulty data
2. [ ] Parent read-only respects #72
3. [ ] Pipeline-lag alerts audit-logged
4. [ ] Panel/nudge/adapted answers in 4 languages, RTL
5. [ ] No `__TODO__` strings

### Out of scope
- Teacher consumption of these signals (Flow 7 / M-16)

---

## T-184 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-14
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.7-§3.9

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-173 through T-183

### What this ticket builds

**Test + PR:** Automated E2E (LLM mocked; NATS + WebSocket exercised with test doubles; no live network) — emit `student.lecture.*` events → all 3 consumers process independently (analytics → `student_events`; session-context → `session_difficulty_log`; live-feedback → WebSocket tick) → panel shows time+questions after 2 min, updates at 60s → stuck >10 min + 0 questions → one-time nudge → 2 questions same sub-topic → angle switch asserted (with persona co-existing) → stalled consumer → `system.event_pipeline_lag` → independent events routed to independent store. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais; merge-commit to `staging` per BRANCHING.md; tickets = commits).

### Acceptance (demo script)

1. [ ] E2E green (LLM mocked; NATS/WebSocket via test doubles; no live network)
2. [ ] Asserts 3 independent consumers + their writes
3. [ ] Asserts panel cadence + stuck-nudge once + angle-switch + persona co-existence
4. [ ] Asserts pipeline-lag alert + independent routing
5. [ ] PR `milestone/M-14-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; merged

### Out of scope
- Anything beyond the M-14 ticket set

---

## Milestone notes

- **Third of four Flow 6 milestones.** M-14 builds the #60 pipeline + 3 consumers, the #59 live feedback panel + stuck-nudge, and #61 per-session adaptation. M-15 finishes Flow 6 (#58 flashcards, #71 enrichment, rating).
- **The NATS pipeline (#60) is cross-cutting Day-1 infrastructure** — three independent durable consumers (analytics, session-context, live-feedback); one slow consumer can't block the others; 7-day JetStream retention + Postgres `student_events` for long-term aggregation. It also serves Flow 8 independent students (tagged + routed), even though Flow 6's panel/adaptation surfaces are school-only.
- **Consumes earlier hooks:** M-12 T-163 emission → the pipeline here; M-12 base persona → adaptive difficulty here; M-08 T-108 adaptation read-hook → full #61 here.
- **Per-session adaptation (#61) is session-local** — the angle switch needs no Cognitive DNA; only the *long-term* difficulty export depends on Flow 9.
- **BLOCKED-HOOKs:** (T-179) live-feedback mastery-estimate metric → Flow 9 / M-18; (T-174) Cognitive DNA analytics consumer reading `student_events` → Flow 9 / M-18 (M-14 builds the writer/store; the DNA reader attaches in Flow 9 — same hook M-12 registered, now sourced).
- **Forward (non-blocked) dep:** live-feedback daily-goal metric → Flow 8 / M-17 (#69); shown once Flow 8 ships.
- **Open questions:** Q5 (stuck threshold), Q7 (adaptation threshold) — built to the spec's launch recommendations (10 min; `AI_ADAPT_QUESTION_THRESHOLD` default 2), treated as decided per standing instruction.
- **Source flow:** Flow 6 v1 §3.7-§3.9 — drafted; the relevant open questions have adopted launch recommendations (none blocking).

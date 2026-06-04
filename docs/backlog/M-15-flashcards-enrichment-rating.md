# M-15 — Flashcards + Concept Enrichment + Lecture Rating

**Status:** todo
**Estimated duration:** 2 weeks
**Tickets:** T-185 through T-194
**Spec source:** `flow-6-student-studies-lecture.md` v1 §3.6 (highlight persistence + auto-flashcards #58), §3.10 (real-world app + career links + mini-simulation #71), §3.11 (lecture rating)

## Goal

The fourth and final Flow 6 milestone — **completes Flow 6.** It adds the lasting study artifacts on top of the M-12 study surface: highlights now persist as yellow marks and auto-generate flashcards, concepts get cached real-world/career/mini-simulation enrichment, and students can rate a finished lecture. After this, the whole "student studies a lecture" journey (#54–#61, #71) is built.

**Scope boundary (Flow 6 split M-12→M-15):**
- M-12 (done): viewer #54, highlight→Q #55, answer panel #56, hybrid widget text+voice #57.
- M-13 (done): hybrid widget image + vision #57.
- M-14 (done): NATS pipeline #60, live feedback #59, per-session adaptation #61.
- **M-15 (this):** highlight persistence + auto-flashcards #58, concept enrichment #71, lecture rating. **Flow 6 complete.**

**Key boundaries:**
- **M-15 only *generates and publishes* flashcards** (`flashcard.created`). Flow 8 / M-17 *surfaces* "due cards," but the spaced-repetition **scheduling (py-fsrs) + question queue #76 are Flow 9 / M-18** (blocked) — so the scheduling consumer is a BLOCKED-HOOK (see T-187), not a plain forward dep.
- **Rating feeds the M-10 quality score** as a 5% supplementary signal (Flow 5 §3.6 #32 stays the 95% primary) — a backward dependency on M-10 (done).
- Flow 6 surfaces are **school-tenant only** (independent students use Flow 8); flashcard events are school-tagged.
- **One BLOCKED-HOOK** (T-187): py-fsrs flashcard *scheduling* → Flow 9 / M-18 (M-15 publishes `flashcard.created`; Flow 8 surfaces the deck; Flow 9 schedules). Other dependencies are on drafted/done milestones; the Cognitive-DNA interaction path stays the already-registered M-14 analytics → Flow 9 hook.

**Demo at milestone end:**
- Student highlights a passage and gets an answer (M-12) → the highlight persists; on returning to the lecture it shows as a yellow mark at the original position
- That highlight+answer auto-becomes a flashcard (front: highlight, back: AI answer); a duplicate highlight doesn't create a second card; a `flashcard.created` event publishes (Flow 8 will deck it)
- "My Highlights" tab lists the student's highlights chronologically with lecture + concept tags
- Student reaches a concept → sees cached real-world applications + Pakistani career links + an interactive mini-simulation; the first student to hit a new concept triggers generation, later students use cache
- Student finishes a lecture (≥80% scroll) → optional 1-5 star prompt → the rating contributes 5% to the teacher's displayed lecture quality score (anonymous, never used to rank students)
- A lecture re-edit that removes a highlighted span silently drops the yellow mark but keeps the flashcard

---

## T-185 — Highlight persistence model + yellow-mark restore (#58)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.6 (highlights table: text_range, content, lecture_id, AI response; yellow marks on return), §5.5 (offset-no-longer-exists edge)

### ARCH source
- `ARCHITECTURE.md` §4 (DB), §12 (viewer overlay), §3.18 (lecture↔GSO)

### Depends on
- T-156 (highlight→Q, M-12), T-159 (answer, M-12), T-152 (viewer, M-12)

### What this ticket builds

**Backend + frontend:** Migration for `highlights {id, lecture_id, student_user_id, text_range (offset+length), highlighted_text, ai_response_ref, concept_tag, created_at, tenant_type}`. Persist a highlight when the student highlights + gets an answer (M-12 made these transient; now they last). On returning to the lecture, render persisted highlights as yellow marks at their original positions via the viewer overlay. **Edge (§5.5):** if the lecture was re-edited and the offset no longer maps, the yellow mark is removed silently (the flashcard, built in T-186, still survives).

### Acceptance (demo script)

1. [ ] Highlight+answer persists a `highlights` row (text_range + content + ai_response_ref)
2. [ ] Returning to the lecture re-renders yellow marks at original positions
3. [ ] Re-edited lecture with a removed span → mark drops silently (no error)
4. [ ] Highlights scoped to the owning student + lecture's GSO
5. [ ] Tenant-tagged

### Out of scope
- Flashcard generation (T-186); the highlights tab (T-188)

---

## T-186 — Auto-flashcard generation (#58)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.6 (auto-flashcard on every highlight+answer pair; front=highlight, back=AI answer; dedupe by hash(highlight_text, lecture_id))

### ARCH source
- `ARCHITECTURE.md` §4 (flashcards table)

### Depends on
- T-185 (highlight persistence)

### What this ticket builds

**Backend:** Migration for `flashcards {id, student_user_id, lecture_id, concept_tag, front_text, back_text, dedupe_hash, created_at, tenant_type}`. On every highlight+answer pair, auto-create a flashcard — front = highlighted text, back = AI answer — tagged for lecture + concept. **Deduplicated** by `hash(highlight_text, lecture_id)` (a repeat highlight of the same text doesn't create a second card). The flashcard survives even if the source highlight's yellow mark is later removed (§5.5).

### Acceptance (demo script)

1. [ ] Each highlight+answer pair auto-creates a flashcard (front/back correct)
2. [ ] Duplicate highlight (same text + lecture) → no second card (hash dedupe)
3. [ ] Flashcard tagged lecture + concept
4. [ ] Flashcard persists independent of the highlight mark
5. [ ] Tenant-tagged

### Out of scope
- Publishing to the SRS deck (T-187); spaced-repetition scheduling (Flow 8)

---

## T-187 — Flashcard publish event → Flow 8 SRS (#58)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.6 (this flow only PUBLISHES the flashcard event; spaced-repetition scheduling via py-fsrs is Flow 9, surfaced by Flow 8)

### ARCH source
- `ARCHITECTURE.md` §9 (`flashcard.created` event), STACK_LOCK §4 (py-fsrs scheduling is Flow 9 / M-18)

### Depends on
- T-186 (flashcards)

### What this ticket builds

**Backend:** Publish a `flashcard.created` NATS event when a flashcard is created, carrying the card + student + concept refs. **M-15 publishes only.** Flow 8 / M-17 *surfaces* the deck ("due cards"), but the spaced-repetition **scheduling (py-fsrs) + question queue #76 are Flow 9 / M-18** — that scheduler consumes this event to compute due dates. No SRS or deck logic here.

### Acceptance (demo script)

1. [ ] `flashcard.created` emitted on each new flashcard
2. [ ] Event carries card + student + concept references
3. [ ] No spaced-repetition scheduling implemented here (verified: Flow 8 owns it)
4. [ ] Event tenant-tagged
5. [ ] Idempotent (dedupe-hash means no duplicate events)

### Out of scope
- The SRS deck/queue (Flow 8 / M-17)

### Notes / known gotchas
- BLOCKED-HOOK: spaced-repetition scheduling (py-fsrs) + question queue #76 that consume `flashcard.created` → Flow 9 / M-18 (M-15 publishes the event; Flow 8 / M-17 surfaces the deck; Flow 9 computes the schedule). Flow 8's surfacing is a normal forward dep; the *scheduling* consumer is the blocked piece.

---

## T-188 — "My Highlights" / flashcards view (#58)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.6 ("My Highlights" tab; chronological with lecture + concept tags), §4 (permissions matrix: view own; parent view-only if #72 allows)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §6.19 (permissions), §13 (i18n)

### Depends on
- T-185 (highlights), T-186 (flashcards)

### What this ticket builds

**Frontend + backend:** A "My Highlights" tab on the student dashboard — a chronological list of the student's highlights with lecture + concept tags, each linking back to its lecture position and showing its paired flashcard. Student sees own; parent read-only subject to #72; Coordinator/Admin aggregate per §6.19.

### Acceptance (demo script)

1. [ ] "My Highlights" tab lists own highlights chronologically with lecture + concept tags
2. [ ] Each entry links to its lecture position + shows its flashcard
3. [ ] Parent read-only respects #72
4. [ ] Coordinator/Admin see aggregate per §6.19
5. [ ] i18n (4 languages, RTL)

### Out of scope
- Spaced-repetition review UI (Flow 8)

---

## T-189 — `concept_applications` + `careers` vocab + per-concept cache (#71 data)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.10 (cached PER CONCEPT; `careers` controlled vocab seeded Pakistani + required_concepts; `student_simulation_progress`; ~90-day cache invalidation)

### ARCH source
- `ARCHITECTURE.md` §4 (DB), §10 (Celery beat for cache invalidation), §7 (concept identification)

### Depends on
- T-116 (lecture concepts, M-09), T-057 (topic_tree, M-04)

### What this ticket builds

**Backend:** Migrations for `concept_applications {id, concept_id, real_world_uses jsonb, career_link_ids jsonb, mini_sim_prompt, generated_at, tenant_type}` (cached **per concept**, not per student); `careers {id, name, sector, required_concepts jsonb}` seeded with Pakistani career options (Phase 2 may add global); `student_simulation_progress {id, student_user_id, concept_id, sim_state jsonb, updated_at}`. Cache invalidation: a Celery beat re-generates entries older than `CONCEPT_ENRICHMENT_CACHE_DAYS` (~90, configurable).

### Acceptance (demo script)

1. [ ] `concept_applications` keyed per concept (shared across students)
2. [ ] `careers` seeded with Pakistani options + required_concepts
3. [ ] `student_simulation_progress` per-student
4. [ ] Cache invalidation beat re-generates entries >90 days old (configurable)
5. [ ] Tables tenant-tagged

### Out of scope
- Generation (T-190); the mini-sim widget (T-191)

---

## T-190 — Concept enrichment generation (#71)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.10 (cache miss → Celery `concept.enrich_applications` → LLM generates real-world uses + career links + mini-sim prompt → persist; ~$0.10/concept amortized ~$0/student)

### ARCH source
- `ARCHITECTURE.md` §10 (Celery `concept.enrich_applications`), §8.6 (typed prompt), §7 (concept ground truth)

### Depends on
- T-189 (`concept_applications` + `careers`)

### What this ticket builds

**Backend:** When a student reaches a concept with no cached `concept_applications` row (cache miss), enqueue `concept.enrich_applications` — an LLM call (typed prompt) generating real-world applications, career links (resolved against the `careers` controlled vocab), and a mini-simulation prompt; persist as the per-concept cache row. Cache hit → serve immediately. First student triggers generation (~$0.10); subsequent students reuse cache (~$0).

### Acceptance (demo script)

1. [ ] Cache hit serves the cached enrichment immediately
2. [ ] Cache miss → `concept.enrich_applications` generates + persists
3. [ ] Career links resolve against the `careers` vocab (no free-text careers)
4. [ ] Generation is per-concept (second student on same concept = cache hit, no regen)
5. [ ] Cost logged for observability

### Out of scope
- The mini-sim interactive widget (T-191)

---

## T-191 — Mini-simulation render + save state (#71)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.10 (mini-sim is a structured prompt rendered as an interactive widget; per-student save state in `student_simulation_progress`)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend widget), §4 (`student_simulation_progress`)

### Depends on
- T-190 (mini_sim_prompt), T-189 (`student_simulation_progress`)

### What this ticket builds

**Frontend + backend:** Render the concept's enrichment to the student — real-world uses + career links + the mini-simulation as an interactive widget (e.g. "calculate the force needed to lift this rope"). Student interaction saves to `student_simulation_progress` (resume on return). RTL-aware.

### Acceptance (demo script)

1. [ ] Enrichment (uses + careers + sim) renders when a concept is reached
2. [ ] Mini-sim is interactive; state saves per student
3. [ ] Returning resumes saved sim state
4. [ ] i18n (4 languages, RTL)
5. [ ] Career links display from the controlled vocab

### Out of scope
- Expanding the careers vocabulary (Phase 2)

---

## T-192 — Lecture rating (§3.11)

**Layer:** 5
**Milestone:** M-15
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.11 (1-5 stars on completion ≥80% scroll/end; optional; 5% into teacher quality score; anonymous; never used to rank students)

### ARCH source
- `ARCHITECTURE.md` §4 (rating model), Flow 5 §3.6 #32 (lecture quality score — M-10), §6.19 (teacher sees average)

### Depends on
- T-152 (viewer completion signal, M-12), T-139 (lecture quality score/benchmark, M-10)

### What this ticket builds

**Backend + frontend:** On lecture completion (reaching the end of text OR ≥80% scroll), show an **optional** 1-5 star prompt (dismissable). Store the rating; it contributes **5% weight** to the teacher's displayed lecture quality score (the M-10 #32 AI scoring stays 95% primary). Teacher sees a 1-5 **average**; individual ratings are **anonymous**, never shown to other students, and **never used to rank students** (coaching-not-grading lock).

### Acceptance (demo script)

1. [ ] Rating prompt shows on completion (≥80% scroll or end); optional/dismissable
2. [ ] Rating stored; contributes 5% to the lecture's displayed quality score (95% AI)
3. [ ] Teacher sees a 1-5 average only; individual ratings anonymous
4. [ ] Never shown to other students; never used in any student ranking
5. [ ] Wires into the M-10 quality-score aggregate (not a new scoring pipeline)

### Out of scope
- Changing the M-10 7-dimension AI scoring itself

---

## T-193 — Permissions + privacy + i18n + notifications

**Layer:** 5 / 6
**Milestone:** M-15
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §4 (permissions matrix for #58/#71/rating), §3.x privacy #72

### ARCH source
- `ARCHITECTURE.md` §6.19 (permissions), §9.21 (namespaces), §14.10 (audit), §13 (i18n)

### Depends on
- T-185 through T-192

### What this ticket builds

**Backend:** Enforce the Flow 6 permissions matrix for the new artifacts — student owns highlights/flashcards/sim-progress/ratings; parent read-only subject to #72; Coordinator/Admin aggregate per §6.19. Audit rating submissions + admin overrides. i18n — highlights tab, enrichment, mini-sim, rating prompt in en/ur/sd/ps (RTL); no `__TODO__`. Notifications minimal per the flow.

### Acceptance (demo script)

1. [ ] Student owns their highlights/flashcards/sim-progress/ratings
2. [ ] Parent read-only respects #72; Coordinator/Admin aggregate per §6.19
3. [ ] Rating submissions audit-logged
4. [ ] All new surfaces in 4 languages, RTL
5. [ ] No `__TODO__` strings

### Out of scope
- Teacher-facing rating analytics beyond the 1-5 average (Phase 2)

---

## T-194 — E2E smoke test + milestone PR (Flow 6 complete)

**Layer:** 6
**Milestone:** M-15
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.6, §3.10, §3.11 (and Flow 6 end-to-end completeness)

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-185 through T-193

### What this ticket builds

**Test + PR:** Automated E2E (LLM mocked; no live network) — highlight+answer → persists + becomes a flashcard (dedupe asserted) + `flashcard.created` emitted → return to lecture shows yellow mark → re-edit removes span → mark drops, flashcard survives → "My Highlights" tab lists it → reach a concept → cache miss generates enrichment, second student = cache hit → mini-sim renders + saves state → finish lecture (≥80% scroll) → optional rating → 5% into the M-10 quality score (anonymous) asserted. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais; merge-commit to `staging` per BRANCHING.md; tickets = commits). **This PR completes Flow 6.**

### Acceptance (demo script)

1. [ ] E2E green (LLM mocked; no live network)
2. [ ] Asserts highlight persistence + dedup flashcard + event + §5.5 edge
3. [ ] Asserts per-concept enrichment cache (miss→gen, hit→reuse) + sim save state
4. [ ] Asserts rating → 5% quality-score contribution + anonymity + no student ranking
5. [ ] PR `milestone/M-15-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; merged — **Flow 6 complete**

### Out of scope
- Anything beyond the M-15 ticket set

---

## Milestone notes

- **Completes Flow 6.** With M-12 (viewer/highlight/Q&A/voice), M-13 (image/vision), M-14 (live feedback/pipeline/adaptation), and M-15 (flashcards/enrichment/rating), the entire "student studies a lecture" journey (#54–#61, #71) is built.
- **Flashcards: M-15 generates + publishes only** (`flashcard.created`). Flow 8 / M-17 surfaces "due cards"; the **py-fsrs scheduling + question queue #76 are Flow 9 / M-18** (BLOCKED-HOOK in T-187). No SRS/deck logic here.
- **Concept enrichment is cached per concept**, not per student — first encounter pays ~$0.10, the rest are ~$0; `careers` is a controlled Pakistani vocabulary; 90-day re-gen.
- **Rating is a 5% supplementary signal** into the M-10 lecture quality score (95% AI #32 stays primary); anonymous; never used to rank students (coaching-not-grading lock).
- **One BLOCKED-HOOK** (T-187): py-fsrs flashcard scheduling + question queue #76 → Flow 9 / M-18. Every other M-15 dependency is on a drafted/done milestone (M-09/M-10/M-12) or Flow 8/M-17 surfacing (normal forward dep); the Cognitive-DNA interaction path remains the already-registered M-14 analytics → Flow 9/M-18 hook.
- **Flow 6 surfaces are school-tenant only** (independent students use Flow 8); flashcard events school-tagged.
- **Open questions:** Q4 (flashcard spam), Q9 (mini-simulation scope), Q10 (enrichment cadence), Q11 (rating completion threshold) — all built to the spec's launch recommendations (dedup by hash; structured per-concept sim; 90-day cache; ≥80% scroll), treated as decided per standing instruction.
- **Source flow:** Flow 6 v1 §3.6/§3.10/§3.11 — drafted; relevant open questions have adopted launch recommendations (none blocking).

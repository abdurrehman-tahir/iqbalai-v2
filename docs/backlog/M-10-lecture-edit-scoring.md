# M-10 — Lecture Edit + Versions + 7-Dimension Scoring

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-129 through T-140
**Spec source:** `flow-5-teacher-creates-lecture.md` v1 §3.5 (edit #29/#30/#31), §3.6 (7-dim scoring #32), §3.7 (originality #33), §3.8 (topic relevance #34), §3.9 (score timeline #35), §3.10 (Teaching Innovation Record #36), §3.11 (anonymized benchmarking #37), §3.12 (admin comparative metrics #38)

## Goal

Picks up exactly where M-09 left off (a lecture sits at READY_FOR_EDIT). The teacher edits the AI draft — typing in a TipTap editor, dictating by voice, dropping in images (with AI proactively suggesting reference-book diagrams) — and **every save is a new immutable version**. Each version is scored asynchronously across 7 dimensions, checked for originality against a global cross-teacher index, and given a topic-relevance percentage. The teacher watches a version-by-version score timeline, gets adaptive coaching from a per-teacher Teaching Innovation Record, sees a positively-framed peer benchmark, and admins get a scope-restricted comparative metrics table.

**Scope boundary:** edit + versioning + scoring + the reporting built on scores. **Auto-quiz per student + publish to students = M-11.** The lecture can reach PUBLISHED state here (the edit lifecycle ends there), but quiz generation and the student-facing publish surface are M-11. Cross-grade linking (#21) + per-lecture access (#21) already shipped in M-09 (T-122/T-123).

**Demo at milestone end:**
- Teacher opens a generated lecture (READY_FOR_EDIT), edits text in TipTap → Save → a new version row is created (the old one is untouched)
- Teacher dictates an edit by voice; the transcription inserts at the cursor
- Teacher drag-drops an image; separately, the AI prompts "Diagram on page 34 of Ref Book X — add it?"
- Effort tracking records active time + edits while the teacher works (timer pauses when the tab loses focus)
- Within seconds of saving, the teacher sees a 7-dimension score, a topic-relevance gauge, and an originality score
- A near-duplicate edit triggers a low originality score (teacher) + a silent Platform-Admin plagiarism flag (matched teacher never revealed)
- The version timeline shows the score climbing across versions, with auto annotations ("Applied voice edit", "Image inserted")
- After a few low-originality versions, the Innovation Record suggests "try grounding in local Punjab examples"; if ignored repeatedly, it changes its angle
- The teacher sees "Top 23% of Physics teachers in Punjab"; a School Admin opens the comparative metrics table (own school only) and exports CSV

---

## T-129 — Edit + scoring data model

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5, §3.6, §3.7, §3.10, §3.11

### ARCH source
- `ARCHITECTURE.md` §4 (DB; `lectures.scores_json` per-version 7-dim breakdown), §3.16 (per-tenant), §4.21 (dual heads)

### Depends on
- T-113 (lectures/lecture_versions/lecture_paragraphs, M-09)

### What this ticket builds

**Backend:** Migrations in both schemas for: `lecture_edit_sessions {id, lecture_version_id, teacher_user_id, active_ms, edits_count, char_delta, started_at, ended_at}`; extend `lecture_versions` with `scores_json` (per-dimension), `topic_relevance_pct`, `originality_score`, `edit_summary` (auto-extracted annotation); `teacher_ai_memory {id, tenant_type, teacher_user_id, category, weakness_type, frequency, last_suggestion, teacher_response ENUM[acted, ignored, none], updated_at}` (Flow 5 #36 — distinct from student Cognitive DNA; Flow 7/M-16 later extends it with a `reflective_response_pattern` category); `teacher_benchmarks {id, teacher_user_id, subject_id, grade_range, region, percentile, cohort_size, opted_out bool, updated_at}`; and the admin-only `lecture_originality_index` view/table reference (§3.7).

**Frontend:** None.

### Acceptance (demo script)

1. [ ] All tables/columns exist in both schemas with constraints
2. [ ] `lecture_versions` are immutable except `scores_json` / `topic_relevance_pct` / `originality_score` populated by the async scoring job
3. [ ] `teacher_ai_memory` exists with a `category` column (extensible — Flow 7 adds a category later)
4. [ ] `teacher_benchmarks` has `opted_out` + cohort keys (subject, grade_range, region)
5. [ ] `lecture_originality_index` is admin-scoped per §3.7

### Out of scope
- Population logic (T-134–T-139)

---

## T-130 — TipTap editor + text edit → immutable new-version save (#29)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5 (edit lifecycle; "every save = new version row")

### ARCH source
- `ARCHITECTURE.md` §5 (API), §12 (frontend), STACK_LOCK §12 (frontend libs — editor)

### Depends on
- T-129 (edit model), T-116 (generation produces v1, M-09)

### What this ticket builds

**Frontend + backend:** The TipTap rich-text editor over the generated lecture (READY_FOR_EDIT). Teacher edits text; Save (manual) or auto-save creates a **new** `lecture_versions` row (never overwrites) and emits NATS `lecture.version.created` (consumed by scoring in T-134). Lifecycle READY_FOR_EDIT → EDIT_SESSION_ACTIVE → SAVED_AS_NEW_VERSION. PUBLISHED is reachable from here (publish-to-students surface is M-11).

### Acceptance (demo script)

1. [ ] Teacher edits the draft in TipTap; Save creates a new version row
2. [ ] The prior version is untouched (immutable)
3. [ ] Auto-save also produces a version (debounced, not per keystroke)
4. [ ] `lecture.version.created` emitted on each save
5. [ ] Editing is server-validated against teacher ownership of the lecture's Grade-Subject

### Out of scope
- Scoring (T-134), voice (T-131), images (T-132), effort metrics (T-133)

### Notes / known gotchas
- Flow 5 §3.5 states the editor is **TipTap** ("locked per STACK_LOCK"). Confirm TipTap is actually listed in STACK_LOCK §12 (frontend) before implementing; if absent, that's a STACK_LOCK gap to raise (do not substitute a different editor).

---

## T-131 — Voice edits (faster-whisper STT) (#29)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5 (voice edits — transcribe, insert-at-cursor or replace-selection)

### ARCH source
- `ARCHITECTURE.md` §5 (WebSocket audio), STACK_LOCK §4 (faster-whisper)

### Depends on
- T-130 (editor)

### What this ticket builds

**Frontend + backend:** Voice dictation in the editor — faster-whisper STT transcribes; the teacher chooses to insert the text at the cursor OR replace the current selection. Reuses the M-09 voice infrastructure (T-121) where possible.

### Acceptance (demo script)

1. [ ] Teacher dictates; transcription inserts at cursor
2. [ ] With text selected, transcription replaces the selection (teacher's choice)
3. [ ] STT uses faster-whisper (STACK_LOCK §4), not raw Whisper
4. [ ] A voice-originated save still creates a normal new version
5. [ ] Works in en/ur (Piper-paired languages) + sd/ps per the M-09 voice stack

### Out of scope
- Voice-quality scoring dimension (T-134 computes it)

---

## T-132 — Image upload + AI diagram suggestions (#30)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5 (image upload #30; AI proactively suggests reference-book diagrams)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`lecture_image` upload profile), §11 (uploads → MinIO), §7 (reference-book content for diagram detection)

### Depends on
- T-130 (editor), T-056 (reference ingestion, M-04)

### What this ticket builds

**Frontend + backend:** Drag-drop image upload into the editor → stored via the `lecture_image` upload profile (§11.19) in MinIO → image URL inserted at cursor. Plus the proactive AI diagram suggestion: during/after generation, the AI flags reference-book pages containing relevant diagrams and surfaces "Diagram on page 34 of Ref Book X — add it?"; accepting inserts it.

### Acceptance (demo script)

1. [ ] Drag-drop image → uploaded via `lecture_image` profile → URL inserted in editor
2. [ ] Upload respects the profile's size/type limits (§11.19)
3. [ ] AI surfaces a "Diagram on page N of Ref Book X — add it?" prompt when a relevant diagram exists
4. [ ] Accepting inserts the referenced diagram; declining dismisses
5. [ ] Image insert produces a new version like any other edit

### Out of scope
- General media library (Phase 2)

---

## T-133 — Effort tracking (#31)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5 (effort tracking #31 — visibility-API pause, 30s heartbeat, effort score formula)

### ARCH source
- `ARCHITECTURE.md` §4 (`lecture_edit_sessions`), §5 (API)

### Depends on
- T-129 (edit-session model), T-130 (editor)

### What this ticket builds

**Frontend + backend:** Track edit effort per session — frontend pauses the timer on tab blur (Page Visibility API), heartbeats every 30s; DB records `active_ms`, `edits_count`, `char_delta`. Effort score = `normalize(active_ms) × 0.4 + normalize(char_delta) × 0.6`, fed into scoring (T-134) as an input.

### Acceptance (demo script)

1. [ ] Timer pauses on tab blur, resumes on focus (Visibility API)
2. [ ] 30s heartbeat persists `active_ms`
3. [ ] `edits_count` + `char_delta` recorded per edit session
4. [ ] Effort score computed per the locked formula
5. [ ] Effort data available to the scoring pipeline

### Out of scope
- Surfacing effort as a teacher-visible metric (it feeds scoring, not a standalone display)

---

## T-134 — 7-dimension quality scoring pipeline (#32)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.6 (7-dimension scoring; triggered every save; async)

### ARCH source
- `ARCHITECTURE.md` §7.10 + §4138 (scoring is a SEPARATE LLM call, evaluator persona, `SCORING_MODEL` per STACK_LOCK §4.1), §8.6 (typed prompt), §10 (Celery `lecture_score` queue), §9 (NATS `lecture.version.created`)

### Depends on
- T-130 (versions + event), T-133 (effort input), T-138 (Innovation Record context — soft; baseline 0 if absent)

### What this ticket builds

**Backend:** Celery task on `lecture.version.created` that scores the version across the 7 dimensions — Originality (10), Depth (10), Cultural relevance (5, region-aware via Flow 3 `teacher_region`), Engagement (5), Alignment (10), Voice quality (5, NULL if text-only), AI Learning (10, vs Innovation Record; baseline 0 on first version) — max 55. A **separate** LLM call using the smaller `SCORING_MODEL` (STACK_LOCK §4.1) with an evaluator persona; inputs = original v1 + edited version + diff + edit-session data + teacher_region + Innovation Record context. Scores written to `lecture_versions.scores_json`. Originality (T-135) + topic relevance (T-136) run as part of the same pipeline.

### Acceptance (demo script)

1. [ ] Every save triggers async scoring; teacher sees scores within seconds of completion
2. [ ] 7 dimensions scored; total max 55; per-dimension breakdown in `scores_json`
3. [ ] Voice quality = NULL for text-only edits
4. [ ] AI Learning baseline = 0 on the first version
5. [ ] Scoring uses `SCORING_MODEL` (separate, smaller model), NOT the generation model
6. [ ] Cultural relevance uses `teacher_region`

### Out of scope
- Originality internals (T-135), relevance internals (T-136), timeline UI (T-137)

---

## T-135 — System-wide originality check (#33)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.7 (global cross-teacher originality; matched teacher hidden; plagiarism flag > 0.85)

### ARCH source
- `ARCHITECTURE.md` §7.15 (originality scoring — no LLM), §7.3 (BGE-M3 embeddings via Infinity), `lecture_originality_index` (§3 admin-scoped), §3.16 (independent isolation), §9 (`system.plagiarism_flagged`)

### Depends on
- T-129 (originality index), T-134 (scoring pipeline), T-056 (embeddings infra, M-04)

### What this ticket builds

**Backend:** As part of the scoring pipeline: embed the lecture content (BGE-M3 via Infinity, §7.3), cosine-compare against the **global** published-lecture index across all school-tenant teachers; `originality_score = 1 − max_similarity`. The matched teacher's identity is **never** revealed. If `max_similarity > 0.85`, raise a Platform-Admin flag (`system.plagiarism_flagged`) — invisible to the teacher (they only see their low originality score). Independent teachers: originality runs within the independent tenant only (their own prior versions), never cross-tenant (§3.16).

### Acceptance (demo script)

1. [ ] Originality score = 1 − max cosine similarity vs the global index
2. [ ] Global index = all published school-tenant lectures; independent lectures excluded
3. [ ] Matched-teacher identity never exposed anywhere
4. [ ] similarity > 0.85 → `system.plagiarism_flagged` to Platform Admin; teacher sees only the score
5. [ ] Independent teacher originality is tenant-isolated (own prior versions only)

### Out of scope
- The Platform-Admin plagiarism dashboard view (surfaced via the notification + admin metrics; full triage UI is Phase 2)

---

## T-136 — Topic relevance percentage (#34)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.8 (topic relevance — embed lecture vs curriculum topic; gauge; <70% warning)

### ARCH source
- `ARCHITECTURE.md` §7.3 (embeddings), §4 (`lecture_versions.topic_relevance_pct`)

### Depends on
- T-134 (scoring pipeline), T-057 (curriculum topic tree, M-04)

### What this ticket builds

**Backend + frontend:** As part of the pipeline: embed the lecture + embed the curriculum topic definition, cosine → `relevance_pct = cos_sim × 100`, stored per version. Shown as a gauge in the editor ("Topic Relevance: 87%"); a warning appears if it drops below 70% (drift).

### Acceptance (demo script)

1. [ ] `relevance_pct` computed + stored per version
2. [ ] Gauge renders in the editor
3. [ ] Warning shown when < 70%
4. [ ] Uses the curriculum topic definition the lecture was generated against

### Out of scope
- Blocking publish on low relevance (advisory only)

---

## T-137 — Version-by-version score timeline (#35)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.9 (score timeline — line chart, hover dims, auto annotations)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend charts), §4 (`lecture_versions`)

### Depends on
- T-134 (scores exist), T-133 (edit-session metadata for annotations)

### What this ticket builds

**Frontend + backend:** A line chart — x = version number, y = total score. Hovering a point reveals all 7 dimensions. Auto annotations extracted from edit-session metadata ("Added worked example", "Applied voice edit", "Image inserted"). Default view = last 6 versions; older via pagination.

### Acceptance (demo script)

1. [ ] Timeline plots total score across versions
2. [ ] Hover reveals all 7 dimensions for that version
3. [ ] Annotations auto-derived from edit metadata
4. [ ] Default = last 6 versions; pagination for older
5. [ ] Renders in the teacher's language (RTL-aware)

### Out of scope
- Cross-lecture timelines (per-lecture only)

---

## T-138 — Teaching Innovation Record (#36)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.10 (Teaching Innovation Record — adaptive coaching from per-teacher memory)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompt), §4 (`teacher_ai_memory`), §3.16 (independent simplified variant)

### Depends on
- T-129 (`teacher_ai_memory`), T-134 (scoring identifies weaknesses)

### What this ticket builds

**Backend + frontend:** Per-teacher adaptive coaching. Scoring identifies recurring weaknesses (e.g. consistently low originality, abstract examples); the AI generates a suggestion ("try grounding in local Punjab examples"); the teacher's response (acted/ignored) is tracked; future suggestions **adapt** — if a suggestion is repeatedly ignored, the AI changes its angle rather than repeating. Memory stored in `teacher_ai_memory` and loaded as LLM context on every scoring + generation session. Per-school-tenant; independent teachers get a simplified own-memory variant. **Coaching framing only — never grading-style judgement.**

### Acceptance (demo script)

1. [ ] Recurring weakness detected → suggestion presented to the teacher
2. [ ] Teacher response (acted/ignored) tracked per suggestion
3. [ ] Repeated ignore → AI changes its angle (not a repeat)
4. [ ] Memory loaded into scoring + generation prompts (closes the AI-Learning dimension loop)
5. [ ] Coaching tone, never grading; independent teachers get the simplified variant

### Out of scope
- Student Cognitive DNA (that's Flow 9 / M-18 — explicitly different from `teacher_ai_memory`)

### Notes / known gotchas
- `teacher_ai_memory` is the teacher-coaching store; do NOT conflate with student Cognitive DNA (M-08 seed / Flow 9). Flow 7 (M-16) later adds a `reflective_response_pattern` category to this same table.

---

## T-139 — Anonymized benchmarking (#37) + Admin comparative metrics (#38)

**Layer:** 4
**Milestone:** M-10
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.11 (anonymized benchmarking #37), §3.12 (admin comparative metrics #38)

### ARCH source
- `ARCHITECTURE.md` §10.6 (beat `benchmark.update_weekly` — already in the locked schedule), §9 (`benchmark.updated`), §6.19 (admin scope), §3.16 (independent exclusion)

### Depends on
- T-134 (scores), T-129 (`teacher_benchmarks`)

### What this ticket builds

**Backend + frontend:** (#37) Celery beat `benchmark.update_weekly` (already locked in §10.6) computes each teacher's percentile within their (subject, grade_range, region) cohort; **framing always positive** ("Top 23% of Physics teachers in Punjab" — never "bottom 30%"); teachers can opt out (removed from the pool, percentile hidden); N/A for independent teachers. (#38) An admin comparative metrics table — rows = teachers, columns = 7 dims + avg + topic_relevance + lecture_count; sortable, filterable (subject/grade/school), CSV export; **scope-restricted per §6.19** (School Admin = own school, District = own district, Platform = all); Coordinator does NOT see it; independent teachers excluded from school-admin views. Live query cached 1hr.

### Acceptance (demo script)

1. [ ] Weekly beat updates `teacher_benchmarks` percentile per cohort
2. [ ] Benchmark framing is always positive; opt-out removes the teacher from pool + hides their percentile
3. [ ] Admin metrics table renders 7 dims + avg + relevance + lecture_count; sortable/filterable; CSV export
4. [ ] Scope enforced per §6.19 (school/district/platform); Coordinator has no access
5. [ ] Independent teachers excluded from both surfaces; query cached 1hr

### Out of scope
- District-level rollups beyond §6.19 inheritance (Phase 2 analytics)

---

## T-140 — Notifications + audit + E2E + milestone PR

**Layer:** 4 / 6
**Milestone:** M-10
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.5–§3.12

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §14.10 (audit), §0 (E2E convention), per `WORKFLOW.md` §1.8 + §2.x

### Depends on
- T-129 through T-139

### What this ticket builds

**Backend + test + PR:** Notifications — scoring complete (teacher), `system.plagiarism_flagged` (Platform Admin), `benchmark.updated` (teacher), Innovation-Record suggestion (teacher); templates in 4 languages. Audit — admin metrics access/export, benchmark opt-out toggle, any admin override; plagiarism flags logged. E2E smoke test — edit (text + voice + image, LLM/STT mocked) → new version → async scoring (mocked LLM) → originality (global-index fixture) → relevance → timeline → Innovation-Record suggestion → weekly benchmark (time-warped) → admin metrics table + CSV; asserts immutability, matched-teacher anonymity, scope restriction. Then the single milestone PR per `WORKFLOW.md` Step 2 (description, `phase-complete-review` skill, demo for Abd. + Awais, merge to `staging`).

### Acceptance (demo script)

1. [ ] Notifications deliver in correct namespaces; templates in en/ur/sd/ps (no `__TODO__`)
2. [ ] Audit entries for metrics access/export, opt-out, plagiarism flags, admin overrides
3. [ ] E2E runs green (LLM/STT/embeddings mocked; no live network)
4. [ ] E2E asserts version immutability, matched-teacher anonymity, §6.19 scope
5. [ ] PR opened `milestone/M-10` → `staging`; `phase-complete-review` passes; CI green; demo clean; merged

### Out of scope
- Anything beyond the M-10 ticket set

### Notes / known gotchas
- Mock the `SCORING_MODEL` LLM, faster-whisper, and BGE-M3 embeddings in CI; use a fixture global originality index (no live cross-tenant data).

---

## Milestone notes

- **Picks up at M-09's READY_FOR_EDIT.** Edit → immutable new version → async score is the core loop; PUBLISHED is reachable but the student-facing publish surface + auto-quiz are **M-11**.
- **Every save is a new immutable version** — `lecture_versions` rows are never overwritten; only `scores_json` / `topic_relevance_pct` / `originality_score` are populated later by the async job.
- **Scoring is a separate LLM call** with the smaller `SCORING_MODEL` (STACK_LOCK §4.1, ARCH §7.10) and an evaluator persona — never folded into the generation prompt.
- **Originality is global + privacy-preserving** — cross-teacher index for school tenant; matched teacher never revealed; >0.85 flags Platform Admin silently; independent tenant isolated (§3.16).
- **`benchmark.update_weekly` is already in the locked §10.6 beat schedule** — wire to it, don't add a new beat entry.
- **Benchmark framing is always positive** and opt-out-able; admin metrics are scope-restricted (§6.19) and exclude Coordinators + independent teachers.
- **`teacher_ai_memory` ≠ student Cognitive DNA.** This is teacher coaching (Flow 5 #36); Flow 7/M-16 later extends the same table with a `reflective_response_pattern` category.
- **TipTap editor:** Flow 5 §3.5 says it's "locked per STACK_LOCK" — confirm it's actually in STACK_LOCK §12 before T-130; flag as a STACK_LOCK gap if absent (don't substitute).
- **Closers combined into T-140** (notifications + audit + E2E + PR) to fit the 12-ticket cap; this milestone's notification/audit surface is light.
- **Source flow:** Flow 5 v1 §3.5–§3.12 — finalized, no blockers.

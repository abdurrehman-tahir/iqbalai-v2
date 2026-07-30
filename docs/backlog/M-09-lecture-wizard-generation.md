# M-09 — Lecture Wizard + AI Generation (Pattern S RAG)

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** in-progress
**Estimated duration:** 3-4 weeks
**Tickets:** T-113 through T-128
**Spec source:** `flow-5-teacher-creates-lecture.md` v1 (§3.1 wizard #23, §3.2 generation #24, §3.4 voice #25, §3.13/§3.14 linking+access #21, §3.15 delivery tips #28/#41, §3.16 independent variant)

## Goal

A teacher runs the 5-step lecture creation wizard, hits Generate, and watches an AI-generated lecture stream in word-by-word with per-paragraph source badges ([Curriculum] / [Ref: Book] / [AI Knowledge]). Generation is Pattern S dual-RAG: curriculum drives structure (weighted 1.5×), references drive depth. Out-of-curriculum content falls back through reference → SearXNG → "no info." Teachers can talk to the AI during creation (voice STS loop), link lectures across grades (unidirectional), and set per-lecture access. Independent teachers get a stripped variant.

**Scope boundary:** generation only. **Edit + versions + 7-dimension scoring = M-10. Auto-quiz per student + publish = M-11.** This milestone stops at GENERATED_V1 / READY_FOR_EDIT. The lecture exists as a draft; editing, scoring, quizzes, and publishing come next.

**Demo at milestone end:**
- Teacher opens the wizard → picks a topic from the curriculum topic tree → confirms curriculum → selects reference books (Grade-Subject filtered, cross-grade toggle) → picks teaching mode → sees estimated time → Generate
- Lecture streams in word-by-word over WebSocket; each paragraph shows a source badge
- An out-of-curriculum segment falls back to reference, then SearXNG, then "I don't have information on this"
- Teacher opens a voice session, says "add an example about Newton's 3rd law," and the draft updates live
- Teacher links this lecture to a lower-grade lecture (allowed); a higher-grade link is blocked
- Teacher sets per-lecture access; an independent teacher runs the same wizard but sees only their own references and gets no auto-quiz

---

## T-113 — Lecture data model (lectures, versions, drafts, paragraphs)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** done
**Commit:** `cf19314`

### ARCH source
- `ARCHITECTURE.md` §4 (DB), §3.18 (Grade-Subject scoping), §4.21 (school + independent schemas)

### Depends on
- T-045 (GradeSubjectOffering, M-03), T-054 (library items, M-04)

### What this ticket builds

**Backend:** Migrations for `lectures {id, tenant_type, school_id (nullable), grade_subject_offering_id (nullable for independent), teacher_user_id, title, topic, lecture_type ENUM[main, mini] default main, parent_lecture_id (nullable), status, current_version, created_at, deleted_at}`; `lecture_versions {id, lecture_id, version, body, scores_jsonb (nullable, filled M-10), created_at}`; `lecture_drafts {id, teacher_user_id, wizard_state_jsonb, updated_at}`; `lecture_paragraphs {id, lecture_version_id, ordinal, text, source_metadata_jsonb}`. Note `lecture_type`/`parent_lecture_id` exist now (Flow 7 mini-lectures use them later).

**Frontend:** None.

### Acceptance (demo script)

1. [ ] All four tables exist with constraints in both schemas
2. [ ] `lecture_type` enum (main/mini) + nullable `parent_lecture_id` present (Flow 7-ready)
3. [ ] `source_metadata_jsonb` on paragraphs holds provenance
4. [ ] Independent lectures have null `grade_subject_offering_id` + null `school_id`
5. [ ] Soft-delete + versioning columns present

### Out of scope
- Scoring columns populated (M-10), quiz tables (M-11)

---

## T-114 — Wizard steps 1-2 (topic + curriculum) + draft auto-save

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.1 (Step 1 topic from curriculum tree; Step 2 curriculum confirm; auto-save)

### ARCH source
- `ARCHITECTURE.md` §5 (API), §6.19

### Depends on
- T-113 (data model), T-057 (curriculum topic tree, M-04)

### What this ticket builds

**Frontend + backend:** Wizard Step 1 (pick topic from the curriculum's `topic_tree_jsonb`; freeform fallback if structured parse degraded) and Step 2 (confirm curriculum; default = primary curriculum for the Grade-Subject). Draft auto-saves to `lecture_drafts` at every step; teacher can close + resume.

### Acceptance (demo script)

1. [ ] Step 1 lists topics from the curriculum topic tree
2. [ ] Freeform topic fallback when topic tree is degraded/empty
3. [ ] Step 2 defaults to the Grade-Subject's primary curriculum
4. [ ] Draft auto-saves; closing + reopening resumes at the same step
5. [ ] Teacher scoped to their assigned Grade-Subject offerings

### Out of scope
- Steps 3-5 (T-115), generation (T-116)

---

## T-115 — Wizard steps 3-5 (references + mode + confirm/estimate)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.1 (Step 3 references w/ filter + cross-grade toggle; Step 4 teaching mode; Step 5 confirm + estimate)

### ARCH source
- `ARCHITECTURE.md` §3.18 (cross-grade), §7.21

### Depends on
- T-114 (steps 1-2), T-063 (cross-grade library visibility, M-04)

### What this ticket builds

**Frontend + backend:** Step 3 (select reference books, filtered to `subject=this AND grade≤this AND language=pref` per Flow 3 §5.3; cross-grade toggle default off reveals lower grades). Step 4 (teaching mode: auto / manual / voice_assisted). Step 5 (confirm settings + show estimated generation time → Generate).

### Acceptance (demo script)

1. [ ] Step 3 shows references filtered by subject + grade≤this + language
2. [ ] Cross-grade toggle (default off) reveals lower-grade references; never higher
3. [ ] Step 4 offers auto / manual / voice_assisted modes
4. [ ] Step 5 shows an estimated generation time before commit
5. [ ] Generate transitions the draft to GENERATING

### Out of scope
- The generation pipeline itself (T-116)

---

## T-116 — Pattern S dual-RAG generation pipeline

**Layer:** 4
**Milestone:** M-09
**Estimate:** 3 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.2 (dual-RAG; curriculum 1.5× weight; structure vs depth)

### ARCH source
- `ARCHITECTURE.md` §7.2 (Pattern S), §7.3 (embedding BGE-M3 via Infinity), §7.7 (chunking), §8.6 (typed prompt)
- `ARCHITECTURE.md` §10.3-§10.5 (Celery, `soft_time_limit` 5 min)

### Depends on
- T-056 (RAG ingestion, M-04), T-115 (wizard → Generate)

### What this ticket builds

**Backend:** The Celery generation task: dual-RAG retrieval (curriculum chunks for sequence/structure, reference chunks for depth/examples; curriculum weighted 1.5×), LLM synthesis via typed prompt `lecture_generate_v1.py`, persist as `lectures` + v1 `lecture_versions` + `lecture_paragraphs`. NATS `lecture.generation_requested` / `lecture.version.created`. 5-min soft time limit.

**Frontend:** None (streaming in T-117).

### Acceptance (demo script)

1. [ ] Generation retrieves both curriculum + reference chunks
2. [ ] Curriculum weighted 1.5× over references in retrieval scoring
3. [ ] Structure follows curriculum order; depth pulls from references
4. [ ] Output persisted as lecture + v1 + paragraphs
5. [ ] 5-min soft limit; exceed → halt + notify
6. [ ] NATS events published

### Out of scope
- Streaming UI (T-117), source badges (T-118), fallback tiers (T-119)

---

## T-117 — Streaming generation via WebSocket + reconnect/resume

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.2 (word-by-word streaming; reconnect resumes)

### ARCH source
- `ARCHITECTURE.md` §5 (WebSocket), §7.2

### Depends on
- T-116 (generation task)

### What this ticket builds

**Backend + frontend:** Stream generation word-by-word to the frontend over a WebSocket (`lecture.gen` channel scoped to lecture_id). If the connection drops, generation continues server-side; reconnect resumes streaming from the current position.

### Acceptance (demo script)

1. [ ] Generation streams word-by-word to the teacher
2. [ ] Channel scoped to lecture_id (no cross-lecture leakage)
3. [ ] Connection drop → generation continues server-side
4. [ ] Reconnect resumes from current position
5. [ ] Stream completes → READY_FOR_EDIT state

### Out of scope
- Source badge rendering (T-118)

---

## T-118 — Per-paragraph source attribution + source badges (#26)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.2 (source tagging #26)

### ARCH source
- `ARCHITECTURE.md` §7.2 (provenance), §4 (`source_metadata_jsonb`)

### Depends on
- T-116 (generation), T-117 (streaming)

### What this ticket builds

**Backend + frontend:** Every paragraph carries provenance — a curriculum chunk ref, a reference book chunk ref, or `ai_knowledge`. Stored in `lecture_paragraphs.source_metadata_jsonb`. Source badges render in the viewer ([Curriculum] / [Ref: Book Name] / [AI Knowledge]) and persist across versions.

### Acceptance (demo script)

1. [ ] Each paragraph tagged with its actual source tier
2. [ ] Badges render: Curriculum / Ref: <name> / AI Knowledge
3. [ ] Attribution stored per paragraph, survives versioning
4. [ ] AI-extrapolated paragraphs correctly tagged `ai_knowledge`
5. [ ] Badge reflects the real tier used (not a guess)

### Out of scope
- Fallback tier logic (T-119)

---

## T-119 — Out-of-curriculum fallback tiers (#27)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.2 (#27: reference → SearXNG → "no info")

### ARCH source
- `ARCHITECTURE.md` §7.12 (Pattern A web fallback), §7.2

### Depends on
- T-116 (generation), searxng (M-00)

### What this ticket builds

**Backend:** When a segment isn't covered by curriculum: (1) reference book search → (2) web search via SearXNG → (3) "I don't have information on this." Source badge always reflects the tier actually used.

### Acceptance (demo script)

1. [ ] Curriculum-covered segment uses curriculum (no fallback)
2. [ ] Uncovered segment falls back to reference search
3. [ ] Still uncovered → SearXNG web search
4. [ ] Still uncovered → "I don't have information on this"
5. [ ] Badge reflects the actual tier at each step

### Out of scope
- General web-research agent (that's M-07 framework / Pattern A elsewhere)

---

## T-120 — Exam framework overlay context

**Layer:** 4
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.2 (exam framework overlay per Flow 4 v3 §3.5.4)

### ARCH source
- `ARCHITECTURE.md` §3.19 (Exam Framework), §8.6

### Depends on
- T-116 (generation), T-096 (framework selection, M-07)

### What this ticket builds

**Backend:** If students in the target Grade have selected an Exam Framework relevant to this Subject, inject the framework's `exam_strategy` + topic `priority_weights` as ADDITIONAL generation context (never replacement). Lectures incorporate exam-readiness language without displacing curriculum focus.

### Acceptance (demo script)

1. [ ] Framework context injected when relevant frameworks are selected by Grade students
2. [ ] Context is additive (curriculum still primary)
3. [ ] No framework selected → no overlay (clean generation)
4. [ ] Custom Persona NOT injected into lecture generation (class-wide content)

### Out of scope
- Lecture Mode "exam prep track" tab UI (M-12+)

### Notes / known gotchas
- Per §3.2: custom persona (§8.20) does NOT affect lecture generation (class-wide); only per-student surfaces.

---

## T-121 — Voice conversation during creation (#25)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 3 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.4 (voice STS loop; live draft edits)

### ARCH source
- `ARCHITECTURE.md` §5 (WebSocket audio), STACK_LOCK §4 (faster-whisper, Piper, Edge-TTS, AI4Bharat)

### Depends on
- T-116 (generation/draft exists to edit)

### What this ticket builds

**Backend + frontend:** "Talk to AI" voice session — bidirectional WebSocket audio. faster-whisper STT → LLM → Piper (en/ur) / Edge-TTS (fallback) / AI4Bharat (sd/ps) → audio back. Voice commands ("add an example about Newton's 3rd law") produce structured edit operations applied to the draft via OT. Audio retained 24h; transcripts indefinitely. Target STS loop < 2s (feasibility flagged — see notes).

### Acceptance (demo script)

1. [ ] Voice session opens; bidirectional audio works
2. [ ] STT (faster-whisper) → LLM → TTS (Piper/Edge/AI4Bharat by language) round-trips
3. [ ] Voice command edits the draft live (insert/replace/append paragraph)
4. [ ] Audio retained 24h; transcript archived with the lecture
5. [ ] Independent teachers also get voice mode

### Out of scope
- Sub-2s latency guarantee on CPU (flagged open question; best-effort at launch)

### Notes / known gotchas
- STACK_LOCK: faster-whisper (NOT raw Whisper). Sub-2s STS on CPU is an open feasibility question (Flow 5 §8 Q3) — implement the loop; latency tuning is iterative.

---

## T-122 — Cross-grade / cross-subject lecture linking (#21)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.13 (cross-grade/subject linking #21)

### ARCH source
- `ARCHITECTURE.md` §3.18 (cross-grade unidirectional rule), §7.21

### Depends on
- T-113 (lectures), T-047 (cross-grade guard, M-03)

### What this ticket builds

**Backend + frontend:** Link a lecture to related lectures across grades/subjects. The cross-grade link is unidirectional — Grade N may link to ≤N (lower); higher-grade linking blocked. Reuses the T-047 `assert_cross_grade_access` guard.

### Acceptance (demo script)

1. [ ] Teacher links a Grade 9 lecture to a Grade 8 lecture → allowed
2. [ ] Link to a Grade 10 lecture → blocked (FORBIDDEN)
3. [ ] Cross-subject linking within allowed grades works
4. [ ] Reuses the T-047 guard (no duplicate logic)
5. [ ] Links render in the lecture detail

### Out of scope
- RAG retrieval weighting from linked lectures (later)

---

## T-123 — Per-lecture access control (#21)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.14 (per-lecture access control #21)

### ARCH source
- `ARCHITECTURE.md` §6.19 (inheritance), §3.18

### Depends on
- T-113 (lectures), T-077 (student enrollment, M-06)

### What this ticket builds

**Backend + frontend:** Per-lecture access settings — by default a lecture is visible to the enrolled students of its Grade-Subject; teacher can restrict to specific sections/students. Access enforced server-side. (This is the foundation Flow 7 mini-lecture targeted distribution reuses.)

### Acceptance (demo script)

1. [ ] Default: lecture visible to the Grade-Subject's enrolled students
2. [ ] Teacher can restrict to specific sections/students
3. [ ] Unenrolled / out-of-scope students cannot access
4. [ ] Access enforced server-side (not just UI)
5. [ ] Coordinator/Admin see per §6.19 inheritance

### Out of scope
- Student viewer experience (M-12); mini-lecture targeted distribution (Flow 7/M-16)

---

## T-124 — Delivery tips + technique demo + real-world examples (#28, #41)

**Layer:** 4
**Milestone:** M-09
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.15 (delivery tips, technique demo, real-world examples #28/#41)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompts)

### Depends on
- T-116 (generation)

### What this ticket builds

**Backend + frontend:** Alongside the lecture body, generate teacher-facing delivery tips, a teaching-technique demo, and real-world examples (#28, #41) via typed prompts. Shown to the teacher in the draft review (not part of student-facing body unless the teacher includes them).

### Acceptance (demo script)

1. [ ] Delivery tips generated + shown to teacher
2. [ ] Teaching-technique demo generated
3. [ ] Real-world examples generated (#41) with cultural relevance
4. [ ] These are teacher-facing aids (separate from the lecture body)
5. [ ] Generated in the teacher's language

### Out of scope
- Student-facing rendering (M-12)

---

## T-125 — Independent teacher stripped variant

**Layer:** 4
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.16 (independent teacher stripped variant)

### ARCH source
- `ARCHITECTURE.md` §3.16 (independent tenant)

### Depends on
- T-114/T-115 (wizard), T-070 (independent teacher, M-05)

### What this ticket builds

**Backend + frontend:** Independent teachers run the same wizard but Step 3 shows only their own private uploaded references (no school library); no Grade-Subject scoping; auto-quiz NOT generated (deferred to Flow 8 generic quiz tooling); voice mode available. Lectures written to the independent schema.

### Acceptance (demo script)

1. [ ] Independent teacher runs the wizard; Step 3 shows only their private references
2. [ ] No school-library references appear
3. [ ] No Grade-Subject scoping required
4. [ ] No auto-quiz generated
5. [ ] Lecture written to independent schema; voice mode works

### Out of scope
- Independent quiz tooling (Flow 8, M-17)

---

## T-126 — Notifications + audit

**Layer:** 4 / 6
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §7 (notifications)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS), §14.10 (audit)

### Depends on
- T-116 (generation events), T-038 (notif infra, M-02), T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Notifications: generation complete / generation failed / generation timeout (teacher). NATS events for generation lifecycle. Audit entries for lecture create, generation, linking, access changes. Templates in 4 languages.

### Acceptance (demo script)

1. [ ] Generation complete/failed/timeout notify the teacher
2. [ ] NATS lifecycle events published
3. [ ] Audit entries for create/generate/link/access
4. [ ] Templates in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Publish/quiz notifications (M-11)

---

## T-127 — E2E smoke test

**Layer:** 6
**Milestone:** M-09
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` §3.1, §3.2, §3.13-§3.16

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-113 through T-126

### What this ticket builds

**Test harness:** Automated E2E: teacher runs wizard (all 5 steps, draft auto-save) → generates (dual-RAG, LLM mocked/sandboxed) → streams → source badges asserted → out-of-curriculum fallback asserted → cross-grade link allowed/blocked asserted → per-lecture access asserted → independent variant (own refs only, no auto-quiz) asserted. Runs in CI with fixture content.

### Acceptance (demo script)

1. [ ] E2E runs green end-to-end
2. [ ] Wizard + draft resume asserted
3. [ ] Generation + streaming + source badges asserted (LLM mocked)
4. [ ] Fallback tiers + cross-grade rule asserted
5. [ ] Independent variant asserted

### Out of scope
- Frontend Playwright E2E (Phase 2); voice-loop latency benchmarking

### Notes / known gotchas
- Mock LLM + SearXNG in CI (no live network). Use fixture curriculum + reference content.

---

## T-128 — Milestone M-09 PR + demo

**Layer:** 6
**Milestone:** M-09
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-5-teacher-creates-lecture.md` v1 (generation portions)

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-113 through T-127

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-09 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-09` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-127 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-09 ticket set

---

## Milestone notes

- **Generation only.** Edit + versions + 7-dim scoring = M-10; auto-quiz per student + publish = M-11. This milestone ends at GENERATED_V1 / READY_FOR_EDIT.
- **First real Pattern S dual-RAG** at generation scale (T-116) — curriculum weighted 1.5× drives structure, references drive depth. Reuses the M-04 ingestion output.
- **Source badges (#26)** are a core trust feature — every paragraph must carry honest provenance, including `ai_knowledge` when the LLM extrapolated.
- **Voice creation (T-121)** carries the open sub-2s STS feasibility question (Flow 5 §8 Q3) — implement the loop; latency tuning is iterative, CPU-only at launch.
- **Cross-grade linking (T-122)** reuses the T-047 guard — no new comparison logic.
- **`lecture_type`/`parent_lecture_id` exist from T-113** so Flow 7 mini-lectures (M-16) slot in without a schema change later.
- **Custom Persona is NOT injected into lecture generation** (class-wide content) per §3.2 — only per-student surfaces use it.
- **Source flow:** Flow 5 v1 (generation portions) — finalized, no blockers.

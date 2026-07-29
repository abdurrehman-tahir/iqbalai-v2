# M-12 — Lecture Mode Viewer + Highlight + Q&A + Voice


<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 3-4 weeks
**Tickets:** T-151 through T-165
**Spec source:** `flow-6-student-studies-lecture.md` v1 §3.1 (session lifecycle), §3.2 (viewer + TTS voice #54), §3.3 (highlight → auto-prompt → submit #55), §3.4 (AI answer side panel #56), §3.5 (hybrid input widget — text+voice base of #57)

## Goal

The first of four milestones that build Flow 6 (a student studying a published lecture). M-12 delivers the core study surface: a student opens a published lecture, reads it (text mode) or has it read aloud karaoke-style (voice mode with TTS), highlights any passage to auto-generate a question, and gets a streamed, source-cited AI answer in a side panel with multi-turn follow-ups. Questions are tagged to their content element (for Flow 7) and classified misconception/knowledge_gap (baseline). Voice question input works via STT. The reusable hybrid input widget is built here in its text+voice form.

**Scope boundary (Flow 6 is split M-12→M-15):**
- **M-12 (this):** session lifecycle #54 viewer + TTS voice, #55 highlight→Q, #56 AI answer panel, #57 text+voice base of the hybrid widget.
- **M-13:** extends the *same* hybrid widget with image attachment + vision-LLM routing (#57 full). **No second widget — M-13 extends this one.**
- **M-14:** live feedback panel #59, the full NATS JetStream consumer pipeline #60, per-session AI adaptation #61. (M-12 *emits* session/question events; it does **not** build the consumers or adaptation.)
- **M-15:** highlight persistence + auto-flashcards #58, concept enrichment + career links + mini-simulation #71, lecture rating.

So in M-12: highlights are transient triggers for questions (persistent yellow-marks + flashcards are #58/M-15); the AI answer uses a **base** custom persona (§8.20) but **not** adaptive difficulty (#61/M-14); session-end emits a summary event but post-session consumers (flashcards/DNA/review) live in M-15/M-18/M-16.

**Demo at milestone end:**
- Student opens a published lecture from their dashboard → session starts (`lecture.session.opened`)
- Text mode renders the lecture with per-paragraph source badges; student toggles **voice mode** → AI reads aloud, text scrolls in sync, with play/pause/speed/skip/download controls
- Student highlights a sentence → question box pre-fills "Explain: [text]" → 3-second auto-send (cancelable) → question submitted, tagged to its content element + classified misconception/knowledge_gap
- AI answer streams into a right side panel (bottom sheet on mobile) with source badges ([Curriculum]/[Ref]/[AI]/[Web]); clicking a badge highlights the source passage; student asks a follow-up in the same panel
- Student asks a question by voice (mic in the hybrid widget) → faster-whisper transcribes → same answer pipeline
- A student with an exam framework selected sees framework-aware overlay context on answers
- Question is private-by-policy per #72; a linked parent's read-only access respects it
- Session times out after 30 min inactivity → `session_ended` summary event emitted

---

## T-151 — Lecture session data model + lifecycle

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.1 (session bounded by opened/close or 30-min inactivity; concurrent sessions; new session on re-open)

### ARCH source
- `ARCHITECTURE.md` §4.2-4.8 (DB mixins), §4.12 (migrations), §3.16 (tenant tagging), §3.18 (lecture scoped to GradeSubjectOffering)

### Depends on
- T-142 (lecture PUBLISHED, M-11), T-077 (student enrollment, M-06)

### What this ticket builds

**Backend:** Migrations (both schemas; independent uses `self_study_sessions` in Flow 8 — here, school `lecture_sessions`): `lecture_sessions {id, lecture_id, student_user_id, mode ENUM[text,voice], status ENUM[active,ended], opened_at, last_activity_at, ended_at, tenant_type}`. Session opens on lecture open; `last_activity_at` updated on interaction; a sweeper (or lazy check) ends sessions after 30 min inactivity. Re-opening after timeout creates a NEW session row. Concurrent sessions on the same lecture (different devices) allowed — distinct `session_id`. Conversations/questions (T-160) hang under `session_id`.

**Frontend:** None.

### Acceptance (demo script)

1. [ ] Opening a published lecture creates a `lecture_sessions` row (status=active)
2. [ ] 30 min of no interaction → session ends (status=ended, `ended_at` set)
3. [ ] Re-opening after timeout creates a new session, not a resume
4. [ ] Two devices on the same lecture → two distinct active sessions
5. [ ] Session is tenant-tagged; scoped to the student's enrollment in the lecture's GSO

### Out of scope
- Event emission (T-163), post-session processing (M-15/M-16/M-18)

---

## T-152 — Student lecture viewer: text mode (#54)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.2 (TEXT_MODE — lecture text rendered with source badges)

### ARCH source
- `ARCHITECTURE.md` §5.1-5.7 (API), §3.18 (GSO scope), §6.19 (access), §12 (frontend), §13 (i18n)

### Depends on
- T-151 (session), T-142 (published lecture), T-123 (per-lecture access, M-09)

### What this ticket builds

**Frontend + backend:** The student lecture viewer rendering the published lecture version in text mode — paragraphs with per-paragraph source badges ([Curriculum] / [Ref: Book] / [AI Knowledge] / [Web] / [No Source]) per Flow 5 #26/#27. Access-gated: only students enrolled in the lecture's Grade-Subject offering, respecting the per-lecture access set (T-123). Renders in the student's UI language (RTL-aware). This is the surface highlights (T-156) and the answer panel (T-159) attach to.

### Acceptance (demo script)

1. [ ] Enrolled student opens a published lecture → text renders with source badges
2. [ ] Non-enrolled / access-restricted student is blocked (403)
3. [ ] Only the latest published version is shown
4. [ ] RTL languages render correctly
5. [ ] Viewer opening is what triggers the T-151 session

### Out of scope
- Voice mode (T-153/T-154), highlights (T-156)

---

## T-153 — TTS lecture audio generation + caching (#54)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.2 (TTS engines per language; audio cached per lecture; lazy gen; invalidate on re-edit)

### ARCH source
- `ARCHITECTURE.md` §10.5 (`tts.generate_audio` Celery task), §11.19 (lecture audio cached in MinIO), §4 (audio cache reference), STACK_LOCK §4 (TTS engines)

### Depends on
- T-152 (viewer), T-116 (lecture content, M-09)

### What this ticket builds

**Backend:** Lecture audio generation via the locked TTS stack — Piper for English/Urdu (fast path), Edge-TTS fallback, AI4Bharat for Sindhi/Pashto (STACK_LOCK §4; replaces v2 doc's ElevenLabs). Lazy: generated on first voice-mode request (`tts.generate_audio` Celery task), cached in MinIO per lecture+language; subsequent plays serve cache. Audio invalidated + regenerated on lecture re-edit (launch = full regen; per-paragraph regen is a noted Phase-2 optimization, Open Q2). Sentence-level alignment metadata stored for karaoke sync (T-154).

### Acceptance (demo script)

1. [ ] First voice-mode request generates audio via the correct engine for the language
2. [ ] Audio cached in MinIO; second request serves cache (no regen)
3. [ ] Lecture re-edit invalidates + regenerates audio
4. [ ] Sentence-level alignment metadata produced for sync
5. [ ] All 4 languages route to the correct TTS engine (§13)

### Out of scope
- The player UI (T-154); word-level sync (Phase 2, Open Q1 — sentence-level at launch)

---

## T-154 — Voice mode karaoke player (#54)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.2 (VOICE_MODE — karaoke read-aloud, text scrolls in sync; controls)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §13 (i18n/RTL)

### Depends on
- T-153 (audio + alignment), T-152 (viewer)

### What this ticket builds

**Frontend:** Voice-mode toggle in the viewer → karaoke player: AI reads aloud while text highlights/scrolls in sync (sentence-level per Open Q1). Controls: play/pause, ±10s skip, speed (0.5/0.75/1×/1.25/1.5/2×), download full lecture audio. Toggling back to text mode or session end stops playback. Voice and text mode are the two `lecture_sessions.mode` values.

### Acceptance (demo script)

1. [ ] Toggle to voice mode → audio plays, text scrolls/highlights in sync (sentence-level)
2. [ ] All controls work (play/pause, ±10s, speed, download)
3. [ ] Toggle back to text mode stops audio
4. [ ] Mode change reflected on the session
5. [ ] Works RTL

### Out of scope
- Voice *question* input (T-155 hybrid widget)

---

## T-155 — Hybrid text/voice question input widget (v1 of #57)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (single reusable component; text + voice paths; live transcription)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend; canonical reusable component), STACK_LOCK §4 (faster-whisper), §8.6 (input feeds Q&A)

### Depends on
- T-152 (viewer)

### What this ticket builds

**Frontend + backend:** The **canonical reusable** hybrid input component in its text+voice form: text input + mic icon; recording shows a red pulse with live faster-whisper transcription into the box; stops on tap-mic-again / ESC / 30-second silence. This is the same component Flow 5 chat, Flow 8, Flow 11 will reuse — **frontend reuse is mandatory; no duplicate input implementations.** Built so M-13 extends it with the image-attach icon + vision routing (do not fork it).

### Acceptance (demo script)

1. [ ] One reusable component renders text input + mic
2. [ ] Recording → red pulse + live transcription via faster-whisper
3. [ ] Stops on tap-again / ESC / 30s silence
4. [ ] Component is structured for M-13 to add image attach + vision routing without a rewrite
5. [ ] Used by both the highlight question box (T-156) and follow-ups (T-160)

### Out of scope
- Image attachment + vision LLM (#57 full — M-13)

### Notes / known gotchas
- §3.5 mandates a SINGLE widget reused everywhere. M-12 builds the text+voice base; M-13 extends THIS component (image chips + `attached_images[]` + Groq Llama-3.2-Vision routing). Forking it in M-13 would violate the reuse rule — extend, don't duplicate.

---

## T-156 — Highlight → auto-prompt → submit (#55)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.3 (selection → prefilled box → 3s countdown → submit; content-element tagging)

### ARCH source
- `ARCHITECTURE.md` §5.9-5.10 (idempotency, If-Match for concurrent submissions), §8.6 (feeds Q&A), §9 (`student.question.asked` event)

### Depends on
- T-155 (input widget), T-152 (viewer), T-113 (lecture paragraphs / source chunks, M-09)

### What this ticket builds

**Frontend + backend:** Text selection in the viewer opens the question box pre-filled `Explain: [highlighted text]` (editable). A 3-second auto-send countdown fires only if the student doesn't interact within 3s; any keystroke / mic activation cancels it. On submit, the question is **auto-tagged with its content element** (`lecture_id`, `paragraph_id`, `source_chunk_id` when the highlight sits in a source-tagged paragraph) — this is what lets Flow 7 aggregate questions per content element. Emits `student.question.asked` with content + position metadata. Idempotent submission (§5.10) so a double-tap doesn't double-ask.

### Acceptance (demo script)

1. [ ] Selecting text opens a prefilled, editable question box
2. [ ] 3s auto-send fires only without interaction; any keystroke/mic cancels
3. [ ] Submitted question carries lecture_id + paragraph_id + source_chunk_id (when applicable)
4. [ ] `student.question.asked` emitted with position metadata
5. [ ] Double-submit is idempotent

### Out of scope
- Persistent yellow highlight marks (#58 — M-15); the answer itself (T-158)

---

## T-157 — Question classification (misconception vs knowledge_gap) (#55)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.3 (auto-classify misconception/knowledge_gap; Phase 1 baseline)

### ARCH source
- `ARCHITECTURE.md` §8.6 (typed prompt `question_classifier_v1.py`)

### Depends on
- T-156 (question submitted)

### What this ticket builds

**Backend:** Each submitted question is auto-classified `misconception` (wrong mental model) or `knowledge_gap` (never learned) via the `question_classifier_v1` typed prompt. Baseline accuracy target 75%+ (Open Q3; refined in Flow 9 Phase 5 with Cognitive DNA training data — not this milestone). Stored on the question record; feeds Flow 7 aggregation + later Flow 9.

### Acceptance (demo script)

1. [ ] Each question gets a classification stored on its record
2. [ ] Uses the `question_classifier_v1` typed prompt
3. [ ] Classification available to downstream (Flow 7 aggregation)
4. [ ] Baseline only — no Cognitive-DNA-informed refinement (that's Flow 9)

### Out of scope
- Flow 9 refinement of the classifier

---

## T-158 — AI answer pipeline (#56 backend)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 3 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.4 (streamed answer; source badges per #26/#27)

### ARCH source
- `ARCHITECTURE.md` §7.3-7.10 (Pattern S retrieval), §7.12 (Pattern A web fallback for out-of-curriculum, Flow 5 #27), §8.6 (`lecture_qa_v1.py`), §8.20 (base custom persona prepended)

### Depends on
- T-156 (question + content element), T-116 (lecture + source corpus, M-09)

### What this ticket builds

**Backend:** The answer pipeline — Pattern S RAG retrieval scoped to the lecture's curriculum + reference corpus (§7.3-7.10), answered via the `lecture_qa_v1` typed prompt, **streamed** token-by-token. Source badges computed per Flow 5 #26/#27 ([Curriculum] / [Ref: Book] / [AI Knowledge] / [Web] / [No Source]). Out-of-curriculum questions fall back to Pattern A web search (§7.12, Flow 5 #27) and are badged [Web]. A **base** custom persona (§8.20) is prepended to the system prompt (static per student/session — adaptive difficulty #61 is M-14). Answer + source spans returned for the panel (T-159).

### Acceptance (demo script)

1. [ ] Question → streamed answer grounded in the lecture's curriculum/reference corpus
2. [ ] Source badges correct per #26/#27; out-of-curriculum → Pattern A web fallback, badged [Web]
3. [ ] Base custom persona prepended (no adaptive difficulty — that's M-14)
4. [ ] Answer in the question's language (§13)
5. [ ] Source spans returned so the panel can deep-link to passages

### Out of scope
- Adaptive difficulty #61 (M-14); the panel UI (T-159)

---

## T-159 — AI answer side panel UI (#56 frontend)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.4 (side panel / bottom sheet; header quote; streamed answer; source-badge click → source passage; anchored on scroll)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §13 (i18n/RTL)

### Depends on
- T-158 (answer + source spans), T-152 (viewer)

### What this ticket builds

**Frontend:** The answer surface — slide-in side panel (40% width desktop) / bottom sheet (mobile), same interaction model. Header shows the quoted highlight + question; the streamed answer renders below with live source badges. Lecture text scrolls behind; panel stays anchored. Clicking a source badge highlights the source passage in the document sidebar (Flow 5 §3.2 attribution).

### Acceptance (demo script)

1. [ ] Panel slides in (desktop) / bottom sheet (mobile) on submit
2. [ ] Header shows quoted highlight + question; answer streams below
3. [ ] Source badge click → highlights the source passage
4. [ ] Panel stays anchored while lecture scrolls behind
5. [ ] RTL-correct

### Out of scope
- Multi-turn persistence (T-160)

---

## T-160 — Multi-turn follow-up + questions tab (#56)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.4 (multi-turn in same panel; conversation grouped under session under lecture; persists; reopenable from "questions" tab)

### ARCH source
- `ARCHITECTURE.md` §4 (conversation model), §5 (API)

### Depends on
- T-159 (panel), T-158 (pipeline), T-151 (session)

### What this ticket builds

**Frontend + backend:** Follow-up questions continue in the same panel as a multi-turn conversation — `conversation_id` grouped under `session_id` under `lecture_id`. Conversations persist after the panel closes and are reopenable from a "questions" tab on the lecture. Each follow-up reuses the hybrid widget (T-155) + answer pipeline (T-158).

### Acceptance (demo script)

1. [ ] Follow-up continues the same conversation in the panel
2. [ ] Conversation grouped conversation_id → session_id → lecture_id
3. [ ] Closing the panel preserves the conversation
4. [ ] "Questions" tab lists + reopens past conversations for the lecture
5. [ ] Follow-ups support text + voice (hybrid widget)

### Out of scope
- Cross-lecture question history (Phase 2)

---

## T-161 — Exam framework overlay on AI answers

**Layer:** 5
**Milestone:** M-12
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.19 reference + §10 (framework may overlay context on AI answers, not lecture body)

### ARCH source
- `ARCHITECTURE.md` §8.21 (Exam Framework agent — overlay context when student has framework selected), §3.19

### Depends on
- T-158 (answer pipeline), T-220-range exam framework (M-07)

### What this ticket builds

**Backend:** When the student has an exam framework selected (M-07), the Exam Framework agent (§8.21) overlays framework-aware context onto AI answers — e.g. exam-relevant emphasis, framework terminology — **on the answer only, never altering the lecture body**. Folds the M-09 deferred "Lecture Mode exam-prep overlay" hook (the answer-overlay portion; a standalone exam-prep study-plan tab, if wanted, is separate/Phase 2).

### Acceptance (demo script)

1. [ ] Student with a framework selected → answers carry framework-aware overlay context
2. [ ] Student without a framework → normal answers (no overlay)
3. [ ] Overlay affects the AI answer only, never the lecture body
4. [ ] Uses §8.21 Exam Framework agent

### Out of scope
- A standalone exam-prep track tab UI (Phase 2 / separate)

---

## T-162 — Permissions + privacy matrix (#72)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §4 (permissions matrix), §3.x privacy #72; Open Q12 (default = share)

### ARCH source
- `ARCHITECTURE.md` §6.13 (ParentChildLink read-only, subject to #72), §6.19 (inheritance), §3.16 (independent tagging), §14.10 (audit #72 changes)

### Depends on
- T-156 (questions), T-160 (conversations), T-081 (parent link, M-06)

### What this ticket builds

**Backend + frontend:** Enforce the Flow 6 permissions matrix — student owns their session/questions/answers; teacher receives question *signals* via events (no direct UI here); a linked parent has read-only visibility **subject to privacy #72**; Coordinator/Admin per §6.19. Privacy #72 default = share-with-teacher (Open Q12), student can opt out anytime; #72 changes audit-logged (§14.10). Independent students' sessions/events tagged `tenant_type=independent` (Open Q13).

### Acceptance (demo script)

1. [ ] Student sees only own sessions/questions
2. [ ] Linked parent read-only access respects #72 (opted-out = hidden)
3. [ ] #72 toggle works; changes audit-logged
4. [ ] Coordinator/Admin visibility per §6.19
5. [ ] Independent sessions tagged `tenant_type=independent`

### Out of scope
- Teacher's next-day-review consumption of these signals (Flow 7 / M-16)

---

## T-163 — Session + question event emission (NATS)

**Layer:** 5
**Milestone:** M-12
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.1 (events at every interaction), §3.8 reference (#60 pipeline is M-14)

### ARCH source
- `ARCHITECTURE.md` §9 (NATS JetStream `student.lecture.*` subjects), §9.21 (namespaces), §3.16 (tenant-tagged events)

### Depends on
- T-151 (session), T-156 (questions), T-038-range (NATS infra, M-01)

### What this ticket builds

**Backend:** Emit the session/interaction events M-12 produces onto NATS JetStream `student.lecture.*` — `lecture.session.opened`, `student.question.asked` (already in T-156), `student.highlight.created`, `lecture.session.ended` (with session summary). Events tagged with tenant_type. **M-12 emits only** — the full consumer pipeline (#60), live feedback (#59), and per-session adaptation (#61) are M-14; the nightly analytics aggregator (Flow 7 next-day review) is M-16; the Cognitive DNA consumer is Flow 9 / M-18.

### Acceptance (demo script)

1. [ ] Session open/end + question + highlight events published to `student.lecture.*`
2. [ ] `lecture.session.ended` carries a session summary
3. [ ] Events tenant-tagged (Open Q13: independent on same streams, tagged)
4. [ ] No consumers built here — emission only (verified: M-14 owns the pipeline)
5. [ ] Events durable on JetStream (replay-safe per Open Q6)

### Out of scope
- Consumer pipeline #60, live feedback #59, adaptation #61 (all M-14); analytics aggregation (Flow 7/M-16); DNA update (Flow 9/M-18)

### Notes / known gotchas
- BLOCKED-HOOK: Cognitive DNA interaction-signal consumer (session/question events → DNA update) → Flow 9 / M-18 (events emitted here; consumer built when Flow 9 ships)
- Flow 7 (M-16, drafted) and the M-14 analytics pipeline also consume these events — those are normal forward dependencies, not blocked.

---

## T-164 — Notifications + audit + i18n

**Layer:** 5 / 6
**Milestone:** M-12
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §7 (notifications), §3.x (#72 audit), i18n throughout

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces `lectures`/`system`), §14.10 (audit), §13 (i18n; AI answers in question language; TTS per language)

### Depends on
- T-151 through T-163

### What this ticket builds

**Backend:** Notifications in correct namespaces (per Flow 6 §7 — minimal in this flow; mostly event-driven). Audit entries for #72 privacy changes + admin overrides. i18n sweep — viewer UI in en/ur/sd/ps (RTL), AI answers returned in the question's language, TTS routed per language; no `__TODO__` in production strings.

### Acceptance (demo script)

1. [ ] Notifications (if any per §7) in correct namespaces, 4 languages
2. [ ] #72 changes + admin overrides audit-logged
3. [ ] Viewer UI in all 4 languages, RTL correct
4. [ ] AI answer language follows the question; TTS routes per language
5. [ ] No `__TODO__` strings

### Out of scope
- Anything beyond M-12 scope

---

## T-165 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-12
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.1-§3.5

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-151 through T-164

### What this ticket builds

**Test + PR:** Automated E2E (LLM / TTS / STT / embeddings mocked; no live network) — open published lecture → session created → text mode renders with source badges → toggle voice mode (audio gen mocked, sync metadata asserted) → highlight text → prefilled box → submit (content-element tags asserted) → classification stored → streamed answer with source badges (curriculum + a web-fallback case) → source-badge click resolves a passage → voice follow-up via hybrid widget → exam-framework overlay case → #72 privacy + parent read-only asserted → events emitted on `student.lecture.*` → 30-min timeout ends session. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais, merge to `staging`; tickets = commits, merge-commit not squash per BRANCHING.md).

### Acceptance (demo script)

1. [ ] E2E green (all models mocked; no live network)
2. [ ] Asserts content-element tagging, source badges, web-fallback, voice path, exam overlay
3. [ ] Asserts #72 privacy + parent read-only + tenant tagging
4. [ ] Asserts session lifecycle (open → timeout → end + summary event)
5. [ ] PR `milestone/M-12-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; demo clean; merged

### Out of scope
- Anything beyond the M-12 ticket set

---

## Milestone notes

- **First of four Flow 6 milestones.** M-12 = study surface (#54/#55/#56 + #57 text+voice base). M-13 = #57 image+vision (extends the *same* widget). M-14 = #59 live feedback + #60 NATS consumer pipeline + #61 adaptation. M-15 = #58 flashcards + #71 enrichment + rating.
- **The hybrid widget (T-155) is the canonical reusable input** — M-13 extends it (image+vision), does not rebuild it. Same component is reused by Flow 5/8/11.
- **M-12 emits events; it does not consume them.** The full NATS pipeline, live feedback, and adaptation are M-14. M-12 just publishes `student.lecture.*`.
- **Base persona only.** AI answers use a static §8.20 persona; adaptive difficulty (#61) is M-14.
- **Highlights are transient here.** Persistent yellow-marks + auto-flashcards (#58) are M-15.
- **BLOCKED-HOOK** (T-163): Cognitive DNA interaction-signal consumer → Flow 9 / M-18 (events emitted now; consumed when Flow 9 ships). Flow 7 (M-16) review aggregation + M-14 analytics also consume these events — normal forward deps, not blocked.
- **Open questions:** the M-12-relevant ones (Q1 sentence-level karaoke, Q2 full TTS regen on edit, Q3 75% classifier target, Q12 #72 default=share, Q13 independent on same NATS streams) are built to the spec's launch recommendations. The unresolved design questions (Q4/Q5/Q7/Q8/Q9/Q10/Q11) all belong to M-13/M-14/M-15 features — confirm with Awais before those milestones.
- **Source flow:** Flow 6 v1 §3.1-§3.5 — drafted with open questions; M-12-relevant ones have adopted launch recommendations (none blocking).

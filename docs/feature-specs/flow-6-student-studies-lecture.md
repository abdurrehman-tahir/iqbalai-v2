# Flow 6 — Student Studies a Lecture

**Status:** draft (v2 — adds image attachments to hybrid widget #57)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy), §4 (DB patterns), §5 (API), §6 (auth + permission inheritance §6.19), §7 (RAG pipeline), §8 (LLM, esp. §8.20 Custom Persona, §8.21 Exam Framework), §9 (NATS JetStream event pipeline), §9.21 (notification namespaces), §10 (Celery), §11.19 (upload profiles), §13 (i18n)
**Related feature specs:** `flow-3-teacher-onboarding.md`, `flow-4-student-onboarding.md` (Mode selection + Cognitive DNA seeded by diagnostic), `flow-5-teacher-creates-lecture.md` (lectures published by teachers), `flow-7-next-day-review.md` (future — questions from this flow seed mini-lectures), `flow-8-self-study.md` (future — flashcards from #58 land in spaced repetition queue), `flow-9-ai-intelligence.md` (future — Cognitive DNA receives interaction signals from this flow)
**v2 doc features covered:** #50, #54, #55, #56, #57, #58, #59, #60, #61, #71

---

## 1. Purpose

A school student in Lecture Mode consumes a teacher-published lecture (created via Flow 5). This flow owns the entire study experience: reading or listening, asking questions by selection or voice, highlighting and flashcard generation, live feedback during the session, and AI adaptation when the student is stuck.

It also establishes a piece of cross-cutting infrastructure that powers later flows: the **real-time event streaming pipeline** (#60) via NATS JetStream — every student interaction is published as an event consumed by (1) the live feedback panel via WebSocket, (2) the AI session context updater, and (3) the nightly analytics aggregator (used by Flow 7 next-day review and Flow 9 Cognitive DNA).

Critical foundations:

- **Lecture viewer UI** (text + voice/karaoke mode #54)
- **Highlight → auto-prompt question flow** (#55, #56)
- **Hybrid text / voice / image input widget** (#57) — reusable across all student surfaces (lecture Q&A, group study, study plan, self-study); supports text typing, voice transcription, AND image attachments (drag-drop, paste, click; vision-LLM routing for image questions)
- **Highlight persistence + auto-flashcards** (#58) — feeds spaced repetition deck (Flow 8 territory)
- **Live feedback panel** (#59) updates every 60s; nudges at 10-minute stuck threshold
- **NATS JetStream event pipeline** (#60) — Day 1 architecture decision (replaces v2 doc's Kafka)
- **Per-session AI adaptation** (#61) — angle/metaphor switch on 2+ repeat questions
- **Real-world app + career links + mini simulation** (#71) — concept enrichment cached per concept

**Independent students:** this flow does NOT apply directly — they are locked to Self-Study Mode (Flow 8) per Flow 4 v3 §3.2. The reusable widget (#57) and event pipeline (#60) ARE used by independent students in Flow 8.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Student** | Primary actor. In Lecture Mode (#53). Opens lectures from their Grade-Subject teachers; reads/listens; asks questions; highlights; gets nudged; gets adaptive AI. |
| **Parent (linked)** | Read-only view of student's lecture-mode interactions per Flow 10 (no direct UI in this flow). Visibility subject to privacy setting #72. |
| **Teacher (assigned)** | Receives signal of student questions/highlights via NATS pipeline; consumed by Flow 7 next-day review. No direct UI in this flow. |
| **Coordinator / School Admin / District+Platform** | Per §6.19: inherited read access; consume aggregate signals in Flow 11 dashboards. No direct UI here. |
| **Independent Student** | DOES NOT appear in this flow. Self-Study Mode only (Flow 8). |

---

## 3. Lifecycle

### 3.1 Lecture session lifecycle

```
   LECTURE_OPENED              (student opens a published lecture from their dashboard)
       ↓ session begins; NATS event `lecture.session.opened`
   STUDYING_TEXT_MODE  OR  STUDYING_VOICE_MODE  (student chooses mode #54)
       ↓ during session: highlights (#55), questions (#55-57), live feedback (#59)
       ↓ events streamed to NATS at every interaction (#60)
   ACTIVE
       ↓ student exits OR session times out (30 min inactive)
   SESSION_ENDED               (final NATS event with session summary)
       ↓ background processing
   POST_SESSION_PROCESSING     (flashcards updated #58; Cognitive DNA updated per Flow 9; next-day review collection per Flow 7)
   COMPLETE
```

**Locked rules:**
- A session is bounded by an `opened` event and either an explicit close OR 30 minutes of inactivity (no clicks, no scroll, no keyboard).
- Re-opening the same lecture after timeout creates a NEW session.
- Concurrent sessions on the same lecture (different devices) allowed — session_id distinguishes; events tagged.
- Session events flow through NATS JetStream `student.lecture.*` subjects per §9 / §9.21.

### 3.2 Lecture viewer mode lifecycle (#54)

```
   TEXT_MODE                   (default: lecture text rendered in viewer)
       ↓ student toggles
   VOICE_MODE                  (karaoke-style: AI reads aloud; text scrolls in sync)
       ↓ student toggles back OR session ends
```

**Locked rules:**
- **TTS:** Piper for English/Urdu fast path; Edge-TTS fallback; AI4Bharat for Sindhi/Pashto (per STACK_LOCK §4; replaces v2 doc's ElevenLabs).
- **Audio player controls:** play/pause, ±10s skip, speed (0.5 / 0.75 / 1× / 1.25 / 1.5 / 2×), download (lecture's full audio).
- **Karaoke sync:** sentence-level alignment; word-level optional via Piper's phoneme alignment (Phase 2 enhancement).
- **Audio cached per lecture** in MinIO. Generation: lazy on first request; subsequent plays serve cached audio. Audio invalidated on lecture re-edit.
- **Voice questions in voice mode:** mic icon active; faster-whisper STT transcribes; question flows through same answer pipeline as text questions.

### 3.3 Highlight → Auto-Prompt → Submit lifecycle (#55)

```
   STUDENT_SELECTS_TEXT        (text selection event in editor)
       ↓ question box appears
   QUESTION_BOX_PREFILLED      ("Explain: [highlighted text]")
       ↓ student edits, clears, OR taps mic to add voice context
   QUESTION_READY              (text + optional voice transcription)
       ↓ 3-second auto-send countdown (cancelable)
   QUESTION_SUBMITTED          (NATS event `student.question.asked` with content + position metadata)
       ↓ AI answers (see §3.4)
   ANSWERED
```

**Locked rules:**
- Selection triggers question box; default text "Explain: [highlighted text]" is editable.
- 3-second auto-send countdown only fires if student doesn't interact within 3s; any keystroke / mic activation cancels.
- Each question is auto-tagged with **content element**: lecture_id, paragraph_id, source_chunk_id (if highlighted text is inside a source-tagged paragraph). This enables Flow 7 to aggregate questions per content element.
- Each question is auto-classified as `misconception` (wrong mental model) or `knowledge_gap` (never learned) per LLM classifier (Phase 1 baseline; refined in Flow 9 Phase 5).
- Mic icon opens the hybrid text/voice widget (#57).
- Highlighted text persists per #58 (yellow mark on return).

### 3.4 AI answer side panel lifecycle (#56)

```
   QUESTION_SUBMITTED
       ↓ side panel slides in from right (40% width desktop) OR bottom sheet (mobile)
   PANEL_OPENED
       ↓ panel header: quoted highlight + question
       ↓ streamed AI answer below; live source badges per paragraph
   ANSWER_STREAMING
       ↓ student reads; may add follow-up
   FOLLOW_UP                    (multi-turn conversation in same panel)
       ↓ student closes panel OR opens another highlight
   CLOSED                       (conversation persists; reopenable from "questions" tab)
```

**Locked rules:**
- Panel state preserved on scroll — lecture text scrolls behind the panel; panel stays anchored.
- Mobile: bottom sheet replaces side panel; same interaction model.
- Multi-turn conversation in same panel; conversation_id grouped under session_id under lecture_id.
- Source badges on AI answers per Flow 5 #26/#27 rules: [Curriculum] | [Ref: Book Name] | [AI Knowledge] | [Web] | [No Source].
- Source badge click → highlights source passage in document sidebar (Flow 5 §3.2 source attribution).

### 3.5 Hybrid text/voice/image input widget lifecycle (#57)

Reusable component used in: lecture Q&A panel, creation chat (Flow 5), group study (Flow 11), study plan creation (Flow 8), self-study (Flow 8). Same widget everywhere.

```
   IDLE                         (text input visible; mic icon + image icon to the right)
       ↓ student types, clicks mic, OR attaches image (drag-drop OR paste OR icon-click)
   TYPING  OR  RECORDING  OR  IMAGE_ATTACHED
       (Recording: red pulse indicator; live transcription appears in input box)
       (Image: thumbnail preview shown below text input; X to remove; multiple stack as chips)
       ↓ student stops recording (tap mic again) OR adds more (text + voice + image freely combinable)
   READY                        (text in box + optional voice transcript + optional image attachments [0-3])
       ↓ student hits send
   SUBMITTED                    (request includes text + attached_images[] MinIO keys; routed to vision-capable LLM if images present)
```

**Locked rules:**
- Single reusable React component. **Frontend reuse mandatory** — if a feature needs text/voice/image input, it MUST use this widget. No duplicate implementations.
- Live transcription via faster-whisper (per STACK_LOCK §4).
- Visual: text input with mic icon + image-attach icon; mic toggle to red pulse during recording; image thumbnails render as chips below input.
- Stops recording on tap-mic-again, ESC, or 30-second silence.
- Image attachment: drag-drop, paste (Ctrl/Cmd+V), or click image-attach icon. Max 3 images per question; max 5 MB each.
- Image formats: JPEG, PNG, WEBP. Upload profile `student_question_image` per ARCHITECTURE §11.19 — EXIF stripped at ingest, MinIO storage scoped per-tenant, 1-year retention.
- **LLM routing:** if `attached_images[]` is present, request routes to vision-capable model (Groq Llama-3.2-Vision); pure text/voice questions route to default text model. Cost difference (~2-3× per call with images) acceptable.
- Frontend-master skill references this as a canonical pattern.

### 3.6 Highlight persistence + auto-flashcards lifecycle (#58)

```
   STUDENT_HIGHLIGHTS_TEXT      (per #55)
   HIGHLIGHT_PERSISTED          (highlights table row: lecture_id, text_range, content)
       ↓ AI answer paired with highlight
   FLASHCARD_AUTO_CREATED       (front: highlight; back: AI answer; tagged for lecture + concept)
       ↓ added to spaced-repetition deck (Flow 8 ownership)
   IN_SPACED_REP_QUEUE
       ↓ on lecture return
   HIGHLIGHTS_VISIBLE_AS_MARKS  (yellow marks at original positions)
```

**Locked rules:**
- Highlight stored with text_range (offset + length), highlighted text content, lecture_id, AI response.
- Auto-flashcard generation runs on every highlight+answer pair; deduplicated by hash of (highlight_text, lecture_id).
- "My Highlights" tab visible in student dashboard; chronological list with lecture + concept tags.
- Spaced repetition implementation is Flow 8's domain (py-fsrs per STACK_LOCK §4); this flow only publishes the flashcard event.
- Yellow marks rendered via lecture viewer overlay on return.

### 3.7 Live feedback panel lifecycle (#59)

```
   PANEL_HIDDEN                 (default state, until session is N minutes in)
       ↓ panel auto-shows after 2 minutes of activity
   PANEL_VISIBLE                (bottom-right; collapsible)
       ↓ updates every 60 seconds via WebSocket-pushed NATS events
   UPDATING                     (live: time on topic, questions asked, mastery estimate)
       ↓ student stuck > 10 min with 0 questions
   NUDGE_TRIGGERED              ("Been here 10 min — need help?")
       ↓ student acknowledges, asks question, OR ignores
   CONTINUED                    (panel keeps updating until session ends)
```

**Locked rules:**
- Update cadence: every 60 seconds; driven by NATS JetStream consumer pushing to WebSocket channel `student.live_feedback.{user_id}`.
- Metrics shown:
  - Time on this topic (current lecture or current chapter span)
  - Questions asked this session
  - Current mastery estimate (from Cognitive DNA, Flow 9)
  - Daily goal status (if student set one via #69 in Flow 8)
- **Nudge trigger:** >10 minutes on same page + 0 questions asked → soft nudge "Been here 10 min — need help?" with quick-action buttons (rephrase last paragraph / list key concepts / change to voice mode).
- Nudge appears once per stuck-session; doesn't repeat to avoid annoying loop.
- Panel collapsible by student; collapsed state persists for that session.

### 3.8 NATS JetStream event pipeline lifecycle (#60)

**Foundation infrastructure**, Day 1 — replaces v2 doc's Kafka/Kinesis decision with NATS JetStream per STACK_LOCK §4.

```
   STUDENT_INTERACTION_EVENT    (highlight, question, scroll, time-on-page, page-change, mode-switch)
       ↓ published to NATS subject `student.lecture.*` with structured envelope
   FAN_OUT                      (3 consumers receive in parallel)
       │
       ├─→ Live Feedback Consumer    (pushes to WebSocket; powers #59)
       ├─→ AI Session Context Consumer (updates per-session difficulty log for #61)
       └─→ Analytics Consumer        (writes to event store; nightly aggregator reads for Flow 7 + Flow 9 + Flow 11)
   CONSUMED
```

**Locked rules:**
- **NATS JetStream** (locked per STACK_LOCK §4 / §9). v2 doc's "Kafka vs Kinesis" decision is settled — we use NATS.
- **Subject pattern:** `student.lecture.{event_type}` (e.g., `student.lecture.question_asked`, `student.lecture.highlight_created`, `student.lecture.session_opened`, `student.lecture.session_closed`).
- **Event envelope** per §9: includes tenant_id, tenant_type (school in this flow's case), user_id, session_id, lecture_id, timestamp, event_type, payload.
- **Three consumers run independently** with separate durable consumer subscriptions. One slow consumer cannot block the others.
- **Event retention:** JetStream stream retention 7 days for live processing; analytics consumer persists to Postgres `student_events` table for long-term aggregation.
- **Backpressure:** if any consumer lags > 30 seconds behind, alert Platform Admin (`system.event_pipeline_lag`).
- **Independent students:** same NATS infrastructure but events tagged `tenant_type=independent` and routed to independent tenant's event store. They use Flow 8 surfaces, not Flow 6.

### 3.9 Per-session AI teaching adaptation lifecycle (#61)

```
   SESSION_STARTED              (per #3.1)
       ↓ student asks questions
   QUESTION_LOGGED              (question + sub-topic auto-tagged)
       ↓ session_difficulty_log accumulates
   SAME_SUB_TOPIC_2X            (2+ questions on same sub-topic in this session)
       ↓ AI session context updated
   APPROACH_SWITCHED            (system prompt now includes: "Student struggling with [X] — try different angle: example/metaphor/analogy/visual")
       ↓ student asks next question
   ANSWERED_WITH_DIFFERENT_ANGLE
       ↓ session ends
   LONG_TERM_LOG                (difficulty signals exported to Cognitive DNA via Flow 9)
```

**Locked rules:**
- Sub-topic identification via lecture_paragraphs.source_chunk_id (mapping back to curriculum topic_tree from Flow 3 #18).
- 2+ threshold for the angle-switch trigger; configurable via env var `AI_ADAPT_QUESTION_THRESHOLD` (default 2).
- Angle types: example / metaphor / analogy / visual description / real-world application. Cycles through; tracked in `session_difficulty_log.tried_angles`.
- **Custom Persona interaction:** if student has Custom Persona active (per ARCHITECTURE §8.20), the persona description is prepended to system prompt alongside the angle-switch context. Adaptation respects persona's tone/structure preferences.
- Long-term cognitive DNA update is an analytics-consumer responsibility (Flow 9).

### 3.10 Real-world app + career links + mini simulation lifecycle (#71)

```
   CONCEPT_ENCOUNTERED          (student reaches a concept in lecture)
       ↓ system checks cache
   CACHE_HIT                    (concept_applications row exists) → render
   OR CACHE_MISS
       ↓ Celery task `concept.enrich_applications`
   GENERATING                   (LLM generates real-world uses + career links + mini-simulation prompt)
       ↓ persisted
   ENRICHED                     (concept_applications row created; rendered to student)
       ↓ student interacts with mini-simulation
   SIMULATION_STATE_SAVED       (per-student save state)
```

**Locked rules:**
- Concept enrichment is **cached PER CONCEPT**, not per student. First student to encounter a concept triggers generation; subsequent students use cached version. Cache invalidated quarterly (~90 days, configurable).
- Career links use a controlled vocabulary: `careers` table seeded with Pakistani career options + `required_concepts` array. Phase 2 may expand with global careers.
- Mini-simulation per concept is a structured prompt (e.g., "calculate force needed to lift this rope") rendered as an interactive widget. Save state per student stored in `student_simulation_progress`.
- Generation cost: ~$0.10 per concept; cache means amortized ~$0 per student.

### 3.11 Lecture rating lifecycle (per v2 doc Phase 2 row, included in this flow for completeness)

A 1-5 star rating after finishing a lecture. Feeds 5% into the teacher's lecture quality score (Flow 5 §3.6 #32 supplementary signal — not a primary scoring dimension, but contributes weighted aggregate).

```
   LECTURE_COMPLETED            (student reaches end of lecture text OR ≥80% scroll)
       ↓ rating prompt shown
   PROMPT_DISPLAYED
       ↓ student rates 1-5 stars OR dismisses
   RATED OR SKIPPED
```

**Locked rules:**
- Rating is OPTIONAL; student can dismiss prompt.
- Rating contributes 5% weight to the lecture's display quality score seen by teacher (alongside #32 AI scoring at 95%).
- Rating shown to teacher as a 1-5 average; individual student ratings anonymous.
- Locked rules per coaching-not-grading: never displayed to other students; never used in any "ranking" of students.

---

## 4. Permissions matrix

Per §6.19 inheritance: every action available to a role is available to roles above in scope. This flow is primarily student-facing; admin roles inherit READ access for monitoring.

| Action | Student (self) | Parent (linked) | Teacher (assigned) | Coordinator (scoped) | School Admin | (+District+Platform Admin per inheritance) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Open lecture in Lecture Mode | ✅ | ❌ | view-only | view-only | view-only | inherit view-only ✅ |
| Toggle text / voice mode (#54) | ✅ | n/a | n/a | n/a | n/a | n/a |
| Highlight + ask question (#55) | ✅ | view-only | view-only (if privacy #72 allows) | view-only (aggregate) | view-only (aggregate) | inherit ✅ |
| Use hybrid voice widget (#57) | ✅ | n/a | n/a | n/a | n/a | n/a |
| View own highlights / flashcards (#58) | ✅ | view-only | view-only (if #72 allows) | view-only (aggregate) | view-only (aggregate) | inherit ✅ |
| View live feedback panel (#59) | ✅ | n/a | n/a | n/a | n/a | n/a |
| Rate lecture | ✅ | view-only | view (aggregate) | view (aggregate) | view (aggregate) | inherit ✅ |
| Toggle self-study privacy (#72 — owned in Flow 8 but affects this flow's teacher visibility) | ✅ | view | n/a | n/a | n/a | inherit ✅ |
| View student questions for own lecture (Flow 7 consumes) | n/a | n/a | view (if #72 allows; aggregated for Flow 7) | view (aggregate, scope) | view (aggregate, scope) | inherit ✅ |
| Override student privacy setting | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Locked rule:** student's privacy setting (#72) is INVIOLATE — no role can override it. Setting #72 to "do not share with teacher" means the teacher loses visibility into that student's lecture-mode interactions (Flow 7 next-day review excludes them). Aggregate anonymous data still flows to system-level AI improvement regardless of #72.

---

## 5. Edge cases

### 5.1 Lecture viewer
- **Student opens a lecture with restricted access (per Flow 5 §3.14):** if not in assignee list, returns 404. If access changed mid-session (admin restricts), student sees "Access changed" banner; session ends; events flushed.
- **Student opens an unpublished/draft lecture:** returns 404 (only published lectures visible).
- **Lecture deleted by admin while student is reading:** session marked as orphaned; data flushed; banner "Lecture no longer available." Question history preserved (linked to lecture_id which is soft-deleted).
- **Voice mode requested for unsupported language:** falls back to text mode with toast "voice not yet available in [language]."
- **Audio generation fails (TTS service down):** student sees error in voice mode; can switch to text mode. NATS event for monitoring.
- **Audio cache expired or evicted:** lazy regenerates on next request.

### 5.2 Highlight + question
- **Student highlights inside an inline image / non-text element:** highlight ignored. Only text selection produces highlight.
- **Multiple overlapping highlights:** allowed; each is a separate row in highlights table.
- **Question submitted with no text selected (clicked "ask question" button instead):** opens question box without prefilled "Explain:" prefix. Behaves as plain free-form question.
- **Question contains language that isn't the student's preference (e.g., student in Urdu UI but types in English):** AI responds in the LANGUAGE OF THE QUESTION. Student's UI language only affects UI chrome; question/answer language follows the question.
- **Question is too long (> 2000 chars):** truncated with warning "your question is unusually long; consider asking in parts."

### 5.3 AI answer panel
- **AI answer generation fails:** retry 3x; final failure → "Couldn't generate an answer. Try rephrasing or check your connection." Question logged anyway for next-day review (Flow 7).
- **AI answer takes > 30 seconds:** loading indicator; student can cancel. Cancelled question still logged.
- **Source badge click on out-of-date source (lecture re-edited, paragraph removed):** badge shows "source updated" message; fallback to current paragraph that closest-matches.
- **Multi-turn conversation reaches 20+ turns:** earliest turns truncated from context window; warning "long conversation — older context may be lost."

### 5.4 Hybrid widget (#57)
- **Mic permission denied:** widget gracefully degrades to text-only mode; voice icon shows "permission needed."
- **STT transcription empty (silence or low confidence):** prompt "couldn't hear that — try again."
- **Live transcription latency > 1s:** acceptable but logged; sustained latency > 3s alerts Platform Admin.
- **Image exceeds 5 MB:** rejected at upload pipeline (`student_question_image` profile); toast "Image too large; max 5 MB."
- **Unsupported image format** (e.g., HEIC, BMP, TIFF): rejected with toast "Format not supported — use JPEG, PNG, or WEBP."
- **More than 3 images attached:** 4th attachment blocked at UI with toast "Max 3 images per question."
- **Image with sensitive content** (e.g., personal ID, exam paper photo): no detection at launch; student responsible. Phase 2 may add content-moderation pre-filter.
- **Vision LLM call fails / times out:** retry 3x with same payload; final failure → "Couldn't process image — try again or send text-only question." Images retained in MinIO for retry; question logged.
- **Image upload succeeds but vision LLM hallucinates content not in image:** treated as standard LLM error; student can rephrase. No corrective feedback loop at launch.
- **Drag-drop on mobile:** falls back to icon-click image picker (drag-drop unreliable on mobile browsers).
- **Pasted image is a screenshot of copyrighted content** (e.g., past paper): no detection at launch; same content moderation deferral as above.

### 5.5 Highlight persistence + flashcards
- **Highlight at offset that no longer exists** (lecture re-edited, content removed): yellow mark removed silently; flashcard remains in deck (front text + back AI answer preserved).
- **Duplicate flashcards** (student highlights same text twice): deduped by hash; second highlight reuses existing flashcard.
- **Flashcard back is an empty AI response (failure case):** flashcard created with placeholder back; student can edit or delete from "My Highlights" tab.
- **Student deletes a highlight:** flashcard from that highlight also removed from spaced rep deck (cascade delete; soft-delete in highlights table).

### 5.6 Live feedback panel
- **Live feedback updates fail (WebSocket disconnect):** panel shows "reconnecting"; reconnects automatically. On reconnect, full state refreshes from NATS replay.
- **Nudge fires but student then asks question within 30s:** nudge dismisses silently.
- **Student keeps tab open for hours with no activity (laptop closed):** session auto-times-out at 30 min; panel disappears; events flushed.
- **Daily goal not set:** goal field shows "set a goal" link (which deep-links to Flow 8 goal setting #69).

### 5.7 NATS event pipeline (#60)
- **Consumer lag > 30s:** Platform Admin alert (`system.event_pipeline_lag`); consumer auto-recovers from JetStream's durable subscription.
- **Event publish failure** (network blip): retry via NATS client's built-in retry; if all retries fail, event written to a local fallback queue, replayed on reconnect.
- **JetStream stream full** (high event volume): old events trimmed per retention policy; alert at 80% capacity.
- **Tenant_type mismatch** (event from school tenant accidentally tagged independent): drops at consumer; alert.
- **Schema evolution** of event envelope: backwards-compatible additions only; breaking changes require versioned subjects (e.g., `student.lecture.v2.question_asked`).

### 5.8 Per-session adaptation (#61)
- **Threshold 2 questions on same sub-topic — but sub-topic detection wrong:** AI may not switch angle when it should. Mitigation: sub-topic mapping uses Flow 3 #18 topic_tree which has been parsed; fallback to embedding similarity if structured map unavailable.
- **All angles exhausted in session** (cycle complete): AI falls back to "consider speaking to your teacher" or links to teacher's office hours (Phase 2).
- **Student switches lectures mid-session:** new session begins; difficulty log per session, not per lecture (different lecture = different topics).

### 5.9 Concept enrichment (#71)
- **Concept enrichment cache stale (90+ days):** Celery beat job refreshes; cache hit but with "updated" badge for users.
- **Mini-simulation widget fails to render** (LLM produced malformed structure): falls back to text-only "real-world use" description.
- **Save state corrupted** (student's progress on a simulation): reset to start with notification "your progress was reset due to a data issue."

### 5.10 Cross-tenant
- **Independent student tries to access Lecture Mode** (UI redirect or direct URL hack): 404; Mode Switcher UI never exposed per Flow 4 v3.
- **School student migrated to independent:** during 6-month read-only window, lecture viewer is READ-ONLY (per Flow 4 v3 §3.9). Question submission blocked; highlight creation blocked; only viewing past lectures + past highlights.

### 5.11 Privacy (#72)
- **Student toggles #72 OFF mid-session:** subsequent events tagged "private"; teacher's next-day review (Flow 7) excludes this student's questions from that point. Aggregate analytics still receive anonymized signals.
- **Student toggles #72 ON after a private period:** historical private events stay private; new events visible to teacher.

---

## 6. Limits

### Lecture viewer (#54)
- Audio cache TTL: indefinite (until lecture re-edit invalidates).
- Audio file max size: 100 MB per lecture (typical lecture ~30-60 min audio ≈ 30-50 MB).
- Karaoke sync granularity: sentence-level at launch; word-level Phase 2.
- TTS generation timeout: 60 seconds for full lecture; chunks generated incrementally if needed.

### Highlight + question (#55, #56)
- Max highlights per lecture per student: 200.
- Max question length: 2000 characters.
- AI answer streaming target: first token < 1 second; full answer < 15 seconds.
- Multi-turn conversation: 20 turns before context truncation warning.
- Side panel width: 40% of viewport on desktop; bottom sheet on mobile.

### Hybrid widget (#57)
- Recording max duration: 60 seconds per turn.
- STT transcription latency target: < 1 second after stop.
- Silence auto-stop: 30 seconds.
- Image attachments per question: max 3.
- Image size per attachment: max 5 MB.
- Image formats: JPEG, PNG, WEBP only.
- Image retention in MinIO: 1 year (per `student_question_image` profile, ARCHITECTURE §11.19).
- Vision LLM response target: first token < 2 seconds; full answer < 25 seconds (slower than text-only due to image processing).

### Highlight persistence (#58)
- Max highlights per student across all lectures: not capped at launch.
- Flashcard deck max size: per Flow 8 limits (TBD).

### Live feedback (#59)
- Update cadence: every 60 seconds.
- Nudge stuck threshold: 10 minutes.
- Nudge per session: max 1.
- Session timeout: 30 minutes inactive.

### Event pipeline (#60)
- NATS JetStream retention: 7 days live.
- Analytics persistence retention: 7 years (per audit log).
- Consumer lag alert: > 30 seconds.
- Stream capacity alert: > 80% full.

### Per-session adaptation (#61)
- Repeat-question threshold: 2 (env var `AI_ADAPT_QUESTION_THRESHOLD` default 2).
- Angles cycle: 5 (example, metaphor, analogy, visual, real-world).

### Concept enrichment (#71)
- Cache TTL: 90 days (configurable per concept).
- Career taxonomy: ~50 careers at launch.
- Mini-simulation generation cost: ~$0.10 per concept (amortized).

### Cross-flow signal pipeline
- NATS event envelope size: 64 KB max (per §9 spec).

---

## 7. Notifications

Per §9.21 namespace conventions.

### Namespace: `lectures`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| New lecture published in student's Grade-Subject | Student + linked parents | In-app + push | `lectures.new_available` (already in Flow 5 §7) |
| Lecture re-edited (version published) | Students who already viewed v1 | In-app | `lectures.version_published` (already in Flow 5 §7) |
| Lecture access changed for student | Affected student | In-app | `lectures.access_changed` (already in Flow 5 §7) |

### Namespace: `self_study` (Flow 8's namespace — referenced here)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Auto-flashcard added to deck (high volume; batch nightly) | Student | In-app | `self_study.flashcards_added_batch` |

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| NATS consumer lag > 30s | Platform Admin | In-app + email | `system.event_pipeline_lag` |
| TTS service failure rate > 5% in 1 hour | Platform Admin | In-app + email | `system.tts_failure_rate` |
| STT service failure rate > 5% in 1 hour | Platform Admin | In-app + email | `system.stt_failure_rate` |

**Flow 6 generates LOW direct user notifications.** Most signals are events flowing to NATS for consumption by Flow 7 (next-day review notifications) and Flow 9 (Cognitive DNA updates). This flow is interaction-heavy but notification-light.

**Notifications cannot be turned off** per Flow 1 Q13 lock.

---

## 8. Open questions

1. **Karaoke sync granularity at launch.** Sentence-level vs word-level. Recommendation: sentence-level at launch (cheaper, more reliable). Word-level Phase 2 if students request it strongly during pilot.

2. **TTS audio cache invalidation strategy.** Currently invalidated on lecture re-edit. **Sub-question:** what if only one paragraph changed? Recommendation: re-generate ONLY affected paragraphs; serve cached audio for unchanged paragraphs. Phase 2 optimization; launch does full regen.

3. **Question classification quality.** Misconception vs knowledge_gap. **Question:** what's acceptable accuracy? Recommendation: target 75%+; refine in Flow 9 Phase 5 with Cognitive DNA training data.

4. **Flashcard generation policy.** Every highlight + answer pair becomes a flashcard. **Question:** does this create flashcard spam (student highlights 50 things in one lecture)? Recommendation: dedupe by hash; teacher / Phase 2 can introduce "smart flashcard" filter (only highlights that the student asked follow-up questions on become flashcards).

5. **Live feedback panel content for stuck threshold.** **Question:** what counts as "stuck"? Currently: > 10 min same page + 0 questions. Should scroll activity count as "engaged" too? Recommendation: > 10 min same page + 0 questions + 0 scrolls = stuck. Active scrolling = engaged.

6. **NATS JetStream replay on consumer outage.** **Question:** if the analytics consumer is down for 24 hours, does it replay 24 hours of events on restart? Recommendation: yes — JetStream's durable subscription guarantees this. Stream retention = 7 days protects against extended outages.

7. **Adaptation threshold (#61).** Default 2 questions. **Question:** is 2 the right threshold for "struggling"? Some students ask many questions naturally (curious learners), not because they're stuck. Recommendation: configurable env var; tune based on pilot data.

8. **Custom Persona interaction with adaptation.** Custom Persona prepends to system prompt. Adaptation context also prepends. **Question:** which takes priority? Recommendation: Custom Persona sets STYLE (tone, structure); Adaptation sets STRATEGY (try different angle). Both compatible; persona shouldn't override adaptation's intent.

9. **Real-world simulation widget complexity.** **Question:** how interactive should mini-simulations be? Recommendation: lightweight at launch — text-based scenarios with input fields, simple state machines. Phase 2 may add canvas/SVG-based simulations.

10. **Concept enrichment refresh cadence.** 90 days. **Question:** does career taxonomy need its own refresh? Recommendation: career taxonomy is human-curated (small) — manual updates by Platform Admin as needed; concept-application content auto-refreshed quarterly.

11. **Lecture rating after completion.** **Question:** what counts as "completed"? 80% scroll? Reaching end? Recommendation: 80% scroll OR student manually marks "done." Either triggers rating prompt (skippable).

12. **Privacy setting #72 default.** Currently default = Yes (share with teacher) per Flow 8 spec. **Question:** does this default align with the coaching-not-grading principle? Recommendation: yes — sharing enables teacher's next-day review and adaptive teaching. Students can opt out anytime.

13. **Independent student events on the same NATS streams?** Recommendation: yes, same NATS infrastructure; events tagged `tenant_type=independent`; consumers filter by tenant_type to route to correct downstream tables. Single infrastructure, dual logical streams.

---

## 9. Out of scope (for now)

- **Real-time collaboration in lecture viewer** (multiple students reading together, shared cursor). Single-user view at launch. Group study is Flow 11 only. (TODO: `phase-3-collab-lecture-viewing`)
- **Lecture annotations / notes** (student-authored notes in margins). Highlights only at launch. (TODO: `phase-2-lecture-notes`)
- **Word-level karaoke sync** for #54. Sentence-level at launch. (TODO: `phase-2-word-level-tts-sync`)
- **Custom voice / voice cloning** for TTS. Standard voices at launch. (TODO: `phase-3-custom-voice`)
- **In-lecture quiz embeds** (mini-quizzes inline with content). Quizzes are separate via #23b. (TODO: `phase-3-inline-quizzes`)
- **Multi-modal questions with documents / multiple file types beyond images** (uploading PDFs, slides into question chat). Image-only at launch (per v2 feedback). (TODO: `phase-3-multimodal-document-attachments`)
- **Lecture bookmarking** (save my position). Implicit only at launch (last-viewed paragraph tracked). (TODO: `phase-2-explicit-bookmarks`)
- **Sharing highlights with peers**. Highlights are private at launch. (TODO: `phase-3-share-highlights`)
- **Career taxonomy expansion** beyond Pakistani career options. Limited set at launch. (TODO: `phase-2-global-career-taxonomy`)
- **Mini-simulation save state across devices** (student starts on phone, continues on laptop). Single-device save at launch. (TODO: `phase-2-cross-device-sim-state`)
- **AI-suggested questions** ("students who studied this also asked..."). Manual question entry only at launch. (TODO: `phase-3-ai-suggested-questions`)
- **Lecture comments / discussion thread.** Q&A is private to student. (Group study Flow 11.)
- **Smart-flashcard filtering** (only valuable highlights become flashcards). All highlights generate flashcards at launch. (TODO: `phase-2-smart-flashcard-filter`)
- **Subscription tier limits on questions per session.** Schema only. (TODO: per Flow 13.)
- **Office hours scheduling.** Phase 2 — when angles exhausted in #61, AI suggests teacher office hours. (TODO: `phase-2-office-hours-scheduling`)
- **Question rating by student** ("was this answer helpful?"). No feedback loop at launch. (TODO: `phase-2-answer-rating`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy
- **§3.16** — Independent users tenant model (event tagging)
- **§3.18** — Grade/Section/Subject model (lecture scoped to GradeSubjectOffering)
- **§3.19** — Exam Framework engine (may overlay context on AI answers, not lecture body)
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations
- **§5.1-5.7, §5.9** — API design + Idempotency
- **§5.10** — If-Match (concurrent question submissions on same lecture handled idempotently)
- **§6.7** — Dependency primitives
- **§6.13** — ParentChildLink (parent read-only access; subject to #72 privacy)
- **§6.19** — Permission inheritance
- **§7.3-7.10** — RAG pipeline (lecture Q&A uses Pattern S retrieval)
- **§7.12** — Pattern A (fallback to web search for out-of-curriculum questions per Flow 5 #27)
- **§8.6** — Typed prompts: `lecture_qa_v1.py`, `question_classifier_v1.py` (misconception/knowledge_gap), `concept_enrichment_v1.py`, `live_feedback_summary_v1.py`
- **§8.20** — Custom Persona (per-student per-session AI surfaces; prepended to system prompt)
- **§8.21** — Exam Framework agent (overlay context for AI answers when student has framework selected)
- **§9** — NATS JetStream event pipeline (THE foundational infrastructure of this flow's #60)
- **§9.21** — Notification namespaces (`lectures`, `self_study`, `system`)
- **§10.3-10.5** — Celery tasks: `concept.enrich_applications` (lazy concept enrichment), `flashcard.auto_create` (from highlights), `tts.generate_audio` (lecture audio cache build), `ai.adapt_session_context` (per-session difficulty log updates)
- **§10.6** — Beat schedule: `concept.refresh_quarterly` (cache TTL), `flashcards.batch_notification` (nightly digest)
- **§11.19** — Upload profiles: lecture audio not user-uploaded; lecture image inherited from Flow 5
- **§13** — i18n (UI in 4 languages; AI answers in question's language; TTS routes per language)
- **§14.10** — Audit log: privacy setting changes (#72), admin overrides

### Data model sketch

```
# In school schema:
lecture_sessions
  id (uuidv7), school_id, student_user_id (FK), lecture_id (FK),
  session_started_at, last_active_at, session_ended_at,
  mode (enum: text/voice), questions_count, highlights_count,
  time_on_lecture_ms

student_highlights
  id (uuidv7), student_user_id (FK), lecture_id (FK), version_id (FK),
  text_range_start, text_range_length, highlighted_text,
  paragraph_id (FK to lecture_paragraphs),
  created_at, deleted_at

student_questions
  id (uuidv7), student_user_id (FK), session_id (FK to lecture_sessions),
  lecture_id (FK), highlight_id (nullable FK), 
  question_text, question_language, 
  classification (enum: misconception/knowledge_gap/unclassified),
  content_element_paragraph_id (FK), content_element_source_chunk_id (nullable),
  sub_topic_id (nullable, mapped to curriculum topic_tree),
  asked_at, answered_at, answer_text, answer_source_tags_jsonb

student_question_conversations
  id (uuidv7), root_question_id (FK to student_questions), turn_index,
  role (enum: user/assistant), content, source_tags_jsonb, created_at

student_flashcards
  id (uuidv7), student_user_id (FK), source_type (enum: highlight/manual),
  source_highlight_id (nullable FK), front_text, back_text,
  lecture_id (nullable FK), concept_tag, status (enum: active/dismissed),
  created_at, last_reviewed_at
  -- spaced repetition state lives in Flow 8's table

session_difficulty_log
  id (uuidv7), session_id (FK), sub_topic_id (FK), question_count,
  tried_angles (text[]), updated_at

student_simulation_progress
  id (uuidv7), student_user_id (FK), concept_id (FK), state_jsonb,
  created_at, last_active_at

concept_applications  (cached, shared across students; school-tenant only — independents may use a separate copy)
  id (uuidv7), school_id, concept_id (FK to curriculum topic_tree node),
  real_world_uses_jsonb, career_links_jsonb, mini_simulation_prompt_jsonb,
  generated_at, expires_at, regen_cost_usd

careers  (controlled vocabulary, platform-level)
  id, name, required_concepts (text[]), career_category, created_at

lecture_ratings
  id (uuidv7), lecture_id (FK), student_user_id (FK), rating (1-5),
  created_at
  UNIQUE (lecture_id, student_user_id)

# Events table (analytics consumer destination — partitioned by date):
student_events
  id (uuidv7), tenant_type (enum: school/independent),
  tenant_id (school_id or null), user_id, session_id (nullable),
  event_type, event_payload_jsonb, occurred_at
  -- partitioned monthly; 7-year retention

# In independent schema (used by Flow 8):
# Similar tables (independent_lecture_sessions wouldn't exist; replaced by self_study_sessions in Flow 8)
# concept_applications mirrored for independent tenant
```

---

## 11. Acceptance criteria

### Lecture session (#3.1)
- ✅ Session begins on lecture open; NATS event `student.lecture.session_opened` published
- ✅ Session ends on close OR 30-min inactivity
- ✅ Concurrent sessions on same lecture (different devices) tracked separately
- ✅ Session events flow through NATS JetStream

### Voice mode (#54)
- ✅ TTS via Piper (en/ur fast path), Edge-TTS fallback, AI4Bharat (sd/ps) per STACK_LOCK §4
- ✅ Audio player controls: play/pause, ±10s, speed (0.5-2×), download
- ✅ Karaoke sync at sentence level (word-level Phase 2)
- ✅ Audio cached per lecture in MinIO; invalidated on lecture re-edit
- ✅ Voice questions in voice mode: faster-whisper STT
- ✅ Unsupported language: falls back to text mode with toast

### Highlight + auto-prompt (#55)
- ✅ Selection triggers question box with "Explain: [highlighted text]"
- ✅ 3-second auto-send countdown (cancelable)
- ✅ Each question auto-tagged with content element (lecture_id, paragraph_id, source_chunk_id)
- ✅ Each question classified misconception/knowledge_gap
- ✅ Mic icon opens hybrid voice widget (#57)

### AI answer panel (#56)
- ✅ Right slide-in panel (40% width desktop) OR bottom sheet (mobile)
- ✅ Header: quoted highlight + question
- ✅ Streamed AI answer with source badges
- ✅ Multi-turn conversation in same panel; preserved on scroll
- ✅ Source badge click highlights source passage in document sidebar

### Hybrid widget (#57) — reusable component
- ✅ Single shared React component used across lecture Q&A, creation chat, group study, study plan
- ✅ Live transcription via faster-whisper
- ✅ Visual: text input + mic icon + image-attach icon; red pulse during recording; image thumbnails as chips
- ✅ Stop conditions: tap-mic-again, ESC, 30-second silence
- ✅ Image attachment: drag-drop, paste (Ctrl/Cmd+V), or icon-click
- ✅ Max 3 images per question, 5 MB each, JPEG/PNG/WEBP only
- ✅ Image upload uses `student_question_image` upload profile (ARCHITECTURE §11.19); EXIF stripped; 1-year MinIO retention
- ✅ Question with `attached_images[]` routes to vision-capable LLM (Groq Llama-3.2-Vision); pure text routes to default text model
- ✅ Vision LLM failures retry 3x; on final failure, retryable from MinIO
- ✅ Frontend-master skill references this as canonical pattern (ledger entry)

### Highlight persistence + flashcards (#58)
- ✅ Highlights persist across sessions; yellow marks on return
- ✅ "My Highlights" tab in student dashboard
- ✅ Auto-flashcard generated from each highlight + AI answer pair (deduped)
- ✅ Flashcards published to spaced repetition deck (Flow 8)
- ✅ Delete highlight → cascade delete flashcard (soft-delete)

### Live feedback panel (#59)
- ✅ Bottom-right widget, auto-shows after 2 minutes of activity
- ✅ Updates every 60 seconds via WebSocket-pushed NATS events
- ✅ Metrics: time on topic, questions asked, mastery estimate, daily goal
- ✅ Nudge trigger: > 10 min + 0 questions → "Been here 10 min — need help?"
- ✅ Nudge per session: max 1
- ✅ Collapsible

### NATS event pipeline (#60)
- ✅ NATS JetStream replaces v2 doc's Kafka decision
- ✅ Subject pattern `student.lecture.*`
- ✅ Three parallel consumers: Live Feedback, AI Session Context, Analytics
- ✅ Event envelope per §9 (tenant_id, tenant_type, user_id, session_id, lecture_id, etc.)
- ✅ Stream retention: 7 days; persistence to `student_events` for long-term
- ✅ Consumer lag > 30s alerts Platform Admin
- ✅ Independent students share same infrastructure with `tenant_type=independent` tag

### Per-session adaptation (#61)
- ✅ Sub-topic auto-tagged via paragraph_id → source_chunk_id → curriculum topic_tree
- ✅ 2+ questions on same sub-topic → system prompt switch
- ✅ Angle cycle: example / metaphor / analogy / visual / real-world
- ✅ Custom Persona prepended alongside adaptation context
- ✅ Long-term difficulty signals exported to Flow 9 Cognitive DNA via analytics consumer

### Concept enrichment (#71)
- ✅ Concept_applications cached per concept (shared across students)
- ✅ Cache TTL 90 days; Celery beat refreshes
- ✅ Career links from controlled vocabulary
- ✅ Mini-simulation widget renders from LLM-generated prompt
- ✅ Save state per student stored

### Lecture rating
- ✅ Rating prompt on lecture completion (80% scroll or manual done)
- ✅ 1-5 stars; optional, skippable
- ✅ Contributes 5% weight to teacher's quality score (Flow 5 #32)

### Privacy (#72)
- ✅ Student can toggle "share self-study with teacher" — default Yes
- ✅ When Off: teacher (and Flow 7) loses visibility of THIS student's events
- ✅ Aggregate anonymous data still flows to system AI improvement
- ✅ NO role can override this setting

### Cross-tenant
- ✅ Independent students do not appear in this flow's surfaces (UI redirect)
- ✅ Migrated school students in 6-month read-only state: lecture viewer read-only, question/highlight blocked

### Notifications
- ✅ All template keys in correct namespaces (`lectures`, `self_study`, `system`)
- ✅ All 4 languages; no `__TODO__` in production

### i18n
- ✅ UI in en/ur/sd/ps; RTL handled
- ✅ AI answers in question's language (not necessarily student's UI language)
- ✅ TTS voices route per language (Piper/Edge-TTS/AI4Bharat)

### Audit
- ✅ Privacy setting changes audit-logged per §14.10
- ✅ Admin overrides (Flow 5 access restrictions affecting this flow's visibility) audit-logged

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1 → v2 (Awais feedback):**
- Hybrid widget (#57) extended to support image attachments alongside text + voice
- Max 3 images per question, 5 MB each, JPEG/PNG/WEBP
- New upload profile `student_question_image` (ARCHITECTURE §11.19); EXIF strip; 1-year MinIO retention
- Vision LLM routing: questions with `attached_images[]` → Groq Llama-3.2-Vision; pure text → default text model
- Multimodal questions REMOVED from out-of-scope; replaced with narrower "multimodal with non-image attachments" deferral
- Image edge cases added to §5.4; image limits added to §6; acceptance criteria added to §11

**Change log v1:** Initial draft. Covers 9 features (#54, #55, #56, #57, #58, #59, #60, #61, #71). Aligned with:
- Flow 5 (lectures published here are consumed in this flow; source attribution preserved; per-lecture access controls respected)
- Flow 4 v3 (Mode selection — Lecture Mode is one of two; independent students don't appear; graduated students in 6-month read-only state get reduced surface)
- Flow 3 v3 (curriculum topic_tree provides sub-topic mapping for #61 adaptation)
- Ledger §6.19 (permission inheritance), §9.21 (notification namespaces), §8.20 (Custom Persona), §8.21 (Exam Framework overlay), §3.16 (independent tenant in event pipeline)
- STACK_LOCK §4 (faster-whisper, Piper/Edge-TTS/AI4Bharat, NATS JetStream — replaces Kafka)
- §11.19 upload profiles (lecture audio, image inherited from Flow 5)

**Key stack translations from v2 doc:**
- v2 doc says ElevenLabs TTS → STACK_LOCK Piper/Edge-TTS/AI4Bharat
- v2 doc says Whisper STT → STACK_LOCK faster-whisper
- v2 doc says "Kafka vs Kinesis" (Day 1 decision) → STACK_LOCK NATS JetStream
- v2 doc says Google Vision API (for #62 OCR, Flow 8 scope) → STACK_LOCK PaddleOCR + Tesseract

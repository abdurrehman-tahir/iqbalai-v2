# Flow 5 — Teacher Creates a Lecture

**Status:** draft (v1)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy), §4 (DB patterns), §5 (API), §6 (auth + permission inheritance §6.19), §7 (RAG pipeline + Pattern A/S), §8 (LLM, esp. §8.6 typed prompts + §8.21 Custom Persona context), §9.21 (notification namespaces), §10 (Celery for scoring + originality + quiz gen), §11.19 (upload profiles), §13 (i18n), §14.10 (audit log)
**Related feature specs:** `flow-3-teacher-onboarding.md` (teacher capacity + Grade-Subject assignments + library), `flow-4-student-onboarding.md` (Grade enrollment provides student roster + Exam Framework overlay), `flow-6-student-studies-lecture.md` (future — lecture consumption), `flow-7-next-day-review.md` (future — mini-lecture pipeline), `flow-9-ai-intelligence.md` (future — Cognitive DNA feeds auto-quiz calibration)
**v2 doc features covered:** #21, #23, #23b, #24, #25, #26, #27, #28, #29, #30, #31, #32, #33, #34, #35, #36, #37, #38, #41

---

## 1. Purpose

A school teacher creates a lecture for a specific Grade-Subject offering. The process is a wizard-driven RAG pipeline that produces a structured lecture, an auto-generated per-student quiz, delivery tips, and innovation guidance — all version-controlled, quality-scored, and benchmarked.

This flow owns the entire arc from "teacher opens wizard" through "lecture published to students." Critical foundations:

- **Lecture creation wizard** (#23) — 5-step process: pick topic from curriculum tree → confirm curriculum → select reference books → choose teaching mode → generate
- **Dual-source RAG generation** (#24) — curriculum drives sequence/structure; reference books provide depth; AI knowledge fills gaps with explicit source attribution
- **Auto-quiz per student** (#23b) — calibrated to each student's Cognitive DNA (Flow 9) and topic mastery
- **Real-time voice conversation during creation** (#25) — sub-2s STS loop, lecture draft updates from voice
- **Edit lifecycle with 7-dimension scoring** (#29-#34) — every save versions, scores 7 quality dimensions (max 55 points), originality checks against global corpus, topic relevance percentage
- **Teaching Innovation Record** (#36) — AI learns each teacher's recurring weaknesses; adapts suggestions over time
- **Anonymized benchmarking** (#37) + **admin comparative metrics** (#38)
- **Cross-grade lecture linking** (#21) — same lecture usable across multiple Grade-Subject offerings (unidirectional per Flow 2 rule)

**For independent teachers** — a STRIPPED variant of this flow: lecture-plan generation only, no student distribution, no auto-quiz, no scoring/innovation/benchmarking. See §3.10.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Teacher** | Primary actor for school-tenant lectures. Opens wizard for their assigned Grade-Subject offering. Generates, edits, scores, publishes. |
| **Independent Teacher** | Uses a stripped variant — generates lecture plans for their own use; no distribution, no scoring/benchmarking. Lives in independent tenant. |
| **Coordinator (assigned scope)** | Read-only on lectures within own assigned Grade-Subjects. Can see quality trends, originality flags. |
| **School Admin** | Per §6.19: inherits all Coordinator + Teacher rights within own school. Can cross-link lectures across Grade-Subjects (#21). Sees comparative metrics across teachers (#38, scope-restricted). |
| **District Admin / Platform Admin** | Per §6.19: inherit all rights of lower roles in scope. Platform Admin can review system-wide originality flags. |
| **Student / Parent** | Receives published lectures via their Grade enrollment (school students) — consumption is Flow 6, not here. |

---

## 3. Lifecycle

### 3.1 Lecture creation wizard lifecycle (#23)

The wizard is 5 steps; draft auto-saves at every step.

```
   WIZARD_OPENED
       ↓ Step 1: Pick topic from curriculum tree
   STEP_1_DONE
       ↓ Step 2: Confirm curriculum (default = primary curriculum for the Grade-Subject)
   STEP_2_DONE
       ↓ Step 3: Select reference books (optional; filtered by Grade-Subject tags per Flow 3 §5.3)
   STEP_3_DONE
       ↓ Step 4: Choose teaching mode (auto / manual / voice-assisted)
   STEP_4_DONE
       ↓ Step 5: Confirm settings + estimated generation time → hit Generate
   GENERATING
       ↓ AI lecture generation begins (RAG pipeline, streaming)
   GENERATED_V1               (draft saved; auto-quiz generation kicks off in parallel)
       ↓ teacher reviews
   READY_FOR_EDIT             (teacher enters edit mode OR publishes as-is)
```

**Locked rules:**
- Draft auto-saved at every step (wizard state persisted in `lecture_drafts` table). Teacher can close wizard and resume.
- Step 1: topic source = curriculum's `topic_tree_jsonb` (from Flow 3 #18 structured parsing). If teacher's selected curriculum has degraded structured parsing, they pick freeform topic name.
- Step 3: reference books filtered to those tagged for `subject=THIS AND grade=THIS_OR_LOWER AND language=teacher_pref` per Flow 3 §5.3 rules. Cross-grade toggle (default off) reveals lower-grade items.
- Step 4: teaching mode options — `auto` (AI generates fully), `manual` (AI provides outline only), `voice_assisted` (teacher speaks instructions during generation per #25).
- Step 5: estimated generation time shown before commit. Teacher confirms or backs out.
- Independent teachers: same wizard structure but Step 3 only shows their own private uploaded references (no school library).

### 3.2 AI lecture generation lifecycle (#24)

```
   GENERATION_REQUESTED       (Step 5 Generate button)
       ↓ NATS event `lecture.generation_requested` published
   GENERATING                 (Pattern S RAG pipeline runs)
       ↓ chunks streamed word-by-word to frontend via WebSocket
       ↓ paragraphs auto-tagged with source: [Curriculum] | [Ref: Book Name] | [AI Knowledge]
   GENERATED_V1               (full draft persisted to `lectures` table; v1 row in `lecture_versions`)
       ↓ auto-quiz generation completes in parallel (see §3.3)
   READY_FOR_PUBLISH OR EDIT
```

**Locked rules:**
- **Dual-RAG retrieval:**
  - Curriculum chunks drive lecture SEQUENCE and STRUCTURE (chapter → section → sub-topic order)
  - Reference book chunks drive DEPTH and EXAMPLES (where the teacher selected references in Step 3)
  - Curriculum chunks weighted 1.5× over reference chunks in retrieval scoring (per Flow 3 v3 §3.3 lock)
- **Source tagging:** every paragraph carries provenance — either a curriculum chunk reference, a reference book chunk reference, or `ai_knowledge` (the LLM had to extrapolate). Per #26, source badges render in the lecture viewer.
- **Streaming:** generation streams to frontend via WebSocket (`lecture.gen` channel scoped to lecture_id). If connection drops mid-generation, generation continues server-side; teacher reconnects and resumes streaming from current position.
- **Out-of-curriculum content (#27):** if the AI determines a question/segment is not covered by curriculum, it falls back: (1) reference book search → (2) web search via SearXNG → (3) "I don't have information on this." Source badge always reflects the actual tier used.
- **Per-paragraph source attribution stored** in `lecture_paragraphs.source_metadata_jsonb` so source badges render correctly in any version of the lecture.
- **Generation timeout:** Celery `soft_time_limit` = 5 minutes per lecture. Exceeded → task halts with notification.
- **Exam framework overlay (per Flow 4 v3 §3.5.4):** if any students in the target Grade have selected an Exam Framework relevant to this Subject, the AI is given the framework's exam_strategy + priority_weights for that topic as ADDITIONAL CONTEXT (not replacement). Result: lectures naturally incorporate exam-readiness language without replacing teacher's curriculum focus.
- **Custom Persona awareness:** for students with custom persona active (per ARCHITECTURE §8.20), their persona description is NOT injected into lecture generation itself (lecture is class-wide); persona only affects per-student AI surfaces (Flow 6 questions, quiz delivery wording).

### 3.3 Auto-quiz generation per student lifecycle (#23b)

```
   QUIZ_GEN_REQUESTED         (triggered alongside lecture generation, after lecture is complete)
       ↓ for each enrolled student in the Grade (via Flow 4 enrollment)
   QUIZ_GENERATING_PER_STUDENT (parallel Celery tasks; each student gets calibrated questions)
       ↓ complete
   QUIZ_READY                 (quiz_assignments rows created; status=pending per student)
       ↓ teacher publishes lecture
   QUIZ_PUBLISHED             (students see quiz on their dashboard)
```

**Locked rules:**
- Per-student calibration uses Cognitive DNA from Flow 9 #83 (mastery map, topic difficulty) + diagnostic results (Flow 4 §3.6) seeded for that student.
- Stronger students get harder questions (deeper conceptual + applied); weaker students get more foundational questions covering same topics.
- Question pool: same lecture topic, varied difficulty per student. Typically 5-10 questions per quiz.
- Results visible to: student (immediate after attempt), teacher (per-student + aggregate), Coordinator (aggregate within scope), School Admin (aggregate within school), per §6.19 inheritance.
- Quiz generation is per-student-parallel; SLA = 2 minutes for full class quiz set (Grade with 30 students → 30 parallel Celery tasks, each ~30-60s LLM time).
- **For independent teachers:** auto-quiz is NOT generated. Independent teachers can manually request a quiz template via a separate feature (deferred to flow-8 self-study, generic quiz tooling).

### 3.4 Voice conversation during creation lifecycle (#25)

```
   VOICE_SESSION_OPENED       (teacher clicks "Talk to AI" during/after generation)
       ↓ WebSocket session established (audio bidirectional)
   ACTIVE_VOICE_SESSION
       Teacher speaks → faster-whisper STT → LLM → Piper/Edge-TTS → audio streamed back
       Each turn: full STS loop target < 2 seconds
       Lecture draft updates live from voice commands ("add an example about Newton's 3rd law")
       ↓ teacher closes session
   SESSION_ENDED              (transcript + audio archived to lecture_voice_sessions)
```

**Locked rules:**
- **STT:** faster-whisper (replaces v2 doc's Whisper mention — STACK_LOCK §4)
- **TTS:** Piper for English/Urdu fast path; Edge-TTS fallback; AI4Bharat for Sindhi/Pashto (STACK_LOCK §4)
- **Target STS loop latency:** < 2 seconds end-to-end. Open question §8 Q3 — feasibility on CPU-only deployment at launch.
- **Lecture draft update via voice:** the LLM is given the current draft + the teacher's transcribed instruction; produces a structured edit operation (insert/replace/append paragraph); applied to draft via OT (operational transform). New version row created on save trigger.
- **Audio retention:** raw audio retained 24 hours for QA; transcripts retained indefinitely with the lecture.
- **Independent teachers** also get voice mode for their lecture-plan generation. Same STS loop.

### 3.5 Edit lifecycle (#29, #30, #31)

```
   READY_FOR_EDIT             (teacher reviewing generated draft)
       ↓ teacher edits — text typing OR voice transcription OR drag-drop image
   EDIT_SESSION_ACTIVE        (lecture_edit_sessions tracks active_ms, edits_count, char_delta)
       ↓ teacher hits Save (manual) OR auto-save triggers
   SAVED_AS_NEW_VERSION       (new row in lecture_versions; score pipeline kicks off)
       ↓ score complete
   SCORED                     (scores written to lecture_versions.scores_json)
       ↓ teacher reviews score, may edit again OR publish
   PUBLISHED                  (lecture visible to enrolled students per Grade-Subject)
```

**Locked rules:**
- **Editor:** TipTap rich-text editor (replaces v2 doc's TipTap/Quill mention — TipTap locked per STACK_LOCK).
- **Voice edits:** faster-whisper STT transcribes; transcribed text inserted at cursor OR replaces selected text per teacher's choice.
- **Image upload (#30):** drag-drop to lecture editor → uploaded via `lecture_image` upload profile (per ARCHITECTURE §11.19) → stored in MinIO → image URL inserted in editor. AI proactively suggests diagrams from reference books: during generation, the AI flags pages with relevant diagrams; teacher sees "Diagram on page 34 of Ref Book X — add it?" prompt.
- **Effort tracking (#31):** frontend pauses timer on tab blur (visibility API). Heartbeat every 30s. DB stores `active_ms`, `edits_count`, `char_delta` per edit session. Effort score = `normalize(active_ms) × 0.4 + normalize(char_delta) × 0.6`.
- **Every save = new version row.** No overwrites. `lecture_versions` immutable except for scores_json populated by async scoring job.

### 3.6 7-Dimension quality scoring lifecycle (#32)

Triggered on every save (every new version). Runs asynchronously via Celery.

```
   SCORING_REQUESTED          (NATS event `lecture.version.created`)
       ↓ Celery task picks up
   SCORING_IN_PROGRESS        (LLM scoring + originality check + topic relevance running)
       ↓ complete (~30s typical)
   SCORED                     (scores_json populated)
```

**Scoring inputs:** original (v1 AI-generated) + edited version + diff + edit_session_data + teacher_region + teacher's Innovation Record context.

**Score dimensions (max 55 total):**

| Dimension | Max | Description |
|---|---:|---|
| Originality | 10 | How distinctively the teacher reshaped the content (deeper analysis if low — see #33 system-wide originality) |
| Depth | 10 | Conceptual depth beyond surface explanation |
| Cultural relevance | 5 | Locally relevant examples (region-aware; uses teacher_region from Flow 3 profile) |
| Engagement | 5 | Likely to capture student attention |
| Alignment | 10 | Aligned with curriculum learning objectives |
| Voice quality | 5 | Voice delivery quality (NULL if text-only edit) |
| AI Learning | 10 | Improvement from previous AI feedback (per Innovation Record #36) |

**Locked rules:**
- Voice quality dimension = NULL if edit was text-only.
- AI Learning dimension references teacher's Innovation Record (per #36); first version has AI Learning baseline = 0.
- Scores stored in `lecture_versions.scores_json` keyed by dimension.
- Teacher sees their scores within seconds of save completing.
- Total score and per-dimension breakdown visible in Version Timeline (#35).

### 3.7 System-wide originality check lifecycle (#33)

```
   ORIGINALITY_CHECK_REQUESTED  (part of scoring pipeline)
       ↓ embed lecture content
   CHECKING                      (cosine similarity vs GLOBAL lecture embeddings index across all teachers)
       ↓ complete
   CHECKED                       (originality_score = 1 - max_similarity; stored)
```

**Locked rules:**
- **Global index:** all published lectures across all schools (school tenant) contribute to a global embedding index. Independent teacher lectures NOT included in this global index (separate tenant per §3.16).
- **Privacy rule:** the teacher whose lecture matched is NEVER revealed. Originality score is shown; matched-teacher identity hidden.
- **Plagiarism threshold:** if similarity > 0.85 (max_similarity), Platform Admin gets a flag in their dashboard (`system.plagiarism_flagged`). Teacher sees their low originality score but no admin escalation visible to them.
- Independent teachers: originality check runs within independent tenant only (their own previous versions). NOT cross-tenant. Lower utility but consistent isolation.
- **Cost:** embedding generation + cosine over ~10K-100K lecture embeddings (per scale) → ~$0.01 per check.

### 3.8 Topic relevance percentage lifecycle (#34)

```
   RELEVANCE_CHECK_REQUESTED    (part of scoring pipeline)
       ↓ embed lecture + embed curriculum topic definition
   CHECKING
       ↓ cosine similarity
   CHECKED                       (relevance_pct = cos_sim × 100; stored per version)
```

**Locked rules:**
- Shown as a separate gauge in lecture editor: "Topic Relevance: 87%".
- Warning displayed if drops below 70% (teacher may have drifted off-topic).
- Stored in `lecture_versions.topic_relevance_pct`.

### 3.9 Version-by-version score timeline lifecycle (#35)

```
   VERSION_CREATED              (every save creates row)
       ↓ scored asynchronously
   VERSION_SCORED               (timeline updates)
```

**Locked rules:**
- Timeline = line chart: x = version number, y = total_score.
- Hover any version reveals all 7 dimensions.
- Annotations: "Added worked example", "Applied voice edit", "Image inserted" — auto-extracted from edit session metadata.
- Default view = last 6 versions; older accessible via pagination.

### 3.10 Teaching Innovation Record lifecycle (#36)

```
   FIRST_LECTURE_EVER          (no record yet)
       ↓ scoring run identifies weakness
   WEAKNESS_DETECTED           (e.g., "consistently low originality", "abstract examples")
       ↓ AI generates suggestion
   SUGGESTION_PRESENTED        (teacher sees "tip: try grounding in local Punjab examples")
       ↓ teacher acts or ignores
   ACTED_ON / IGNORED          (tracked per suggestion)
       ↓ AI adapts next suggestions based on what teacher responds to
   ADAPTIVE_PROFILE_BUILT
```

**Locked rules:**
- Per-teacher memory stored in `teacher_ai_memory` (NOT to be confused with Flow 9 #83 student Cognitive DNA).
- Memory categories: weakness type, frequency, last suggestion, teacher's response (acted/ignored), updated each session.
- Memory loaded as LLM system prompt context every scoring + generation session.
- AI suggestions adapt: if teacher consistently ignores "use local examples" suggestion, AI tries different angle ("consider story-based opening") instead of repeating.
- This is per-school-tenant. Independent teachers get a simplified version (their own memory, no cross-tenant influence).

### 3.11 Anonymized teacher benchmarking lifecycle (#37)

```
   WEEKLY_BENCHMARK_UPDATE    (Celery beat `benchmark.update_weekly`)
       ↓ compute percentile per teacher within (subject, grade_range, region) cohort
   BENCHMARK_UPDATED          (teacher_benchmarks table updated)
```

**Locked rules:**
- Percentile rank within same (subject, grade_range, region) cohort.
- Weekly update.
- **Framing always positive:** "Top 23% of Physics teachers in Punjab." NEVER "you're in the bottom 30%."
- Teachers can opt out via profile setting; removes them from the pool (their lectures no longer contribute to the benchmark; they don't see their percentile).
- N/A for independent teachers (no peer cohort within their tenant).

### 3.12 Admin comparative teacher metrics lifecycle (#38)

```
   ADMIN_OPENS_METRICS_TABLE
       ↓ live query (cached 1hr)
   TABLE_RENDERED              (rows=teachers, cols=7 dims + avg + topic_relevance + lecture_count)
       ↓ admin sorts/filters/exports
   ACTION_TAKEN
```

**Locked rules:**
- Sortable by any column. Filterable by subject, grade, school. CSV export.
- **Scope-restricted per §6.19:** School Admin sees teachers in own school; District Admin sees own district; Platform Admin sees all.
- Coordinator does NOT see this table (read-only on individual lectures but no cross-teacher comparative view at launch).
- Independent teachers excluded from school admin views (different tenant).

### 3.13 Cross-grade / cross-subject lecture linking lifecycle (#21)

```
   LECTURE_PUBLISHED          (originally for Grade 10 Physics)
       ↓ teacher OR admin chooses to link
   LINK_REQUESTED             (target: Grade 9 Physics; unidirectional per Flow 2)
       ↓ admin approves (if teacher-initiated for cross-teacher target) OR auto-approve (own GSO)
   LINKED                     (lecture appears in target Grade-Subject too; same lecture_id, additional lecture_links row)
```

**Locked rules:**
- **Self-link** by teacher: a teacher can link any of their own lectures to other Grade-Subject offerings they are assigned to. Auto-approve.
- **Cross-link** by admin: School Admin (and above per §6.19) can link any teacher's lecture to any Grade-Subject within their hierarchy.
- **Unidirectional rule (per Flow 2 v3):** Grade 10 lecture CAN be linked DOWN to Grade 9. Reverse blocked at API: linking a Grade 9 lecture to Grade 10 returns `PRECONDITION_FAILED`.
- **Linked lectures share lecture_id**: not duplicated. Students in the linked Grade see the same lecture content; their per-student quizzes are recalibrated to their own Cognitive DNA.
- Audit log entry per link per §14.10.

### 3.14 Per-lecture access control lifecycle (#21)

```
   LECTURE_PUBLISHED          (default access: all enrolled students in target Grade)
       ↓ teacher restricts (optional)
   ACCESS_RESTRICTED          (specific students OR specific groups OR specific sections)
       ↓ teacher publishes restriction
   APPLIED                    (lecture_assignments rows created; only specified assignees see lecture)
```

**Locked rules:**
- Default: all students in Grade-Subject see the lecture.
- Teacher can restrict to specific student IDs, group IDs (Flow 11), or section names within the Grade.
- Restriction is applied via `lecture_assignments` table; fetch APIs check assignments AND links.
- School Admin can override restrictions (audit-logged).

### 3.15 Delivery tips + technique demo + real-world examples lifecycle (#28, #41)

```
   LECTURE_GENERATED          (V1 complete from §3.2)
       ↓ second LLM call fires automatically
   TIPS_GENERATING            (separate LLM call: "Generate delivery tips + technique demo + 2 real-world examples NOT from uploaded docs")
       ↓ complete
   TIPS_READY                 (visible in collapsible sidebar)
       ↓ teacher hits Print
   PRINTABLE_VIEW             (printer-friendly CSS layout)
       ↓ teacher hits Share
   SHARE_LINK_GENERATED       (short expiring URL — 30-day TTL)
```

**Locked rules:**
- Tips are GENERATED FRESH per lecture (not templated). Use general world knowledge, NOT the curriculum/ref book content.
- Mobile view: large-text swipeable cards.
- Print view: clean CSS, no platform chrome.
- Share link: expires 30 days; URL viewable without login (PII-stripped — only lecture title + tips).

### 3.16 Independent teacher stripped variant

Independent teachers use a SUBSET of this flow:

```
   WIZARD_OPENED              (steps 1-5 same UI but Step 3 only shows own private references)
       ↓ generate
   GENERATED_V1               (single-teacher; no quiz; no student distribution)
       ↓ edit + version
   EDIT + VERSION             (same TipTap editor, voice mode, image upload)
       ↓ scoring (limited)
   SCORED                     (5 dimensions only — Originality, Depth, Cultural, Engagement, Alignment;
                               Voice quality if applicable; NO AI_Learning — no Innovation Record yet for independents at launch)
       ↓ export
   EXPORTED                   (PDF / DOCX / shareable link — not "published to students" since none exist)
```

**What independents DON'T get:**
- Auto-quiz per student (no students)
- Cross-grade/subject linking (no Grade-Subject offerings)
- Per-lecture access control (no students to restrict)
- Innovation Record (deferred to Phase 2 for independent teachers)
- Anonymized benchmarking (no peer cohort within tenant)
- Admin comparative metrics
- Cross-tenant originality check (own tenant only, lower utility)

**What independents DO get:**
- Wizard (5 steps with their private library at Step 3)
- AI generation with source attribution
- Voice conversation during creation (#25)
- Text + voice editing (#29) with version history
- Image upload (#30)
- Effort tracking (#31)
- 5-dimension scoring (subset of #32; AI_Learning excluded)
- Topic relevance percentage (#34)
- Version-by-version score timeline (#35)
- Delivery tips + technique demo + real-world examples (#28)
- Printable + shareable (#41)

---

## 4. Permissions matrix

Per §6.19 inheritance: every action available to a role is available to all roles above in scope.

**For school-tenant lectures:**

| Action | Teacher (self) | Coordinator (assigned scope) | School Admin | (+District+Platform Admin per inheritance) |
|---|:---:|:---:|:---:|:---:|
| Open lecture wizard (own GSO) | ✅ | ❌ | ✅ | inherit ✅ |
| Generate lecture (RAG) | ✅ | ❌ | ✅ | inherit ✅ |
| Edit own lecture | ✅ | ❌ | override ✅ (audit) | inherit ✅ |
| Save / version lecture | ✅ | n/a | n/a | inherit ✅ |
| Publish own lecture | ✅ | ❌ | ✅ (override) | inherit ✅ |
| Self-link own lecture to own GSO | ✅ | ❌ | ✅ | inherit ✅ |
| Cross-link any teacher's lecture in scope | ❌ | ❌ | ✅ | inherit ✅ |
| Per-lecture access restrictions | ✅ (own) | ❌ | ✅ (override) | inherit ✅ |
| View own quality scores + Innovation Record | ✅ | ❌ | view-only | inherit view-only ✅ |
| View anonymized benchmark (own percentile) | ✅ (own) | n/a | aggregate ✅ | inherit ✅ |
| Opt out of benchmarking | ✅ (own) | ❌ | ❌ | ❌ |
| View Admin Comparative Metrics table (#38) | ❌ | ❌ | ✅ (own school) | inherit ✅ |
| View originality plagiarism flags | ❌ | flag visible (in scope) | ✅ (own school) | inherit ✅ |
| Re-trigger scoring on a version | ✅ (own) | ❌ | ✅ (audit) | inherit ✅ |

**For independent-tenant lectures:**

| Action | Independent Teacher (self) | Platform Admin |
|---|:---:|:---:|
| Open wizard | ✅ | ✅ (support) |
| Generate / edit / version | ✅ | ✅ |
| Export PDF/DOCX | ✅ | ✅ |
| Share link | ✅ | ✅ |
| View 5-dimension scores | ✅ | ✅ |

**Locked rule:** every endpoint enforces `require_role(MIN_ROLE)` per §6.7 with §6.19 inheritance. Cross-tenant operations (linking a school lecture to independent or vice versa) blocked at API level — different schemas, different routes. Lecture visibility to students gated by Grade enrollment (Flow 4) + lecture_assignments + lecture_links per §3.13/§3.14.

---

## 5. Edge cases

### 5.1 Wizard
- **Teacher closes wizard mid-flow:** draft auto-saved; resumable from same step.
- **Teacher's selected curriculum gets soft-deleted by admin between wizard steps:** Step 5 detects deletion; banner "your selected curriculum is no longer available — please pick a replacement." Teacher steps back to Step 2.
- **Step 1 topic tree empty (curriculum has no parsed structure / degraded):** teacher gets a freeform topic name field with warning "AI generation may be less structured for non-parsed curricula."
- **Step 3 zero reference books available:** allowed; AI generates from curriculum alone. Source badges will show [Curriculum] | [AI Knowledge] only.
- **Cross-grade toggle reveals only items where max(grade_range) ≤ teacher's target grade** (unidirectional rule).
- **Teacher's Grade-Subject assignment removed mid-wizard (e.g., Coordinator unassigns):** wizard becomes read-only with "you are no longer assigned to this Grade-Subject" banner; existing draft saved.
- **Independent teacher tries to access school curriculum picker:** API returns 404 — endpoint only serves own private references.

### 5.2 Generation
- **Generation task fails (LLM provider down):** task retries with exponential backoff (3 attempts). On final failure, teacher sees "generation failed — retry" button. NATS event `lecture.generation_failed` logged.
- **Generation exceeds 5-minute soft_time_limit:** task halts; partial draft (whatever was streamed) saved as `INCOMPLETE_DRAFT`. Teacher can resume or discard.
- **Cost exceeds budget per generation:** soft cap $2 per lecture; if exceeded, alert Platform Admin (rare — typical generation is $0.20-0.50 with Groq).
- **WebSocket disconnect mid-streaming:** server-side generation continues; teacher reconnects and resumes streaming from current position. Idempotency via lecture_id + version + chunk_offset.
- **Web search fallback (tier 3 of #27) returns 0 results:** AI displays "I don't have information on this" with [No Source] badge. Teacher can manually add content or ignore.
- **Generation succeeds but contains low-confidence segments:** AI flags these with a yellow underline; teacher reviews before publishing.
- **Independent teacher generation:** same logic minus the auto-quiz step.

### 5.3 Auto-quiz per student
- **Grade has 0 enrolled students at generation time:** quiz generation skipped; lecture publishes without quiz. Banner to teacher: "no students enrolled yet — quiz will generate when first student enrolls" (deferred behavior; per-student quiz can be triggered on enrollment).
- **Student's Cognitive DNA not yet seeded (haven't taken diagnostic):** quiz calibrated to generic Grade-level difficulty. Banner to student: "take diagnostic for personalized quizzes."
- **Quiz generation fails for one student:** task retries; if persistent, that student gets a generic Grade-level quiz with warning. Other students unaffected.
- **Student enrolls AFTER lecture published:** quiz auto-generated for them on enrollment (Celery task `quiz.generate_for_late_enrollment`).
- **Lecture re-edited after quiz published:** existing quizzes for already-attempted students are NOT regenerated (their attempt history preserved). New quizzes for not-yet-attempted students MAY be regenerated (teacher's choice — UI toggle "regenerate quizzes for un-attempted students").

### 5.4 Voice conversation (#25)
- **STS loop exceeds 2 seconds:** acceptable but logged for monitoring; if 90th percentile drops below 2s SLA, alert to Platform Admin.
- **Whisper transcription quality poor (e.g., heavy accent, background noise):** AI confirms understanding via text echo before acting: "Did you mean: 'add an example about Newton's third law'?" Teacher confirms or restates.
- **Voice session active when teacher's account suspended:** session terminates; audio archived; lecture draft saved.
- **Multiple voice sessions on same lecture (different tabs):** only one active session per teacher per lecture. Second tab gets "voice session in progress in another tab" warning.
- **TTS voice not available for selected language:** fallback to text response with notification "voice not yet available in [language]; reading aloud disabled."

### 5.5 Editing & versioning
- **Teacher saves with no changes from previous version:** allowed but no new version row created (deduped on content hash).
- **Voice edit fails to apply (LLM produced malformed operation):** edit rejected; teacher sees "voice instruction unclear — try again or use text"; lecture unchanged.
- **Image upload fails:** clear error; teacher retries or skips. Lecture content unaffected.
- **Image > 5MB:** rejected at upload pipeline (lecture_image profile cap, ARCHITECTURE §11.19).
- **Concurrent edits from teacher's two tabs:** last-write-wins on version save; both tabs see latest version on reload.
- **Edit session crosses > 4 hours (long writing session):** session timer caps at 4 hours; further activity creates new session. Avoids inflated effort scores.

### 5.6 Scoring (#32, #33, #34)
- **Scoring task fails:** retry 3x. Final failure → score = NULL; teacher sees "scoring unavailable for this version, try saving again."
- **LLM produces invalid score JSON:** retry; final failure → null score with operational alert.
- **Originality check finds match > 0.95 (near-identical):** plagiarism flag escalated to Platform Admin. Teacher sees low originality score but NO admin escalation visible to them (per #33 privacy rule).
- **Teacher consistently scores < 30/55:** AI Learning dimension is the diagnostic; Innovation Record (#36) generates targeted improvement suggestions next time.
- **Topic relevance < 70%:** warning banner "your lecture may have drifted from the topic. Review topic alignment." Doesn't block publish.
- **Independent teacher gets the 5-dimension subset:** AI_Learning never scored; total possible = 45 instead of 55.

### 5.7 Innovation Record (#36)
- **First lecture ever:** no Innovation Record yet; AI starts collecting patterns from session 1.
- **Teacher dismisses suggestions repeatedly (3+):** AI category switch — tries different weakness angle to avoid annoying loop.
- **Teacher's region changes (e.g., moves schools, Q in Flow 3 §5.1):** Innovation Record region context updates; suggestions adapt to new region.

### 5.8 Benchmarking (#37)
- **Teacher in tiny cohort (e.g., only Physics teacher in their region):** percentile not shown if cohort < 5 teachers; banner "more peers needed for comparison."
- **Teacher opts out:** removed from pool; no longer sees their percentile; their lectures don't contribute to others' benchmarks.
- **Opt-out reversal:** allowed anytime; benchmark recomputes on next weekly run.

### 5.9 Cross-grade linking (#21)
- **Teacher tries to link own Grade 9 lecture to Grade 10 (reverse direction):** blocked at API with `PRECONDITION_FAILED` and message "Cross-grade linking is unidirectional — lectures can only be linked to lower grades."
- **Teacher tries to link to another teacher's GSO:** blocked at API (only School Admin and above can cross-link across teachers).
- **Linked lecture has restricted access (specific students/groups):** when linked to another Grade, the restrictions DO NOT propagate (different student pool). The link creates a copy of access defaults (all enrolled) in the new GSO. Teacher can re-restrict per-link.
- **Admin links a teacher's lecture to a grade where the teacher is not assigned:** allowed (admin override); audit-logged. Teacher gets notification.
- **Teacher unassigned from a GSO; their linked lectures remain visible to students:** lectures stay (historical content); the teacher attribution remains; teacher cannot edit anymore.

### 5.10 Per-lecture access control (#21)
- **Teacher restricts to 0 students:** treated as "unpublished to all students" — useful for drafts.
- **Restricted-to student is unenrolled:** access for that student removed silently; their access history preserved.
- **Admin override restriction:** audit log entry; teacher notified.

### 5.11 Cross-tenant (school vs independent)
- **School teacher tries to view independent teacher lectures:** 404.
- **Independent teacher tries to publish to students:** API endpoint doesn't exist; UI never offers the option.
- **Originality check across tenants:** disabled — each tenant's index is isolated.
- **Sharing an independent teacher's lecture via short link:** allowed; viewable without login (PII-stripped); doesn't trigger cross-tenant access.

---

## 6. Limits

### Lecture wizard (#23)
- Max draft auto-saves per session: not capped.
- Wizard step state TTL (abandoned drafts): 30 days, then auto-archived.
- Max reference books selectable in Step 3: 10.

### AI generation (#24)
- Generation `soft_time_limit`: 5 minutes.
- Generation cost soft cap: $2 per lecture (typical actual: $0.20-0.50 with Groq).
- Streaming chunk size: ~100 tokens/chunk (frontend renders incremental).
- Source-tag granularity: per paragraph.

### Auto-quiz (#23b)
- Questions per student quiz: 5-10 (calibrated).
- Per-class quiz generation SLA: 2 minutes for 30 students.
- Quiz regeneration on lecture edit: only for un-attempted students; opt-in by teacher.

### Voice conversation (#25)
- STS loop target latency: < 2 seconds (90th percentile).
- Audio retention raw: 24 hours.
- Voice session max duration: 60 minutes per session.

### Editing (#29-31)
- Max lecture content size: 100 KB raw text (TipTap document JSON).
- Max images per lecture: 30.
- Per-image size: 5 MB (lecture_image upload profile).
- Edit session effective duration cap: 4 hours.
- Heartbeat frequency: 30 seconds.

### Scoring (#32-35)
- Score dimensions: 7 (5 for independent teachers).
- Max total score: 55 (45 for independents).
- Scoring `soft_time_limit`: 60 seconds.
- Originality check threshold: > 0.85 similarity flags admin.
- Topic relevance warning threshold: < 70%.

### Innovation Record (#36)
- Memory categories tracked: typically 5-10 per teacher.
- Suggestion presented frequency: max 1 per session.

### Benchmarking (#37)
- Update cadence: weekly (Celery beat `benchmark.update_weekly`).
- Min cohort size for percentile display: 5 teachers.

### Cross-grade linking (#21)
- Max links per lecture: 5 Grade-Subjects.

### Per-lecture access control (#21)
- Max specific student assignments per lecture: 100 (operational; typical Grade has 30-60).
- Max group assignments per lecture: 10 (groups from Flow 11).

---

## 7. Notifications

All notification template keys use namespace prefixes per ARCHITECTURE §9.21. Every notification routes to the relevant feature's notification board; global panel shows aggregate counts only.

### Namespace: `lectures` (primary namespace for this flow)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Lecture generation requested (acknowledgment) | Generating teacher | In-app | `lectures.generation_started` |
| Lecture generation complete | Generating teacher | In-app + push | `lectures.generation_complete` |
| Lecture generation failed | Generating teacher | In-app + email | `lectures.generation_failed` |
| Auto-quiz generation complete (all students) | Teacher | In-app | `lectures.quiz_generated` |
| Lecture published | Enrolled students + linked parents | In-app + push | `lectures.published` |
| Lecture re-edited (new version published) | Enrolled students (if substantive change) | In-app | `lectures.version_published` |
| Lecture cross-linked to another Grade-Subject | Affected teacher (if not the linker) + admin | In-app | `lectures.linked` |
| Lecture access restricted by teacher | Affected students (if removed) | In-app | `lectures.access_changed` |
| Admin overrode access restriction | Teacher whose lecture was overridden | In-app + push | `lectures.access_override` |
| Score complete on a new version | Teacher | In-app | `lectures.scored` |
| Originality below threshold (warning only) | Teacher | In-app | `lectures.originality_warning` |
| Topic relevance below 70% | Teacher | In-app | `lectures.topic_relevance_warning` |
| Innovation Record new suggestion | Teacher | In-app | `lectures.innovation_suggestion` |
| Anonymized benchmark updated weekly | Teacher | In-app | `lectures.benchmark_updated` |

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Plagiarism flag (originality similarity > 0.85) | Platform Admin | In-app + email | `system.plagiarism_flagged` |
| Generation cost ceiling exceeded ($2 cap) | Platform Admin | In-app + email | `system.generation_cost_exceeded` |
| STS loop latency degraded (90th >2s for 1 hour) | Platform Admin | In-app | `system.voice_latency_alert` |
| Scoring task failures > 5% in 1 hour | Platform Admin | In-app + email | `system.scoring_failure_rate_alert` |

### Namespace: `content_library` (overlaps with Flow 3)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Curriculum re-indexed (Flow 1 admin action) — relevant to this teacher's selections | Teacher | In-app | `content_library.curriculum_reindexed` |

**Notifications cannot be turned off** per Flow 1 Q13 lock.

---

## 8. Open questions

1. **STS loop sub-2s feasibility on CPU.** STACK_LOCK is faster-whisper + Piper, no GPU at launch. Realistic latency on a 16-vCPU VM: 1.5-3s typical, depending on prompt length and load. **Question:** acceptable to launch at 2-3s with note "voice mode beta" and target sub-2s by Phase 2 with possible GPU? Recommendation: yes — soft launch with disclaimer; SLA tracked from day 1.

2. **Quiz regeneration on lecture re-edit.** Recommendation locked: only for un-attempted students; opt-in by teacher per save. **Sub-question:** should teacher be NOTIFIED to confirm regen, or just see toggle? Recommendation: toggle in editor + persistent reminder if substantive content change detected (> 30% diff).

3. **Generation cost cap $2 / lecture.** **Question:** is $2 realistic given Groq pricing? Math: 5-7K tokens input (curriculum + ref book context) + 3-5K tokens output (lecture) ≈ $0.05-0.15 with Groq Llama 3.3 70B. Recommendation: $2 cap is generous; alert threshold could be $1 or even $0.50.

4. **Innovation Record retention.** **Question:** does the teacher's memory grow unbounded? Recommendation: cap at 50 active weakness categories per teacher; auto-archive least-frequent on overflow.

5. **Cross-grade self-link auto-approve vs admin approval.** **Question:** if a teacher self-links their own Grade 10 lecture down to their own Grade 9 GSO, should that need admin approval? Recommendation: NO admin approval — own GSO + unidirectional rule already constrains misuse. Direct teacher action.

6. **Voice transcription accuracy concerns.** Pakistani teachers may speak Urdu/Punjabi-accented English. **Question:** what's the acceptable WER (word error rate)? Recommendation: monitor and report; provide manual edit affordance on every transcribed segment. faster-whisper with multilingual + accent fine-tuning is on the deferred TODO.

7. **Plagiarism threshold of 0.85.** **Question:** is 0.85 cosine similarity the right line? Recommendation: tune in pilot; start at 0.85; adjust based on false-positive rate. Platform Admin sees raw similarity in their flag view.

8. **Benchmarking opt-out long-term impact.** **Question:** if 50% of Physics teachers opt out, benchmarking becomes unreliable. Recommendation: not a problem at launch (small teacher pool means high benchmark fidelity required); if opt-out rate > 30% in pilot, revisit framing.

9. **Independent teacher cross-tenant originality check Phase 2?** **Question:** should we run independent teacher lectures through the school-tenant originality index for "is this material copied from school teachers"? Recommendation: NO at launch (privacy/legal complexity). Phase 2 considers a "shared anonymized index" with explicit consent.

10. **AI proactive diagram suggestion (#30).** During generation, AI flags pages with relevant diagrams from reference books. **Question:** how accurate is this? Recommendation: target 70%+ relevance, teacher reviews each suggestion before adding. False positives are cheap (teacher ignores).

11. **Lecture content size cap 100 KB.** **Question:** is this enough? Recommendation: 100 KB raw text ≈ 25 pages typical lecture. Adequate for school content. Reference books are separate (not in lecture body).

12. **Lecture publishing notification fan-out.** A lecture published to a Grade with 200 students + linked parents: 250+ notifications fire. **Question:** any rate limiting concern? Recommendation: batch notifications via Celery, send in 60-second windows; FCM handles 250 push easily.

13. **Admin Comparative Metrics caching.** **Question:** is 1-hour cache acceptable? Recommendation: yes for normal use; force refresh button available if needed.

14. **Tips/demos generation as a SEPARATE LLM call (#28).** Recommendation locked. **Sub-question:** can teacher trigger regeneration manually? Recommendation: yes — "regenerate tips" button. Cost negligible.

15. **Shareable lecture link (#41).** **Question:** is the 30-day TTL appropriate? Recommendation: yes — long enough for classroom use; protects against indefinite sharing.

---

## 9. Out of scope (for now)

- **Co-authored lectures** (multiple teachers editing one lecture). Single-author at launch. (TODO: `phase-2-co-authored-lectures`)
- **Lecture templates** (teacher saves a lecture as template for reuse). Each lecture starts fresh. (TODO: `phase-2-lecture-templates`)
- **AI auto-generation triggered by student questions** (a la "generate a lecture about Newton's 3rd law because 5 students asked about it"). Manual creation only. (Phase 5 territory.)
- **Lecture analytics deep-dive** (engagement heatmaps, drop-off points). Surface-level metrics only at launch. (TODO: `phase-2-lecture-analytics-deep`)
- **Multilingual lecture mixing** (sentences in Urdu + English in same lecture). Single language per lecture at launch. (TODO: `phase-2-mixed-language-lectures`)
- **Lecture-to-podcast export** (audio version with TTS). Print + share at launch. (TODO: `phase-3-lecture-podcast-export`)
- **Innovation Record for independent teachers.** Deferred. (TODO: `phase-2-independent-innovation-record`)
- **Cross-tenant originality check.** (TODO: `phase-2-cross-tenant-originality-shared-index`)
- **GPU-accelerated voice path** for sub-1s STS. (TODO: `phase-2-gpu-voice-acceleration`)
- **AI diagram generation** (creating new diagrams vs. flagging existing ones). Only reuse existing reference book diagrams at launch. (TODO: `phase-3-ai-diagram-generation`)
- **Lecture peer-review by other teachers.** (TODO: `phase-3-teacher-peer-review`)
- **Subscription-tier-driven generation caps** (e.g., free tier = 10 lectures/month). Schema only. (TODO: per Flow 13.)
- **Faster-whisper accent / multilingual fine-tuning.** Use base models at launch. (TODO: `phase-2-whisper-fine-tuning`)
- **Lecture export to LMS** (SCORM, Common Cartridge). (TODO: `phase-3-lms-export`)
- **Real-time collaborative editing** (multiple admins editing simultaneously). Single-editor at launch. (TODO: `phase-3-realtime-collab-editing`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy
- **§3.16** — Independent users tenant model (for independent teacher variant)
- **§3.17** — Subscription cross-cutting (caps deferred per Flow 13)
- **§3.18** — Grade/Section/Subject model (lecture scoped to GradeSubjectOffering)
- **§3.19** — Exam Framework engine (overlay influence on generation)
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations
- **§4.21** — Dual Alembic heads
- **§5.1-5.7, §5.9, §5.10** — API design + Idempotency + If-Match
- **§5.11** — Bulk operations (quiz generation per student is bulk-like)
- **§6.7** — Dependency primitives
- **§6.19** — Permission inheritance
- **§7.3-7.10** — Pattern S RAG (lecture generation)
- **§7.12** — Pattern A agentic RAG (out-of-curriculum web search fallback)
- **§7.21** — Cross-grade unidirectional retrieval weighting
- **§8.6** — Typed prompts: `lecture_generate_v1.py`, `lecture_score_v1.py`, `quiz_generate_v1.py`, `tips_generate_v1.py`, `voice_edit_intent_v1.py`
- **§8.20** — Custom Persona (NOT injected into lecture body; affects per-student surfaces)
- **§8.21** — Exam Framework agent (provides exam_strategy + priority weights as generation context)
- **§9** — NATS events: `lecture.generation_requested`, `lecture.generation_complete`, `lecture.generation_failed`, `lecture.version.created`, `lecture.scored`, `lecture.published`, `lecture.linked`, `lecture.access_changed`, `quiz.generated`, `quiz.regen_for_student`, `originality.flagged`, `benchmark.updated`
- **§9.21** — Notification namespaces (`lectures`, `system`, `content_library`)
- **§10.3-10.5** — Celery `@tenant_task` for: generation, quiz_per_student, scoring, originality_check, topic_relevance, tips_generation, benchmark_update, plagiarism_flag
- **§10.6** — Beat schedule: `benchmark.update_weekly`, `quiz.generate_for_late_enrollment`
- **§11.19** — Upload profiles: `lecture_image` (5 MB, JPEG/PNG/GIF), `school_library_content` (for cross-references)
- **§13** — i18n (lecture content language matches teacher's selected language)
- **§14.10** — Audit log: cross-grade linking, admin override of access restrictions, admin override of editing, plagiarism flag review

### Data model sketch

```
# In school schema:
lectures
  id (uuidv7), school_id, grade_subject_offering_id (FK to Flow 2 entity),
  teacher_user_id (FK), title, status (enum: draft/generating/ready/published/archived),
  current_version_id (FK), curriculum_id (FK, the one selected at Step 2),
  reference_book_ids (uuid[]), teaching_mode (enum: auto/manual/voice_assisted),
  generation_started_at, generation_completed_at, published_at,
  created_at, updated_at, deleted_at

lecture_drafts
  id (uuidv7), teacher_user_id, grade_subject_offering_id, wizard_step (1-5),
  step_data_jsonb, created_at, last_active_at
  -- TTL: 30 days

lecture_versions
  id (uuidv7), lecture_id (FK), version_number, content_jsonb (TipTap document),
  edit_mode (enum: ai_generated/text/voice/mixed),
  scores_jsonb (per-dimension scores), originality_score, topic_relevance_pct,
  source_metadata_jsonb (per-paragraph source attribution),
  edited_by_user_id, edited_at,
  edit_session_id (FK to lecture_edit_sessions)

lecture_edit_sessions
  id (uuidv7), lecture_id (FK), teacher_user_id, version_id (FK),
  active_ms, edits_count, char_delta, image_uploads_count,
  started_at, ended_at

lecture_paragraphs
  id (uuidv7), lecture_id (FK), version_id (FK), paragraph_order,
  content_text, source_type (enum: curriculum/reference/ai_knowledge/web),
  source_chunk_id (nullable FK to curriculum_chunks or reference_chunks),
  source_url (nullable, for web fallback)

lecture_links
  id (uuidv7), lecture_id (FK), linked_to_grade_subject_offering_id (FK),
  linked_by_user_id (FK), linked_by_role (enum), linked_at, audit_metadata_jsonb

lecture_assignments
  id (uuidv7), lecture_id (FK), assignee_type (enum: all/group/student/section),
  assignee_id (nullable), assigned_at, audit_metadata_jsonb

lecture_voice_sessions
  id (uuidv7), lecture_id (FK), teacher_user_id, started_at, ended_at,
  transcript_text, audio_key (nullable MinIO, 24hr retention)

quiz_assignments
  id (uuidv7), lecture_id (FK), student_user_id (FK),
  questions_jsonb (calibrated questions), difficulty_level (calibrated 1-5),
  status (enum: pending/attempted/completed), assigned_at, attempted_at

teacher_ai_memory
  id (uuidv7), teacher_user_id (FK), weakness_category, frequency,
  last_suggestion, teacher_response (acted/ignored), acted_on (bool),
  region_context, updated_at

teacher_benchmarks
  teacher_user_id (PK, FK), subject_id (FK), grade_range (int[]), region,
  cohort_size, percentile_rank, last_updated, opted_out (bool, default false)

# In independent schema:
independent_lectures
  id (uuidv7), user_id (FK), title, status (enum: draft/generating/ready/exported),
  current_version_id (FK), reference_book_ids (uuid[]),
  teaching_mode (enum), generation_started_at, generation_completed_at,
  created_at, updated_at, deleted_at

independent_lecture_versions
  id (uuidv7), lecture_id (FK), version_number, content_jsonb,
  edit_mode (enum), scores_jsonb (5 dimensions), topic_relevance_pct,
  source_metadata_jsonb, edited_at
```

---

## 11. Acceptance criteria

### Wizard (#23)
- ✅ 5-step wizard with state persisted at every step (auto-save)
- ✅ Step 1: topic source = curriculum's topic_tree_jsonb from Flow 3 #18
- ✅ Step 3: reference books filtered by Grade-Subject + language + unidirectional cross-grade rule
- ✅ Step 4: teaching mode = auto / manual / voice_assisted
- ✅ Step 5: estimated generation time shown
- ✅ Resumable: teacher closes mid-wizard, returns to same step
- ✅ Independent teacher Step 3 shows own private references only

### AI generation (#24)
- ✅ Pattern S RAG with dual-source (curriculum + reference books)
- ✅ Per-paragraph source attribution stored in lecture_paragraphs
- ✅ Source badges: [Curriculum] | [Ref: Book Name] | [AI Knowledge] | [Web] | [No Source]
- ✅ Streaming via WebSocket; resumable on disconnect
- ✅ 3-tier fallback for #27: curriculum → reference → web → "no info"
- ✅ Exam Framework overlay: priority_weights + exam_strategy injected as additional context (not replacement)
- ✅ Generation soft_time_limit = 5 minutes; failures retry 3x then notify teacher
- ✅ NATS events `lecture.generation_requested` and `lecture.generation_complete` published

### Auto-quiz (#23b)
- ✅ Generated per enrolled student in Grade
- ✅ Calibrated to student's Cognitive DNA + diagnostic results
- ✅ 5-10 questions per student
- ✅ 2-minute SLA for 30-student class
- ✅ Late-enrollment quiz auto-generation
- ✅ Re-edit toggle: regen for un-attempted students only, opt-in
- ✅ Results visible to teacher + coordinator + admin per §6.19

### Voice conversation (#25)
- ✅ WebSocket session with bidirectional audio
- ✅ faster-whisper STT + Piper/Edge-TTS/AI4Bharat output (per STACK_LOCK §4)
- ✅ STS loop target < 2 seconds; logged for monitoring
- ✅ Transcription echo before action: "Did you mean: ..."
- ✅ Audio retained 24 hours; transcripts kept with lecture
- ✅ Single active session per teacher per lecture

### Chat sidebar + source badges (#26)
- ✅ Sidebar visible alongside lecture draft during generation + edit
- ✅ Source badges on every AI response
- ✅ Click badge → highlights source passage in document sidebar
- ✅ 3-tier fallback per #27

### 3-tier out-of-curriculum (#27)
- ✅ Curriculum search first; reference book second; web search via SearXNG third
- ✅ Source disclosed via badge
- ✅ "I don't have information on this" if all tiers fail

### Delivery tips + technique + examples (#28, #41)
- ✅ Second LLM call after lecture generation
- ✅ Tips use general world knowledge, NOT uploaded docs
- ✅ Collapsible sidebar in lecture editor
- ✅ Print button → printer-friendly CSS
- ✅ Share → short URL, 30-day TTL, viewable without login (PII-stripped)
- ✅ Mobile view: large-text swipeable cards
- ✅ Regenerate tips button available

### Edit + version (#29)
- ✅ TipTap rich-text editor
- ✅ Voice editing: faster-whisper STT → insert at cursor OR replace selection
- ✅ Every save creates new version row in lecture_versions
- ✅ No overwrites; edit history preserved

### Image upload (#30)
- ✅ Drag-drop → MinIO via lecture_image upload profile
- ✅ AI proactive suggestion of diagrams from reference books
- ✅ Image size ≤ 5 MB; JPEG/PNG/GIF

### Effort tracking (#31)
- ✅ Frontend pauses on tab blur (Visibility API)
- ✅ Heartbeat every 30 seconds
- ✅ Stores active_ms, edits_count, char_delta
- ✅ Effort = normalize(active_ms)×0.4 + normalize(char_delta)×0.6
- ✅ Session cap = 4 hours

### 7-dimension scoring (#32)
- ✅ LLM scores: Originality(10) + Depth(10) + Cultural(5) + Engagement(5) + Alignment(10) + Voice(5, NULL if text-only) + AI_Learning(10) = 55 max
- ✅ Scoring inputs: original + edited + diff + edit_session_data + teacher_region + Innovation Record context
- ✅ Stored in lecture_versions.scores_jsonb
- ✅ Async via Celery; ~30s typical
- ✅ Independent teacher: 5 dimensions only (no Voice if text-only, no AI_Learning); max 45

### System-wide originality (#33)
- ✅ Global lecture embeddings index (school tenant only)
- ✅ Cosine similarity vs global index
- ✅ originality_score = 1 - max_similarity
- ✅ NEVER reveal matched teacher
- ✅ Plagiarism flag (similarity > 0.85) → Platform Admin notification
- ✅ Independent teachers: own-tenant only, no cross-tenant index

### Topic relevance (#34)
- ✅ Embed lecture + embed curriculum topic definition → cosine similarity
- ✅ relevance_pct shown as separate gauge
- ✅ Warning if < 70%

### Version timeline (#35)
- ✅ Line chart x=version_number, y=total_score
- ✅ Hover reveals all 7 dimensions
- ✅ Annotations from edit session metadata
- ✅ Default view = last 6 versions

### Innovation Record (#36)
- ✅ teacher_ai_memory tracks weakness categories
- ✅ Loaded as system prompt context every generation + scoring session
- ✅ AI adapts suggestions based on teacher's response history
- ✅ Cap 50 active categories per teacher
- ✅ Independent teachers: deferred (no Innovation Record at launch)

### Anonymized benchmarking (#37)
- ✅ Percentile within (subject, grade_range, region) cohort
- ✅ Weekly update via `benchmark.update_weekly` Celery beat
- ✅ Framing always positive ("Top 23%")
- ✅ Never expose other teachers' names or scores
- ✅ Opt-out removes teacher from pool
- ✅ Min cohort size = 5 teachers
- ✅ N/A for independent teachers

### Admin comparative metrics (#38)
- ✅ Sortable table: rows=teachers, cols=7 dims + avg + topic_relevance + lecture_count
- ✅ Filterable by subject / grade / school
- ✅ CSV export
- ✅ Scope-restricted: School Admin sees own school; District+ inherit
- ✅ Coordinator does NOT see this table
- ✅ 1-hour cache with force-refresh option

### Cross-grade linking (#21)
- ✅ Teacher can self-link to own GSO (auto-approve)
- ✅ School Admin+ can cross-link any teacher's lecture (audit-logged)
- ✅ Reverse direction (Grade 9 → Grade 10) blocked at API
- ✅ Linked lecture shares lecture_id; access defaults reset per link

### Per-lecture access control (#21)
- ✅ Default: all enrolled students see lecture
- ✅ Teacher can restrict to specific students/groups/sections
- ✅ lecture_assignments table tracks
- ✅ Fetch APIs check both assignments AND links
- ✅ Admin override audit-logged
- ✅ Max 100 specific students per restriction

### Cross-tenant (school vs independent)
- ✅ Independent teacher cannot publish to students (endpoint doesn't exist)
- ✅ Independent teacher can export PDF / DOCX / share link
- ✅ School-tenant teachers cannot view independent lectures (404)
- ✅ Originality index isolated per tenant

### Notifications
- ✅ All templates in correct namespaces: `lectures` (primary), `system` (admin alerts), `content_library` (curriculum re-index)
- ✅ Notifications route to feature's local board per §9.21
- ✅ Global panel shows aggregates
- ✅ All 4 languages; no `__TODO__` in production

### i18n
- ✅ Lecture content language matches teacher's preference
- ✅ Source badges + UI in 4 languages
- ✅ RTL layout for ur/sd/ps

### Audit log
- ✅ Cross-grade linking events logged per §14.10
- ✅ Admin overrides (access restriction, capacity, edit) logged
- ✅ Plagiarism flag review logged

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1:** Initial draft. Covers 19 features (#21, #23, #23b, #24-28, #29-38, #41). Aligned with:
- Flow 3 v3 (teacher capacity, curriculum/reference content_type, library tag filtering, unidirectional cross-grade)
- Flow 4 v3 (Grade-Section enrollment provides student roster; Exam Framework overlay; Cognitive DNA seeding for quiz calibration)
- Flow 2 v3 (Grade-Subject offerings as lecture parent)
- Ledger §6.19 (permission inheritance), §9.21 (notification namespaces), §3.19 (Exam Framework overlay)
- STACK_LOCK §4 (faster-whisper, Piper/Edge-TTS/AI4Bharat, TipTap, SearXNG)
- §11.19 upload profiles

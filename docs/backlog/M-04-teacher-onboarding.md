# M-04 — Teacher Onboarding + Content Library (school tier)

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-053 through T-068
**Spec source:** `flow-3-teacher-onboarding.md` v3 (school-tier scope only — independent teacher onboarding is M-05)

## Goal

A School Teacher logs in for the first time, completes a forced profile screen, and becomes READY_TO_TEACH once a Coordinator (M-03) has assigned them ≥1 Grade-Subject offering. This milestone also builds the **school-tier Content Library**: curricula (with structured topic-tree parsing) and reference books (with a teacher privacy toggle), the **RAG ingestion pipeline** (parse → chunk → embed), and library browse/search/tag-filtering. Teachers can self-edit their capacity within bounds (building on M-03's assignment enforcement).

**Scope boundary:** school tier only. Independent teacher signup + Platform Library = M-05. No lecture creation yet (that's M-09+). The library content ingested here is what Flow 5 will later consume.

**Demo at milestone end:**
- A School Teacher (created in M-02, assigned in M-03) logs in → forced profile completion → READY_TO_TEACH derived
- Coordinator uploads a curriculum ("Punjab Physics Grade 9") to the school library → ingestion runs → status moves INGESTING → AVAILABLE → topic tree visible
- Teacher uploads a reference book → chooses "private" (default) → ingests → visible only to them
- Teacher publishes that reference book to the school → now visible to other teachers per tags
- Teacher browses the Content Library, filters by subject/grade/language, sees Grade ≤9 curricula (cross-grade rule), NOT Grade 10
- Teacher edits their own capacity from 5 → 8; School Admin overrides a teacher above cap (audit-logged)
- All actions audit-logged; ingestion-complete notifications delivered

---

## T-053 — School Teacher onboarding: forced profile + READY_TO_TEACH derivation

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done (`ead1820`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.1 (School Teacher onboarding lifecycle #16)

### ARCH source
- `ARCHITECTURE.md` §6 (auth — session + first-login gating), §6.19 (inheritance)
- `ARCHITECTURE.md` §3.18 (Grade-Subject assignment drives READY)

### Depends on
- T-035 (Teacher role invitation, M-02)
- T-046 (Teacher assigned to Grade-Subject offering, M-03)

### What this ticket builds

**Backend:** A forced profile-completion gate on first login (`profile_complete` flag). A derived `ready_to_teach` computation: `profile_complete AND assignment_count ≥ 1`. Endpoint exposes onboarding state.

**Frontend:** First-login forced profile screen (name, subjects taught, language, brief bio). After completion, teacher lands on a dashboard that shows "assigned" status; READY_TO_TEACH banner appears only once a Grade-Subject assignment exists.

### Acceptance (demo script)

1. [ ] New teacher's first login forces the profile screen (cannot bypass)
2. [ ] After profile complete but with 0 assignments → state = PROFILE_COMPLETE (not ready)
3. [ ] Once Coordinator assigns ≥1 Grade-Subject → `ready_to_teach` becomes true
4. [ ] Suspended teacher (M-02 lifecycle) blocked from new content; existing readable
5. [ ] READY derivation is server-side, not a stored boolean that can drift

### Out of scope
- Independent teacher onboarding (M-05)
- Lecture creation (M-09+)
- Content pre-selection as a gate (per §3.1 v3 change — content selection is per-lecture, not onboarding)

### Notes / known gotchas
- Per Flow 3 v3 §3.1: READY no longer requires content selection — being assigned is enough. Don't re-introduce a content gate.

---

## T-054 — Content Library data model (school tier)

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done (`9204e29`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.3 (curriculum), §3.4 (reference books, privacy model)
- `flow-1-platform-setup.md` §x (multi-tier content library — school tier)

### ARCH source
- `ARCHITECTURE.md` §4 (DB patterns), §4.21 (school schema)
- `ARCHITECTURE.md` §3.18 (subject/grade tagging)

### Depends on
- T-041 (Subjects), T-043 (Grades)

### What this ticket builds

**Backend:** Migrations for the school-tier library: `library_items {id, school_id, title, content_type ENUM[curriculum, reference], language, subject_id (nullable), grade_level_ordinal (nullable), storage_key, sha256, ingestion_status, topic_tree_jsonb (nullable), created_by, visibility ENUM[private, school_public], created_at, deleted_at}` and `library_item_selections {id, library_item_id, user_id, selected_at}` (who's "using" an item, esp. for private→public dedup semantics). Tag fields support filtering.

**Frontend:** No UI yet (model only); used by T-058/T-059/T-060.

### Acceptance (demo script)

1. [ ] `library_items` + `library_item_selections` tables exist with constraints
2. [ ] `content_type` enum = curriculum | reference; `visibility` = private | school_public
3. [ ] `grade_level_ordinal` present for cross-grade filtering (T-063)
4. [ ] RLS: items school-scoped; private items visible only to creator
5. [ ] Seed data: one sample curriculum + one sample reference inserted via migration

### Out of scope
- Upload mechanics (T-055), ingestion (T-056), UI (T-058+)
- Platform Library tier (M-05)

### Notes / known gotchas
- `grade_level_ordinal` mirrors the T-047 normalized ordinal so cross-grade filtering is reliable (don't tag by string grade name).

---

## T-055 — Library upload via `school_library_content` profile + school-scoped dedup

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done (`b4d9fbb`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.3, §3.4 (uploads), §5.4 (dedup nuances)

### ARCH source
- `ARCHITECTURE.md` §11 (file upload pipeline), §11.19 (`school_library_content` profile)
- `ARCHITECTURE.md` §11.x (SHA-256 dedup)

### Depends on
- T-054 (library data model)
- T-013/T-014 (file upload foundation, M-00)

### What this ticket builds

**Backend:** Wire the `school_library_content` upload profile (100 MB, PDF, per-school, per-school SHA-256 dedup, indefinite retention) to MinIO. On upload: compute SHA-256; if an identical file already exists in the school, reuse the storage entry and create a separate `library_item_selections` record (separate privacy state per uploader per §5.4). Returns the created `library_items` row in `ingestion_status=pending`.

**Frontend:** Minimal upload entry point (full UIs in T-058/T-059) — a file picker that accepts PDF and reports upload success.

### Acceptance (demo script)

1. [ ] Upload a PDF → stored in MinIO, `library_items` row created (status=pending)
2. [ ] Same PDF re-uploaded in same school → storage reused (dedup), new selection record
3. [ ] Same PDF in a different school → separate storage (per-school dedup)
4. [ ] Non-PDF or >100 MB → rejected per profile rules
5. [ ] Two teachers upload same file both private → shared storage, independent privacy state

### Out of scope
- Ingestion processing (T-056)
- Curriculum vs reference UI distinction (T-058/T-059)

### Notes / known gotchas
- Dedup is school-scoped, NOT global (global is the Platform tier in M-05). Two teachers, same file, both private → one storage object, two selections, two privacy flags.

---

## T-056 — RAG ingestion pipeline (Pattern S: parse → chunk → embed)

**Layer:** 3
**Milestone:** M-04
**Estimate:** 3 days
**Status:** done (`1601892`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.3, §3.4 (ingestion → AVAILABLE)

### ARCH source
- `ARCHITECTURE.md` §7.1 (two patterns), §7.2 (Pattern S pipeline), §7.3 (embedding — BGE-M3 via Infinity), §7.7 (chunking)
- `ARCHITECTURE.md` §10.3-§10.5 (Celery `@tenant_task`)

### Depends on
- T-055 (uploaded items to ingest)
- T-010/T-011 (RAG + LLM base, M-00), T-012 (Celery, M-00)

### What this ticket builds

**Backend:** The core async ingestion Celery task for reference books (curriculum structured-parse is T-057): parse PDF → chunk per §7.7 → embed via Infinity/BGE-M3 per §7.3 → write vectors to Qdrant (school-scoped collection) + chunk metadata to Postgres. Drives `ingestion_status`: pending → ingesting → available (or failed). Idempotent + retryable.

**Frontend:** None (status surfaced in T-061).

### Acceptance (demo script)

1. [ ] Uploading a reference book triggers the ingestion task
2. [ ] Status transitions pending → ingesting → available
3. [ ] Chunks embedded via Infinity (BGE-M3) and stored in Qdrant (school-scoped)
4. [ ] Chunk metadata persisted in Postgres, linked to `library_items.id`
5. [ ] Task is idempotent (re-running doesn't duplicate vectors) and retryable on transient failure

### Out of scope
- Structured topic-tree parsing for curricula (T-057)
- Retrieval / lecture generation (M-09+)
- Failure-UI + retry button (T-061)

### Notes / known gotchas
- This is Pattern S (standard). Pattern A (agentic/web) is not in this milestone.
- Qdrant collections are school-scoped per multi-tenancy; never cross-school vector leakage.

---

## T-057 — Curriculum structured parsing → topic_tree_jsonb

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done (`aabaa80`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.3 (structured parsing applies to curricula only #18)

### ARCH source
- `ARCHITECTURE.md` §7.2 (Pattern S), §8.6 (typed prompt for topic extraction)
- `ARCHITECTURE.md` §7.7 (chunking — curricula still chunked + embedded too)

### Depends on
- T-056 (base ingestion pipeline)

### What this ticket builds

**Backend:** For `content_type=curriculum` items, an extra structured-parse step produces `topic_tree_jsonb` (chapter → section → sub-topic) via a typed LLM prompt (`curriculum_topic_extract_v1.py`). Curricula are ALSO chunked + embedded (like references) — the topic tree is additive. Reference books skip this step.

**Frontend:** None (topic tree displayed in T-058).

### Acceptance (demo script)

1. [ ] Uploading a curriculum runs structured parse → `topic_tree_jsonb` populated
2. [ ] Topic tree has chapter → section → sub-topic hierarchy
3. [ ] Curriculum is also chunked + embedded (topic tree is additive, not a replacement)
4. [ ] Reference book upload does NOT run structured parse (`topic_tree_jsonb` stays null)
5. [ ] Parse failure → item still becomes available with empty topic tree + a flag

### Out of scope
- Using the topic tree in lecture generation (Flow 5, M-09+)
- Manual topic-tree editing (Phase 2)

### Notes / known gotchas
- Per §3.3: the curriculum/reference distinction drives RAG weighting later (curriculum chunks weighted higher). This ticket establishes the data; weighting is consumed in content milestones.

---

## T-058 — Curriculum upload UI + lifecycle (admin/coordinator + teacher-always-public)

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done (`81ce9c1`)

### Spec source
- `flow-3-teacher-onboarding.md` §3.3 (curriculum lifecycle; always public to tier)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`school_library_content`), §6.19 (who can upload)

### Depends on
- T-055 (upload), T-057 (structured parse)

### What this ticket builds

**Frontend + backend wiring:** Curriculum upload UI — pick subject + grade + language, upload PDF, see ingestion progress, then view the extracted topic tree. Curricula uploaded by Admin/Coordinator/Teacher are **always public to the school** (no privacy toggle for curricula per §3.3). Lifecycle: uploaded → ingesting → available → soft-deleted (T-064).

### Acceptance (demo script)

1. [ ] Coordinator uploads "Punjab Physics Grade 9" curriculum with tags
2. [ ] Progress shows INGESTING → AVAILABLE
3. [ ] Topic tree renders (chapter → section → sub-topic)
4. [ ] Curriculum is school-public (no private option offered for curricula)
5. [ ] A Teacher uploading a curriculum also results in school-public (not private)

### Out of scope
- Reference book privacy toggle (T-059)
- Cross-grade visibility filtering (T-063)

### Notes / known gotchas
- Curricula are NEVER private — the privacy toggle is reference-book-only.

---

## T-059 — Reference book upload UI + privacy toggle

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-3-teacher-onboarding.md` §3.4 (reference book lifecycle + privacy model)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`school_library_content`), §6.19

### Depends on
- T-055 (upload), T-056 (ingestion)

### What this ticket builds

**Frontend + backend:** Reference book upload UI with a privacy toggle "Make available to the school" — **default PRIVATE**. Teacher can later publish a private item to school (private → public, one-way). Public → private is BLOCKED. Removing a selection of a public item leaves the item public for others.

### Acceptance (demo script)

1. [ ] Teacher uploads a reference book → defaults to PRIVATE → visible only to them
2. [ ] Teacher toggles "Make available to school" at upload → becomes school_public
3. [ ] Teacher publishes a previously private item → now school_public (one-way)
4. [ ] Attempt to make a public item private → BLOCKED with clear message
5. [ ] Teacher removes their selection of a public item → item stays public for others

### Out of scope
- Curriculum (always public — T-058)
- Independent teacher private pool (M-05)

### Notes / known gotchas
- Default private is the safe default per §3.4; require explicit opt-in to share. Don't flip the default.

---

## T-060 — Content Library browse / search + tag filtering

**Layer:** 3
**Milestone:** M-04
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-3-teacher-onboarding.md` §5.3 (library tag filtering)

### ARCH source
- `ARCHITECTURE.md` §5 (API — list/filter), §3.18 (subject/grade tags)

### Depends on
- T-054 (data model), T-058, T-059 (content exists)

### What this ticket builds

**Frontend + backend:** A Content Library page — browse all items the user can see (school-public + own private), filter by subject, grade, language, and content_type (curriculum | reference). Search by title. Shows ingestion status badges. Respects visibility (private items only to creator).

### Acceptance (demo script)

1. [ ] Library page lists school-public items + the viewer's own private items
2. [ ] Filter by subject / grade / language / content_type works (combinable)
3. [ ] Title search works
4. [ ] Another teacher's private item is NOT visible
5. [ ] Ingestion status badge shown per item (ingesting/available/failed)

### Out of scope
- Cross-grade rule enforcement (T-063 — layered on top of this list)
- Selecting content into a lecture (Flow 5, M-09+)

---

## T-061 — Ingestion status tracking + retry + failure handling

**Layer:** 3
**Milestone:** M-04
**Estimate:** 1 day
**Status:** done

### Spec source
- `flow-3-teacher-onboarding.md` §3.3, §3.4 (INGESTING → AVAILABLE; failure paths)

### ARCH source
- `ARCHITECTURE.md` §10.5 (Celery retries / DLQ), §7.2 (pipeline stages)

### Depends on
- T-056 (ingestion), T-060 (library UI to show status)

### What this ticket builds

**Backend + frontend:** Robust status surface — per-item ingestion progress, failure reason capture, and a manual "retry ingestion" action. Failed items remain visible with a clear error and don't block the library.

### Acceptance (demo script)

1. [ ] An item stuck/failed shows a clear failure reason
2. [ ] "Retry ingestion" re-runs the task; success flips status to available
3. [ ] Transient failures auto-retry (3×) before surfacing as failed
4. [ ] A failed item doesn't break the library list for other items
5. [ ] Failures logged to DLQ per §10.5

### Out of scope
- Bulk re-ingestion (Phase 2)

---

## T-062 — Teacher self-edit capacity + School Admin override surface

**Layer:** 3
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.5 (capacity #11 — teacher-editable [1,20], admin override)

### ARCH source
- `ARCHITECTURE.md` §3.18 (capacity rule), §6.19 (override authority), §14.10 (audit)

### Depends on
- T-046 (capacity enforcement + override, M-03)

### What this ticket builds

**Frontend + backend:** A teacher can edit their own `teacher_capacity` within [1, 20] from their profile/settings. School Admin (and above) retains override authority for assignments beyond cap (already enforced in M-03 T-046; this ticket adds the teacher self-edit + surfaces the override path with audit).

### Acceptance (demo script)

1. [ ] Teacher edits own capacity 5 → 8 within bounds → persists
2. [ ] Capacity outside [1, 20] → rejected
3. [ ] Lowering capacity below current assignment count → warns but allowed (no auto-unassign); flagged
4. [ ] School Admin override above a teacher's cap still works (T-046) and is audit-logged
5. [ ] Capacity change emits a notification + audit entry

### Out of scope
- Auto-rebalancing assignments when cap lowered (Phase 2)

### Notes / known gotchas
- Capacity counts Grade-Subject assignments, not students (§3.18). Lowering below current count doesn't force unassignment — it just blocks NEW assignments until under cap.

---

## T-063 — Cross-grade content visibility in library

**Layer:** 3
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.3 (multiple curricula incl. cross-grade lower)

### ARCH source
- `ARCHITECTURE.md` §3.18 (cross-grade unidirectional rule), §7.21 (retrieval weighting)

### Depends on
- T-047 (cross-grade guard, M-03), T-060 (library list)

### What this ticket builds

**Backend:** Apply the T-047 `assert_cross_grade_access` guard to library visibility: a teacher working in Grade N can see/select content tagged grade ≤ N (lower or equal), but NOT higher-grade content. Wire the guard into the library list/filter query.

**Frontend:** Library reflects the rule — higher-grade items don't appear when scoped to a lower grade context.

### Acceptance (demo script)

1. [ ] Grade 9 context shows Grade 9 + Grade 8 curricula; NOT Grade 10
2. [ ] Grade 10 context shows Grade 10 + Grade 9 + lower
3. [ ] Untagged (grade-agnostic) reference books are visible regardless
4. [ ] Guard enforced server-side (not just UI hiding)
5. [ ] Reuses the exact T-047 guard (no duplicate logic)

### Out of scope
- RAG retrieval weighting at lecture-gen time (§7.21 — M-09+)

---

## T-064 — Soft-delete / remove lifecycle (citations retained)

**Layer:** 3
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.3, §3.4 (SOFT_DELETED / REMOVED; existing lectures retain citations)

### ARCH source
- `ARCHITECTURE.md` §4.x (soft-delete mixin)

### Depends on
- T-054 (data model)

### What this ticket builds

**Backend + frontend:** Soft-delete for library items (`deleted_at`). Soft-deleted items are hidden from new uses but retained so future lecture citations (M-09+) don't break. Removing a *selection* of a public item only removes that user's selection; the item persists if others use it.

### Acceptance (demo script)

1. [ ] Soft-deleting a curriculum hides it from the library + new selection
2. [ ] The underlying row + vectors are retained (citation integrity for future lectures)
3. [ ] Removing a selection of a public item leaves the item for other selectors
4. [ ] Soft-deleted items don't appear in browse/search/filter
5. [ ] Audit entry written on delete

### Out of scope
- Hard-delete / purge (Phase 2; prohibited-action territory per safety rules anyway)

---

## T-065 — Notifications (`content_library` namespace)

**Layer:** 3
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §7 (`content_library` namespace)

### ARCH source
- `ARCHITECTURE.md` §9.21 (namespaces), §9 (NATS)

### Depends on
- T-056 (ingestion events), T-038 (notification infra, M-02)

### What this ticket builds

**Backend:** Deliver `content_library` namespace notifications: ingestion complete (uploader notified item is AVAILABLE), ingestion failed, item published to school. NATS events for library mutations. All templates in 4 languages.

### Acceptance (demo script)

1. [ ] Ingestion complete → uploader gets `content_library.item_available`
2. [ ] Ingestion failed → uploader gets `content_library.item_failed`
3. [ ] Reference book published to school → relevant teachers notified per tags
4. [ ] NATS events published for library mutations
5. [ ] Templates present in en/ur/sd/ps (no `__TODO__`)

### Out of scope
- Student-facing library notifications (no students in M-04)

---

## T-066 — Audit logging for library + capacity changes

**Layer:** 3 / 6
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3 (audit-logged actions)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log)

### Depends on
- T-036 (audit infra, M-02)

### What this ticket builds

**Backend:** Register audit action types for: library upload, publish (private→public), soft-delete, curriculum ingestion, capacity self-edit, and capacity override. Reuse M-02 audit infra. Surface in the existing scope-restricted audit page.

### Acceptance (demo script)

1. [ ] Each library mutation writes an audit entry (actor, action, target, scope, time)
2. [ ] private→public publish is logged
3. [ ] Capacity override (School Admin) flagged/elevated
4. [ ] Audit page shows M-04 actions, scope-restricted per role

### Out of scope
- Audit export (Phase 2)

---

## T-067 — E2E smoke test (teacher → profile → upload curriculum → ingest → library)

**Layer:** 6
**Milestone:** M-04
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.1-§3.4 (full onboarding + library flow)

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-053 through T-066

### What this ticket builds

**Test harness:** Automated E2E running the milestone demo: teacher first login → profile completion → READY derivation (after M-03 assignment) → Coordinator uploads curriculum → ingestion completes → topic tree present → teacher uploads private reference → publishes → library search + cross-grade filter asserts → capacity self-edit + override. Runs in CI against the compose stack (uses a small fixture PDF).

### Acceptance (demo script)

1. [ ] E2E runs green in CI end-to-end
2. [ ] Ingestion pipeline asserted (status → available, chunks in Qdrant, topic tree for curriculum)
3. [ ] Privacy toggle + private→public one-way asserted
4. [ ] Cross-grade filter (Grade 9 sees ≤9) asserted
5. [ ] Idempotent / re-runnable with fresh tenants; uses a fixture PDF (no external download)

### Out of scope
- Frontend Playwright E2E (Phase 2 unless already established)
- Load testing

### Notes / known gotchas
- Use a tiny fixture PDF committed to the test fixtures; do not fetch from the network in CI (network is restricted).

---

## T-068 — Milestone M-04 PR + demo

**Layer:** 6
**Milestone:** M-04
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` v3 (whole flow, school tier)

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-053 through T-067

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-04 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-04` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-067 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-04 ticket set

---

## Milestone notes

- **School tier only.** Independent teacher signup + Platform Library are M-05. The ingestion pipeline built here is reused by M-05 for the Platform tier.
- **No lecture creation.** The library content ingested here is consumed by Flow 5 (M-09+). This milestone stops at "content is uploaded, parsed, embedded, searchable."
- **The RAG ingestion pipeline (T-056) is the heaviest ticket** — it's the first real exercise of §7 Pattern S (parse → chunk → embed → Qdrant). Curriculum structured parsing (T-057) layers on top.
- **Privacy defaults matter:** curricula are always school-public; reference books default PRIVATE with explicit opt-in to publish; private→public is one-way.
- **Capacity** (#11) enforcement shipped in M-03 (T-046); M-04 only adds teacher self-edit (T-062).
- **Cross-grade rule** reuses the T-047 guard — no new logic, just applied to library visibility (T-063).
- **Source flow:** Flow 3 v3 — finalized, no blockers. (Independent-tenant portions of Flow 3 deferred to M-05.)

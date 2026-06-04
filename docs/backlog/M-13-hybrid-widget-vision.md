# M-13 — Hybrid Widget + Multimodal Image + Vision LLM

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** todo
**Estimated duration:** 2 weeks
**Tickets:** T-166 through T-172
**Spec source:** `flow-6-student-studies-lecture.md` v1 §3.5 (hybrid text/voice/image input widget #57 — the image + vision portion)

## Goal

The second of four Flow 6 milestones. M-13 completes the hybrid input widget (#57) by **extending the text+voice component built in M-12 (T-155)** with image attachment, and wiring image-bearing questions to a vision-capable LLM. A student studying a lecture can now attach up to 3 images to a question (a diagram from a textbook, a photo of handwritten working, a screenshot), combine them freely with text and voice, and get an answer from a vision model that can actually see the images.

**Scope boundary (Flow 6 split M-12→M-15):**
- M-12 (done): viewer #54, highlight #55, AI answer panel #56, hybrid widget **text+voice base** #57.
- **M-13 (this):** **extends the same widget** with image attachment + vision-LLM routing (#57 full). Fleshes out the M-00 vision-routing stub (§8.22).
- M-14: live feedback #59, NATS consumer pipeline #60, per-session adaptation #61.
- M-15: highlight persistence + flashcards #58, concept enrichment #71, rating.

**Hard constraint (carried from M-12 T-155):** there is ONE hybrid widget component. M-13 **extends** it — it does not create a second input. The same component is the canonical input for Flow 5 chat / Flow 8 / Flow 11 when those are built.

**Demo at milestone end:**
- In the lecture Q&A panel, the student clicks the image-attach icon (or drag-drops, or pastes) → a textbook diagram attaches as a thumbnail chip below the input
- Student adds text ("why does this force diagram balance?") + the image, optionally dictates more by voice → all three combine in one question
- On send, because images are attached, the request routes to the vision model (Groq Llama-3.2-Vision) and the answer reflects the image content; pure text/voice questions still route to the default text model
- Attaching a 4th image is blocked (max 3); a 6 MB image is rejected (max 5 MB); a `.gif` is rejected (JPEG/PNG/WEBP only)
- EXIF is stripped on ingest; the image is stored per-tenant in MinIO; a linked parent's read-only access respects #72
- Multi-turn follow-up can attach a new image to the same conversation

---

## T-166 — `student_question_image` upload profile + ingest

**Layer:** 5
**Milestone:** M-13
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (image formats JPEG/PNG/WEBP; max 3 × 5 MB; EXIF stripped; MinIO per-tenant; 1-year retention)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`student_question_image` upload profile), §11 (uploads → MinIO), §3.16 (per-tenant scoping)

### Depends on
- T-155 (hybrid widget base, M-12), T-051-range (upload/MinIO infra, M-04)

### What this ticket builds

**Backend:** The `student_question_image` upload profile per §11.19 — accepts JPEG / PNG / WEBP only; max 3 images per question, max 5 MB each (server-side enforced, not just client); **EXIF stripped at ingest** (privacy); stored in MinIO **scoped per-tenant**; 1-year retention. Returns MinIO keys for the widget to reference in `attached_images[]`. Rejects oversized / wrong-format / >3 uploads with clear errors.

**Frontend:** None (the widget UI is T-167).

### Acceptance (demo script)

1. [ ] Upload accepts JPEG/PNG/WEBP; rejects other formats
2. [ ] Server enforces max 3 images + max 5 MB each (not client-only)
3. [ ] EXIF metadata stripped on ingest
4. [ ] Stored per-tenant in MinIO; 1-year retention set
5. [ ] Returns MinIO keys for `attached_images[]`

### Out of scope
- Widget UI (T-167), vision routing (T-168)

---

## T-167 — Hybrid widget: image attachment (extends T-155)

**Layer:** 5
**Milestone:** M-13
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (image-attach icon; drag-drop / paste / click; thumbnail chips; X to remove; 0-3 stack; combinable with text+voice)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §11.19 (upload profile)

### Depends on
- T-155 (the text+voice widget — **extend it**), T-166 (upload profile)

### What this ticket builds

**Frontend:** Extend the **existing** hybrid widget (T-155) — add the image-attach icon next to the mic; support drag-drop, paste (Ctrl/Cmd+V), and click-to-attach; render attached images as thumbnail chips below the text input with an X to remove; stack up to 3; freely combinable with text + voice in one submission. On send, include `attached_images[]` (MinIO keys from T-166). **This modifies the T-155 component in place — no new/forked input component.**

### Acceptance (demo script)

1. [ ] Image-attach icon + drag-drop + paste all attach images
2. [ ] Thumbnails render as chips below input; X removes one
3. [ ] Max 3 enforced in the UI (4th blocked) with a clear message
4. [ ] Text + voice + image combine in a single submission
5. [ ] It is the SAME component as T-155 (verified: no duplicate input implementation)

### Out of scope
- Vision routing (T-168)

### Notes / known gotchas
- §3.5 mandates ONE reusable widget. This ticket EXTENDS the M-12 T-155 component — do not create a parallel image-input component. The same widget is the canonical input reused by Flow 5 chat / Flow 8 / Flow 11.

---

## T-168 — Vision-LLM routing (fleshes out the M-00 §8.22 stub)

**Layer:** 5
**Milestone:** M-13
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (if `attached_images[]` present → vision model; else default text model; ~2-3× cost acceptable)

### ARCH source
- `ARCHITECTURE.md` §8.22 (Vision-LLM routing — M-00 built the basic scaffolding stub), §8.6 (typed prompt, vision-capable variant), STACK_LOCK §4 (Groq Llama-3.2-Vision)

### Depends on
- T-166 (image keys), T-158 (answer pipeline, M-12)

### What this ticket builds

**Backend:** Flesh out the M-00 vision-routing stub (§8.22): when a question's `attached_images[]` is non-empty, route the request to the vision-capable model (Groq Llama-3.2-Vision) with the images passed in context; pure text/voice questions continue to the default text model. The ~2-3× per-call cost with images is accepted (Flow 6 §3.5). Integrate into the T-158 answer pipeline so routing is transparent to the panel.

### Acceptance (demo script)

1. [ ] Images present → routes to Groq Llama-3.2-Vision
2. [ ] No images → routes to default text model (unchanged)
3. [ ] Images passed in model context (answer reflects image content)
4. [ ] Builds on the M-00 §8.22 stub (not a new routing layer)
5. [ ] Cost difference logged for observability

### Out of scope
- The widget UI (T-167); RAG grounding changes (still Pattern S per T-158)

---

## T-169 — Vision Q&A integration in the lecture flow

**Layer:** 5
**Milestone:** M-13
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.4 + §3.5 (image-bearing questions flow through the #56 answer panel; multi-turn)

### ARCH source
- `ARCHITECTURE.md` §7.3-7.10 (RAG grounding still applies where text-answerable), §5.9-5.10 (idempotent submission), §9 (`student.question.asked` carries image refs)

### Depends on
- T-167 (widget images), T-168 (vision routing), T-159/T-160 (answer panel + multi-turn, M-12)

### What this ticket builds

**Frontend + backend:** Wire image-bearing questions end-to-end through the existing #56 answer panel — the question (text + voice transcript + `attached_images[]`) submits, routes via T-168, and the streamed vision answer renders in the same side panel / bottom sheet. Source badges still apply where the answer draws on curriculum/reference text; image-derived reasoning is badged appropriately ([AI Knowledge] for pure-vision reasoning). Multi-turn follow-ups may attach new images to the same conversation. `student.question.asked` event carries image refs.

### Acceptance (demo script)

1. [ ] Image question → vision answer streams in the existing answer panel
2. [ ] Text + voice + image in one question all reach the model
3. [ ] Source badges correct; pure-vision reasoning badged [AI Knowledge]
4. [ ] Follow-up can attach a new image to the same conversation
5. [ ] Question event carries image references

### Out of scope
- New panel UI (reuses M-12 T-159/T-160)

---

## T-170 — Image-question privacy, retention + cost limits

**Layer:** 5
**Milestone:** M-13
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (per-tenant, EXIF, 1-year retention), §3.x privacy #72

### ARCH source
- `ARCHITECTURE.md` §3.16 (per-tenant), §6.13/§6.19 (parent read-only subject to #72), §14.10 (audit)

### Depends on
- T-166 (ingest), T-168 (vision cost), T-162 (privacy matrix, M-12)

### What this ticket builds

**Backend:** Extend the M-12 privacy/permissions model to image questions — attached images obey privacy #72 (opted-out students' image questions hidden from parent read-only just like text); images scoped per-tenant; EXIF-strip + 1-year retention verified end-to-end; a vision-cost guard (per-student/day soft ceiling, configurable env var) to bound the ~2-3× cost. Independent-tenant image questions tagged + scoped to the independent schema.

### Acceptance (demo script)

1. [ ] Image questions respect #72 (parent read-only hides opted-out)
2. [ ] Images per-tenant scoped; EXIF stripped; 1-year retention enforced
3. [ ] Vision-cost guard caps runaway image-question cost (configurable)
4. [ ] Independent-tenant image questions tagged + isolated
5. [ ] No cross-tenant image access possible

### Out of scope
- General cost dashboards (Phase 2)

---

## T-171 — Audit + i18n + notifications + reuse contract

**Layer:** 5 / 6
**Milestone:** M-13
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5 (canonical reusable widget), §7 (notifications), i18n throughout

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit), §13 (i18n; vision answer in question language), §9.21 (namespaces)

### Depends on
- T-166 through T-170

### What this ticket builds

**Backend + docs:** Audit entries for image uploads + vision-routing decisions + any admin overrides. i18n — vision answers returned in the question's language; widget UI strings (attach/remove/limits) in en/ur/sd/ps (RTL); no `__TODO__`. Document the **reuse contract** for the now-complete hybrid widget (the canonical text/voice/image input) so Flow 5 chat / Flow 8 / Flow 11 import it rather than re-implementing; note the existing Flow 5 creation-chat input as a tracked follow-up to migrate onto the shared widget (not forced in M-13 to avoid disturbing working M-09 code).

### Acceptance (demo script)

1. [ ] Image uploads + vision-routing decisions audit-logged
2. [ ] Vision answers in the question's language; widget UI in 4 languages, RTL
3. [ ] No `__TODO__` strings
4. [ ] Reuse contract documented; widget exported as the canonical shared component
5. [ ] Flow 5 creation-chat migration logged as a tracked follow-up (TODO.md)

### Out of scope
- Actually migrating Flow 5 creation chat (tracked follow-up, not this milestone)

---

## T-172 — E2E smoke test + milestone PR

**Layer:** 6
**Milestone:** M-13
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-6-student-studies-lecture.md` §3.5

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention), per `WORKFLOW.md` Step 2

### Depends on
- T-166 through T-171

### What this ticket builds

**Test + PR:** Automated E2E (vision LLM / STT / upload mocked; no live network) — attach image (icon + drag-drop + paste paths) → reject 4th image / 6 MB file / `.gif` → combine text + voice + image → submit → routes to vision model (asserted) → vision answer streams in the panel → pure text question still routes to text model → EXIF-strip + per-tenant scoping + #72 + cost-guard asserted → follow-up with a new image. Then the single milestone PR per `WORKFLOW.md` Step 2 (`phase-complete-review`, demo for Abd. + Awais; merge-commit to `staging` per BRANCHING.md; tickets = commits).

### Acceptance (demo script)

1. [ ] E2E green (vision/STT/upload mocked; no live network)
2. [ ] Asserts format/size/count rejection + EXIF strip + per-tenant scope
3. [ ] Asserts vision-vs-text routing + combined text/voice/image
4. [ ] Asserts #72 + cost guard
5. [ ] PR `milestone/M-13-...` → `staging`; `phase-complete-review` passes; CI (incl. ticket-status-check) green; merged

### Out of scope
- Anything beyond the M-13 ticket set

---

## Milestone notes

- **Extends, does not rebuild.** The whole milestone hangs off the M-12 T-155 hybrid widget — M-13 adds image+vision to the SAME component. The "no duplicate input" rule (§3.5) is the central constraint.
- **Vision routing builds on M-00's §8.22 stub** — flesh it out, don't add a parallel router.
- **Cost is bounded, not unlimited.** Vision calls are ~2-3× (accepted by the spec), with a configurable per-student/day guard (T-170).
- **Privacy carries over.** Image questions obey #72 + per-tenant scoping exactly like text questions; EXIF stripped at ingest.
- **No new BLOCKED-HOOKs.** Vision/image is self-contained — no deferral to a blocked flow (9-12). (The M-12 Cognitive-DNA event hook still stands from T-163; M-13 adds nothing new there.)
- **Reuse contract documented; Flow 5 creation-chat migration is a tracked follow-up** (TODO.md), deliberately not forced here to avoid disturbing working M-09 code.
- **Open questions:** §3.5 image/vision rules are fully specified (no open question governs this milestone); built to spec.
- **Source flow:** Flow 6 v1 §3.5 (image+vision portion) — fully specified, no blockers.

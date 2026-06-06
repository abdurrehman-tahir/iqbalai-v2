# AMENDMENTS.md — Architecture decisions that changed after launch

**Status:** Locked process. Append-only log.
**Owner:** @abdurrehman-tahir
**Purpose:** When reality contradicts an `ARCHITECTURE.md` decision, this is where we document the change. Different from `DEVIATIONS.md`.

---

## When to use this file

| File | Use for |
|---|---|
| `DEVIATIONS.md` | "I'm using a library outside `STACK_LOCK.md` — here's why." Pre-approved exceptions to the locked stack. |
| `AMENDMENTS.md` (this file) | "We said X in `ARCHITECTURE.md` §N. We now say Y because reality showed us X was wrong/incomplete." Architecture-level changes. |
| `TODO.md` | "We deferred X to Phase 2+. Not done yet." Future work. |

If you're about to silently ignore something in ARCHITECTURE.md because "it doesn't quite work in practice," **stop**. That's an amendment. File one here.

---

## The process

1. **You hit something where the locked architecture doesn't fit reality.** Example: §10.6 says beat is a singleton, but you discovered a way to safely run it as a pair with `redbeat` locking, and you want to do that.
2. **Open a PR with two changes:**
   - Update `ARCHITECTURE.md` to the new decision (with the OLD text struck through or rewritten in place).
   - Add an entry to this file (see template below).
3. **Abd. reviews and approves.** This is the same gate as any other architecture change — not lower-bar.
4. **On merge,** the amendment is locked in. Future readers see both the new architecture AND the history of how it got there.

**Never** edit `ARCHITECTURE.md` without a matching `AMENDMENTS.md` entry. Silent drift is forbidden — that's the whole point of this file.

---

## Amendment template

Copy this block for every new amendment:

```markdown
## A-NNN — <short title>

- **Date:** YYYY-MM-DD
- **Author:** @<github-handle>
- **Affects:** `ARCHITECTURE.md` §<X.Y>
- **Status:** approved | reverted

### What changed

<One paragraph: what was the old decision, what's the new one.>

### Why

<What made us change our minds? A bug? A measurement? A failed deploy? A new product requirement? Be specific.>

### What we considered before deciding

<Other options we evaluated. Why we picked this one.>

### Migration

<If existing code or data needs to change to match, list the steps. If not, say "no migration needed."

### What this DOES NOT change

<Things people might assume changed but actually didn't. Helps prevent over-correction.>

### Related

- Original section: `ARCHITECTURE.md` §<X.Y>
- Related PRs: #NNN, #NNN
```

---

## Amendments

(Append below this line. Newest at the top.)

## A-002 — TS API types generated from OpenAPI (brought forward from Phase 2)

- **Date:** 2026-05-29
- **Author:** @abdurrehman-tahir
- **Affects:** `ARCHITECTURE.md` §12.4, §2.13
- **Status:** approved

### What changed

§12.4 + §2.13 specified that `types.ts` TypeScript types are hand-mirrored from backend Pydantic models, with auto-generation deferred to Phase 2 (TODO). We now **generate** them from the backend OpenAPI via **openapi-typescript** (`frontend/src/lib/api/schema.d.ts`), **at launch (M-01a)**. Hand-mirroring is forbidden; `types.ts` re-exports the generated schema.

### Why

Manual type-mirroring is the structural root cause of the FE↔BE integration failures observed while implementing M-00/M-01 (backend correct, frontend calling mismatched request/response shapes). Drift is unavoidable while two type definitions are maintained by hand. openapi-typescript is build-time, zero-runtime, MIT, and pairs with the already-locked TanStack Query layer — pulling it forward is cheap and removes the entire drift class rather than papering over it.

### What we considered before deciding

`orval` (generates hooks + types — heavier; would duplicate the locked hand-written `api.ts`/TanStack hook layer); staying manual (rejected — it is the root cause); a runtime-only Zod validation layer (doesn't catch compile-time drift). Chose **openapi-typescript**: lightest, types-only, leaves the locked `api.ts` hook pattern intact.

### Migration

M-01a adds the generator + a CI drift check; existing M-00/M-01 `api.ts`/`types.ts` are regenerated against the live OpenAPI as part of the M-01a audit-fix tickets. `response_model=` is now mandatory on every endpoint (STACK_LOCK §1) so the generated OpenAPI is complete.

### What this DOES NOT change

The locked `api.ts` client-object pattern, the TanStack Query hooks, and the base `apiClient` (§12.4/§12.5) stay exactly as-is — only the *types* feeding them become generated. `schemas.ts` Zod schemas for form validation remain (now derived from generated types).

### Related

- `ARCHITECTURE.md` §12.4, §12.5, §2.13; `STACK_LOCK.md` §2 (openapi-typescript row + `response_model` mandate); `docs/backlog/M-01a-foundation-remediation.md`

---

## A-001 — Spec-set review consolidation (Flows 1-6 + Flow 13)

- **Date:** 2026-05-14
- **Author:** @abdurrehman-tahir
- **Affects:** `ARCHITECTURE.md` §0.1, §3.16, §3.17, §3.18, §3.19, §4.21, §6.19, §6.20, §6.21, §6.22, §7.21, §7.22, §8.20, §8.21, §8.22, §8.23, §9.3, §9.21, §9.22, §10.6, §11.19, §11.20, §11.21
- **Status:** approved

### What changed

Eighteen related decisions across the foundational architecture, locked during product review of feature specs Flow 1 through Flow 6 (and the new Flow 13 thin subscription spec):

1. **Personas (#9):** 4 named + 1 Custom slot (replaces v1's "4 + 2 TBD"). Custom persona uses LLM weekly batch summary per ARCH §8.20 — per-student, ~200-word description, prepended to system prompt. Per Q1 feedback.
2. **Disclaimer/ToS (#13):** English-only at launch with `__TODO__` markers for ur/sd/ps; not a production blocker except before Phase 6 (predictions). Per Q3 feedback.
3. **Legal review:** TODO entry — basic industry-standard ToS at launch. Per Q2 feedback.
4. **Data archival:** all data hot at launch; hot/warm/cold tiering deferred to TODO. Per Q4 feedback.
5. **Content Library (#7):** redefined as multi-tier (Platform / School / Personal) multi-source architecture. Privacy rules per uploader role explicitly locked: Curriculum always public to its tier; Admin reference uploads always public to school; Teacher reference uploads default PRIVATE with one-way Private→Public toggle; Student/Independent personal pools always private. Per Q6-Q10 feedback.
6. **Grade/Section/Subject restructure:** entire Flow 2 model redesigned around Grade (primary), Section (optional child), GradeSubjectOffering (Subject linked to Grade per session, teacher assigned here). Replaces v1 "Class" model. Per v3 Q11-Q13 feedback.
7. **Teacher capacity:** redefined as Grade-Subject assignment count (NOT student count). Default cap = 5, range [1, 20]. School Admin can override (audit-logged). Per v3 Q14 feedback.
8. **All 6 roles created at launch** (District Admin not skipped). Per Q8 feedback.
9. **Manual public signup (Path B) for independent users only.** School users via admin-invitation Path A only. Per Q21 feedback.
10. **Permission inheritance (§6.19):** `require_role(X)` means "X or higher within scope." Locked across all flows.
11. **Notification namespaces (§9.21):** 7 locked namespaces (`lectures`, `self_study`, `quiz`, `connections`, `content_library`, `system`, `account`). Per-feature boards + global aggregate panel UI model. Notifications cannot be turned off. Per Q13-Q17 feedback.
12. **One language per user platform-wide** (not per-channel). Per Q9 feedback.
13. **Independent users — separate-schema tenant model (§3.16):** dual Postgres schemas in same instance; dual Alembic heads per §4.21; cross-schema views for platform-shared tables.
14. **Subscription module (§3.17 + Flow 13):** schema-only at launch; Platform Admin tier CRUD active; District/School subscribe buttons show "Coming soon" modal; no Stripe code; placeholder env vars. Free for all at launch.
15. **Promotion workflow (§6.21):** Coordinator-initiates per-grade with manual exclusion list; School Admin approves; atomic Celery transaction with 5-retry. Grade 12 promotion triggers graduation cascade. Per Q18-Q23 feedback.
16. **Exam Framework engine (§3.19 + §8.21):** Platform-level, AI-generated study plans via Pattern-A agentic LLM. Quarterly refresh (`framework.refresh_quarterly`). Manual Platform Admin approval with 72hr SLA. Initial launch set: Matric Punjab + FSc Punjab + O-Level Cambridge + A-Level Cambridge. Per Q-EF1 through Q-EF10 feedback.
17. **Graduation lifecycle (Flow 4 v3 §3.9):** 6-month read-only school window with full Self-Study access, then atomic auto-migration to independent tenant with all learning data preserved. Configurable via `GRADUATION_GRACE_DAYS` env var (default 180). Linked parents auto-severed at migration.
18. **Multimodal question support (Flow 6 v2 Awais feedback):** hybrid widget #57 extended to accept image attachments (max 3 per question, 5 MB each, JPEG/PNG/WEBP). New upload profile `student_question_image` in §11.19. Vision-LLM routing in §8.22 — requests with `attached_images[]` route to Groq Llama-3.2-Vision; pure text routes to default model. Inherits to all flows using widget (Flow 5 wizard chat, Flow 7 review, Flow 8 self-study, Flow 11 group study).

### Why

Two-week intensive review rounds with product (Awais, Mufti, CXO layer) and technical (Hamza, Abd.) stakeholders. The v1 architecture was correct at the abstract level but had to be sharpened against concrete feature workflows in 7 spec drafts. Each item above resolves a specific ambiguity or product decision uncovered during spec drafting.

### What we considered before deciding

Documented in the per-spec change logs (`flow-N-*.md` v2/v3) and the consolidation ledger (retained and renamed `docs/feature-specs/_CHANGE_LOG.md`; this AMENDMENTS.md remains the canonical amendment record).

### Migration

No code migration needed — all changes are pre-Phase-1 (Hamza has not started implementation yet). T0 batch applies decisions to ARCHITECTURE.md + supporting docs + skills. Phase 1 development proceeds from the post-T0 state.

### What this DOES NOT change

- Existing STACK_LOCK: stack remains as locked. Voice path (faster-whisper + Piper/Edge-TTS/AI4Bharat), NATS JetStream, Authentik, etc. unchanged.
- Tenant isolation principles: still three-layer defense (router auth dep → repo filter → DB RLS). Independent schema is an additional layer, not a relaxation.
- Coaching-not-grading principle: AI never grades students/teachers. All scoring + rating surfaces preserve this.

### Related

- Original sections (pre-amendment baseline): §3 multi-tenancy, §4 DB patterns, §6 auth, §7 RAG, §8 LLM, §9 events, §10 jobs, §11 uploads
- Feature specs: `docs/feature-specs/flow-1-platform-setup.md` (v2), `flow-2-admin-coordinator-setup.md` (v3), `flow-3-teacher-onboarding.md` (v3), `flow-4-student-onboarding.md` (v3), `flow-5-teacher-creates-lecture.md` (v1), `flow-6-student-studies-lecture.md` (v2), `flow-13-subscriptions.md` (v1)
- Related PRs: T0 batch PR (this PR)

---

## Reverted amendments

(If an amendment is later reverted, move its full entry here with `Status: reverted` and an explanation of why.)

<!-- None yet. -->

---

**Last updated:** 2026-05-14
**Owner:** @abdurrehman-tahir

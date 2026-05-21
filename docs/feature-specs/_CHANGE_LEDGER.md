# Change Ledger — Non-Spec Doc Updates Pending

**Purpose:** Working document tracking every decision made during flow-spec review that requires changes to ARCHITECTURE.md, AMENDMENTS.md, TODO.md, ENV_VARS.md, STACK_LOCK.md, _TEMPLATE.md, CLAUDE.md, HAMZA_START_HERE.md, README.md, or any skill files.

**Status:** Working document. NOT committed to bootstrap zip. Deleted once all changes are applied.

**Workflow:**
1. Every flow review produces decisions → captured here as pending edits.
2. After all 12 flows reviewed, this ledger drives the batch update of all non-spec docs.
3. Each entry includes: doc, section, change description, source decision.

**Last updated:** 2026-05-14

---

## ARCHITECTURE.md additions pending

### §3.16 — Independent users tenant model (NEW SUBSECTION)
- **Change:** Add new subsection describing the separate-Postgres-schema isolation for independent users (Option B from Q1).
- **Content:** Two Postgres schemas in same instance: `school` (default) and `independent`. Same database, same operational stack, separate tables, separate RLS policies. JWT `tenant_type` claim routes requests to the correct schema repository. Auth via single Authentik IDP with property mapper assigning `tenant_type=school|independent`.
- **Source:** Flow 1 Q10 + Subscription discussion Q1 (Option B confirmed)
- **Spec dependencies:** flow-1-platform-setup.md, flow-3-teacher-onboarding.md, flow-4-student-onboarding.md, flow-13-subscriptions.md (future)

### §3.17 — Subscription as cross-cutting tenant attribute (NEW SUBSECTION, schema-only at launch)
- **Change:** Add new subsection. Subscriptions attach to either District or School (school inherits from District if subscribed). Schema exists; UI placeholders; NO Stripe code; NO cap enforcement at launch.
- **Source:** Flow 2 subscription discussion + Q1-Q10 answers (all "your recommendation"; Q6 = no paid services / placeholders; Q7 = no implementation, placeholders)
- **Spec dependencies:** flow-13-subscriptions.md (future thin spec)

### §3.18 — Grade / Section / Subject model (NEW SUBSECTION)
- **Change:** Document the new entity model: Grade (Grade 9 at School X for session 2025-2026) → Section (A, B, C — optional) → Student enrollment. Subject catalog school-scoped. GradeSubjectOffering links Subject to Grade-Session. Teacher assigned at GradeSubjectOffering level (not section level per Q13 simpler answer).
- **Source:** Flow 2 nomenclature feedback + Q11-Q16 answers
- **Spec dependencies:** flow-2-admin-coordinator-setup.md v3 (future), flow-3-teacher-onboarding.md (REDEFINED capacity), flow-4-student-onboarding.md v2 (Grade-based enrollment)

### §4.21 — Dual Alembic heads (NEW SUBSECTION)
- **Change:** Document Alembic migration strategy with two heads: school schema head + independent schema head. Migrations apply per-schema. Co-located in same `alembic/versions/` but separated by branch labels.
- **Source:** Q1 subscription discussion (Option B = separate schemas)
- **Spec dependencies:** all flows that touch DB

### §6.16 — Permission inheritance semantic (NEW SUBSECTION)
- **Change:** Lock the semantic: `require_role(MIN_ROLE)` means "MIN_ROLE or higher within correct scope." Every role higher in hierarchy automatically inherits all permissions of lower roles, bounded by scope. Coordinator → School Admin → District Admin → Platform Admin.
- **Source:** Flow 2 feedback (Q19 + permission matrix inheritance feedback)
- **Spec dependencies:** flow-2, flow-3, flow-4, and ALL future flow specs

### §6.17 — Independent user signup path (NEW SUBSECTION)
- **Change:** Document `/independent/signup` route + Authentik property mapper for `tenant_type=independent` JWT claim. Separate from school admin invitation flow.
- **Source:** Flow 1 Q10 + Q3 subscription discussion (same Authentik for both)
- **Spec dependencies:** flow-3 (independent teacher), flow-4 (independent student)

### §6.18 — Promotion approval workflow (NEW SUBSECTION)
- **Change:** Document the Coordinator-initiated → School Admin-approved promotion request lifecycle. PENDING_APPROVAL → APPROVED → EXECUTED OR REJECTED. Exclusion list of students held back. Bulk transaction.
- **Source:** Flow 2 Q6 + Flow 2 promotion workflow feedback + Q18-Q23 answers
- **Spec dependencies:** flow-2-admin-coordinator-setup.md v3 (future), flow-4 (graduation lifecycle)

### §8.16 — Custom persona learning batch (NEW SUBSECTION)
- **Change:** Document the weekly LLM batch process for Custom Persona (5th persona option). Per-student global; rolling cadence configurable via env var `PERSONA_LEARNING_BATCH_DAYS` (default 7). Pull last 7 days of student-AI interactions (max 50 turns), LLM summarizes into persona description string, prepended to system prompt for future AI calls. No fine-tuning, no ML training.
- **Source:** Flow 1 Q1 (Custom persona) + Q10-Q13 subscription discussion
- **Spec dependencies:** flow-1-platform-setup.md v2 (future)

### §3.19 — Exam Framework engine (NEW SUBSECTION)
- **Change:** Document the Exam Framework concept as a platform-level, AI-generated, quarterly-refreshed study plan for specific exam targets (Matric Punjab, O-Level Cambridge, MDCAT, FSc Punjab, etc.). Framework definitions are Platform Admin-owned. Study plan content is AI-generated via Pattern-A agentic LLM (web search via SearXNG + content synthesis). Platform Admin approves each version before publication. Quarterly refresh via Celery beat. Students select 1+ frameworks; framework drives Self-Study Mode structure primarily; overlays Lecture Mode as exam-prep supplement.
- **Content:** Three entity types — `exam_frameworks` (definitions), `framework_study_plans` (versioned AI-generated content), `framework_research_jobs` (audit trail of AI runs). Versioning model: students pin to version at selection; v2 banner offers upgrade. Region scoping per framework. AI research cost ceiling $10/refresh; total operational cost ~$400/year for 10 frameworks.
- **Source:** Flow 4 v3 feedback Q5 (Exam Framework redefined) + Q-EF1-EF10 answers
- **Spec dependencies:** flow-4 v3, flow-6 (lecture mode framework overlay), flow-8 (self-study framework-driven), flow-9 (AI intelligence framework contribution)

### §8.17 — Quarterly Exam Framework refresh agent (NEW SUBSECTION)
- **Change:** Document the Pattern-A LLM agent that researches and generates framework study plans. Tool chain: web_search via SearXNG → web_fetch top sources → LLM synthesis → produce structured JSONB plan + cited sources. Quarterly Celery beat task `framework.refresh_quarterly` (per framework). Manual approval gate by Platform Admin (72hr SLA target, 7-day reminder, 14-day escalation). Cost ceiling $10/run (hard cap). Output content structure: topics with priority weights, exam patterns, practice problems (AI-generated similar to public past papers, never republishing copyrighted material), weekly pacing, exam strategy.
- **Source:** Flow 4 v3 Q5, Q-EF4 (content structure confirmation), Q-EF5 (copyright handling)
- **Spec dependencies:** flow-4 v3

### §11.17 — Upload profiles (consolidated NEW SUBSECTION)
- **Change:** Document all upload profiles. `platform_reference_book` (100 MB, PDF, Platform Library scope). `school_library_content` (100 MB, PDF, school-scoped, tags required). `independent_personal_content` (100 MB, PDF, per-user namespace). `lecture_image` (5 MB, JPEG/PNG/GIF, lecture-scoped, embedded in lecture body). `bulk_import` (5 MB, CSV/XLSX, ≤ 5000 rows). `student_question_image` (5 MB, JPEG/PNG/WEBP, EXIF stripped at ingest, per-tenant MinIO namespace, 1-year retention, max 3 per question).
- **Source:** Flow 1 Q10 + Flow 3 v3 + Flow 5 + Flow 6 v2 (Awais image attachments) + Flow 2 v3 bulk import
- **Spec dependencies:** flow-1, flow-2, flow-3, flow-5, flow-6 v2

### §8.18 — Vision-LLM routing (NEW SUBSECTION per Flow 6 v2)
- **Change:** Document automatic LLM model routing based on payload contents. Requests with `attached_images[]` field route to Groq Llama-3.2-Vision (vision-capable). Pure text/voice requests route to default text model (Groq Llama 3.3 70B per STACK_LOCK). Cost differential ~2-3× per call with images. Expected < 10% of question volume uses images at launch.
- **Source:** Flow 6 v2 Awais feedback
- **Spec dependencies:** flow-6 v2; future flows using hybrid widget #57 inherit (flow-5 wizard chat, flow-7 review, flow-8 self-study, flow-11 group study)

### §7.13 — Cross-grade unidirectional RAG retrieval weighting (NEW SUBSECTION per Flow 5)
- **Change:** When a lecture wizard targets Grade N, RAG retrieval filters library content to items where `max(grade_range) ≤ N` (per Flow 2 v3 unidirectional rule). Items containing N in `grade_range` get full weight; items strictly below N (lower-grade material) get half weight (factor 0.5). Default toggle in wizard hides cross-grade items entirely; explicit "include lower grades" toggle reveals them with reduced weighting. Reverse direction (Grade N reading higher-grade content) blocked at API level.
- **Source:** Flow 5 v1 §3.2 + Flow 3 v3 §5.3 + Flow 2 v3 unidirectional cross-grade rule
- **Spec dependencies:** flow-5 v1, flow-3 v3, flow-2 v3

### §0 Quick Index update
- **Change:** Update the task→sections map in §0.1 to reflect new subsections (§3.16-3.19, §4.21, §6.16-6.18, §8.16-8.18, §9.14, §11.17-11.18).
- **Source:** all the above
- **Spec dependencies:** ALL flow specs

---

## AMENDMENTS.md entries pending

### Entry 1 (single dated entry capturing all approved changes from Flows 1-4 review rounds, including v3 feedback)

**Date:** 2026-05-14
**Approved-by:** @abdurrehman-tahir (in this conversation)
**Reviewers:** awaiting Awais sign-off on flow specs

**Summary:** Major architectural amendments approved after first + second review passes on Flow 1-4 specs:

1. **Independent users — separate-schema tenant model** (Q1 = Option B). Two Postgres schemas (school, independent) in same instance.
2. **Permission inheritance semantic.** `require_role(X)` means "X or higher within scope" across all roles.
3. **Notification namespaces (7 locked).** Each notification routes to feature-specific board; global panel shows aggregates only.
4. **Custom Persona (5th).** Per-student LLM-learned persona; weekly batch update; env-var-configurable cadence.
5. **Subscription model (schema-only at launch).** Tiers + subscriptions + payments tables exist; no Stripe code; no cap enforcement; free for all at launch.
6. **Grade / Section / Subject restructure** replacing Class/Subject from v1 of Flow 2. Grade is primary; Section optional; Subject offered to Grade per session.
7. **Teacher capacity redefined** as Grade-Subject assignment count (default 5, range [1, 20]) — not student count.
8. **Promotion workflow** with exclusion lists, Coordinator-initiates / School Admin-approves.
9. **Teacher discovery (#19/#20) removed for school students.** Replaced by automatic Grade enrollment.
10. **Cross-grade content unidirectional** (Grade N can access ≤Grade-N material; reverse blocked).
11. **Library privacy toggle** for teacher reference uploads (default private; admins always public; students always private).
12. **Curriculum vs Reference book** clarified — curriculum = official course book; reference = supplementary material.
13. **All hierarchy roles created from start** (no skipping District Admin or other roles at launch).
14. **Profile mandatory fields trimmed** to name + language preference + ToS acceptance only; other fields deferrable (v3 feedback Q1).
15. **Independent students get diagnostic** at launch (v3 feedback Q3), calibrated per-framework.
16. **Exam Framework engine** (NEW per v3 feedback Q5): platform-level AI-generated study plans, quarterly refreshed, Platform Admin-approved, multi-framework per student, drives Self-Study Mode + augments Lecture Mode.
17. **Graduation lifecycle rewritten** (v3 feedback): 6-month read-only school window with full Self-Study access, then atomic auto-migration to independent tenant with all learning data preserved. Configurable via `GRADUATION_GRACE_DAYS` env var (default 180). Linked parents auto-severed at migration.
18. **Multimodal question support (Flow 6 v2 Awais feedback):** hybrid widget #57 extended to accept image attachments (max 3 per question, 5 MB each, JPEG/PNG/WEBP). New upload profile `student_question_image` in §11.17. Vision-LLM routing in §8.18 — requests with `attached_images[]` route to Groq Llama-3.2-Vision; pure text routes to default model. Inherits to all flows using widget (Flow 5 wizard chat, Flow 7 review, Flow 8 self-study, Flow 11 group study).

**Sources:** Flows 1-4 review conversations + Q1-Q28 answers + Flow 3 v3 + Flow 4 v3 + subscription Q1-Q10 answers + Flow 2 follow-up feedback + Flow 4 v3 feedback round (Q-EF1-EF10, Q-FB1-FB5).

**Files impacted:** ARCHITECTURE.md (multiple new subsections); flow-1, flow-2, flow-3, flow-4 specs; flow-13 (new); _TEMPLATE.md; CLAUDE.md; HAMZA_START_HERE.md; TODO.md; ENV_VARS.md.

---

## TODO.md additions pending

### Phase 2 — moved here from Flow 1 / Flow 2 / Flow 3 / Flow 4 specs

1. **Full legal review of ToS** (Flow 1 Q2; basic industry-standard ToS for launch only)
2. **Disclaimer translations to ur/sd/ps** (Flow 1 Q3; English only at launch — no production blocker)
3. **Independent-to-school migration** (Q2 subscription discussion; no migration at launch)
4. **Cross-grade student-initiated teacher discovery** (Flow 4 Q17 follow-up; #19/#20 removed at launch)
5. **Per-section teacher assignments** (Flow 2 Q13 — answered "yes" but launch keeps Grade-Subject-level assignment for simplicity)
6. **CSV import for promotion exclusions** (Flow 2 Q19 = "your recommendation" = manual checkboxes at launch)
7. **Bulk-promote-all grades** (Flow 2 Q18 = per-grade only at launch)
8. **School → Independent migration on graduation** (Flow 4 Q22 = manual new account at launch)
9. **Subscription cap enforcement** (Flow 13 thin-spec; placeholder UI at launch)
10. **Stripe integration** (Q6 subscription discussion; no paid services at launch)
11. **Cross-school content library sharing** (Flow 3 v3 §9; school-scoped only at launch)
12. **Library moderation workflow** (Flow 3 v3 §9; direct upload at launch)
13. **Teacher rating by students** (Flow 3 v3 §9; OUT per coaching-not-grading policy — explicitly never)
14. **Region-weighted recommendation ML** (Flow 4 v2 §9; discovery removed entirely)
15. **Auto-deactivation of stale bulk-imported students** (Flow 4 v2 §9; manual School Admin review only)
16. **Adaptive question difficulty (CAT) for diagnostic** (Flow 4 v2 §9)
17. **Multi-script names** (Flow 4 v2 §9; single canonical name at launch)
18. **Student ID verification** (Flow 4 v2 §9; trust-based at launch)
19. **Self-service parent-initiated child deletion** (Flow 4 v2 §9; support channel only at launch)
20. **Independent student parent linking** (Flow 4 v2 §9; deferred at launch)
21. **Independent student diagnostic** (Flow 4 v2 §9; not at launch)
22. **Foldering / tagging in Independent Teacher dashboard** (Flow 3 v3 §9; flat list at launch)
23. **Bulk teacher import** (Flow 3 v3 §9; individual invite at launch)
24. **Sentry self-hosted** (deferred from launch per earlier batch; observability via Loki at launch)
25. **Backup automation** (deferred from launch per earlier batch; manual at launch)
26. **TMS integration (Crowdin/Lokalise/Weblate)** (per ARCHITECTURE §13.16; manual JSON editing at launch)
27. **URL-prefixed locales** (per §13.3; cookie + user preference only at launch)
28. **Per-channel language preferences** (Flow 1 Q9; one-language-per-user at launch)
29. **Eastern Arabic digit display preference** (per §13.16)
30. **Hijri calendar** (per §13.16)
31. **Self-service school registration** (Flow 2 §9; manual Platform Admin onboarding at launch)
32. **Audit log queryable UI** (Flow 2 §9; minimal "last 50 actions" log at launch, DB-query for full)
33. **Co-teaching** (Flow 2 §9; one primary teacher per Grade-Subject at launch)
34. **Class roll-over automation** (Flow 2 §9; promotion workflow is manual + approval-driven at launch)
35. **Coordinator write access expansion** (Flow 2 §9; read-only + assigned-scope-writes at launch)
36. **Sub-classes / sections beyond optional A/B** (Flow 2 §9; simple optional Section A/B/C at launch)
37. **Cross-subject classes (homeroom)** (Flow 2 §9; one-subject-per-class at launch)
38. **District Admin policy controls** (Flow 2 §9; schema exists; UI deferred)
39. **Credential verification for teachers** (Flow 3 v3 §9; trust-based at launch)
40. **Curriculum customization by teachers** (Flow 3 v3 §9; read-only at launch)
41. **Reference book sharing across teachers** (Flow 3 v3 §9; selection records are private at launch)
42. **Public→private unpublish** (Flow 3 v3 §9; one-way at launch)
43. **Review step on teacher publishes private→public** (Flow 3 v3 §9; direct publish at launch)
44. **Dynamic teacher capacity** tied to schedule (Flow 3 v3 §9; static at launch)
45. **Mentorship pairing** (Flow 3 v3 §9)
46. **OCR pipeline improvements** for scanned curricula (Flow 3 v3 §9)
47. **Hard delete of reference books** (Flow 1 §9; soft-delete only at launch)
48. **Fuzzy dedup of reference books** (Flow 1 §9; SHA-256 exact-match only at launch)
49. **Persona auto-switch after 10 interactions** (Flow 1 §9; manual selection at launch)
50. **Customer support / help desk integration** (Flow 1 §9)
51. **Hot/warm/cold data tiering** (Flow 1 §9 + Q4; all hot at launch)

### Phase 3+ — long-horizon items

52. **Independent teacher analytics dashboards beyond past-session history** (Flow 3 v3 §9)
53. **Independent teacher peer connections / collaboration** (Flow 3 v3 §9)
54. **Other exam frameworks** beyond Matric/O-Level launch set (Flow 4 v2 §9)
55. **Audit log UI for admins** (Flow 2 §9)
56. **Voluntary pre-graduation migration** (student-initiated school→independent before Grade 12). Flow 4 v3 §9.
57. **Visual change-set diff for framework v1 → v2.** Flow 4 v3 §9.
58. **Content Admin role for framework approval** (delegated from Platform Admin). Flow 4 v3 §9.
59. **Custom school-level exam frameworks.** Flow 4 v3 §9.
60. **Framework auto-selection by AI based on student behavior.** Flow 4 v3 §9.
61. **"Just learning" mode for independent students without framework.** Flow 4 v3 §9.
62. **ML training using post-migration independent tenant Cognitive DNA** (with consent). Flow 4 v3 Q-FB13.

---

## ENV_VARS.md additions pending

1. **`PERSONA_LEARNING_BATCH_DAYS`** — default `7`. Cadence (in days) for custom persona learning batch. Read in `infrastructure/llm/persona_learner.py`. Source: Flow 1 Q13 answer.
2. **`STRIPE_API_KEY`** — placeholder, not yet integrated. Source: Subscription Q6 deferral.
3. **`STRIPE_WEBHOOK_SECRET`** — placeholder. Source: Subscription Q6 deferral.
4. **`GRADUATION_GRACE_DAYS`** — default `180`. Read-only school window after graduation before auto-migration to independent. Source: Flow 4 v3 graduation rewrite.
5. **`FRAMEWORK_REFRESH_DAYS`** — default `90`. Cadence for `framework.refresh_quarterly` Celery beat. Source: Flow 4 v3 Q-EF6.
6. **`FRAMEWORK_RESEARCH_COST_CEILING_USD`** — default `10`. Hard cap on AI research cost per framework refresh. Source: Flow 4 v3 Q-EF9.
7. **`FRAMEWORK_APPROVAL_SLA_HOURS`** — default `72`. Target SLA for Platform Admin to approve AI-generated framework plans. Source: Flow 4 v3 Q-EF7.
8. **`AI_ADAPT_QUESTION_THRESHOLD`** — default `2`. Number of questions on same sub-topic in a session that triggers Flow 6 §3.9 per-session AI adaptation (angle switch). Read in `infrastructure/llm/session_adapter.py`. Source: Flow 6 v1 §3.9 + §8.
9. (others to add as architecture sections lock)

---

## STACK_LOCK.md confirmations pending

1. **Self-hosted TTS** confirmed (no change to existing lock — Piper + Edge-TTS + AI4Bharat). Source: Flow 1 Q8 answer.
2. **Stripe Subscriptions** confirmed in stack (no change — already locked) BUT not implemented at launch. Phase 2. Source: Q6 subscription deferral.
3. **Authentik as the single IDP** confirmed for both school and independent users (Q3 subscription discussion).
4. **Postgres dual-schema** (school + independent) confirmed as the multi-tenant strategy. Source: Q1 Option B.

---

## _TEMPLATE.md (feature-spec template) updates pending

1. **§2 Personas section** — add guidance note: "If a spec covers both school-onboarded users AND independent users, list them as separate personas with distinct lifecycles."
2. **§4 Permissions matrix** — add boilerplate header noting §6.16 permission inheritance rule.
3. **§7 Notifications** — add guidance: every template key must use one of the 7 locked namespaces (`lectures`, `self_study`, `quiz`, `connections`, `content_library`, `system`, `account`).

---

## CLAUDE.md updates pending

1. Add a single-paragraph note about tenant types: "When implementing or modifying any feature, identify whether it operates in the school tenant, independent tenant, or both. ARCHITECTURE.md §3.16 documents the dual-schema model."

---

## HAMZA_START_HERE.md updates pending

1. Add a paragraph in §3 mentioning the two tenant types and that most features need to handle both.
2. Add a reference to `_CHANGE_LEDGER.md` philosophy (but the ledger itself is deleted after batch update; only `AMENDMENTS.md` survives as the permanent record).

---

## README.md updates pending

1. Update `docs/feature-specs/` description to mention the multiple flow specs (rather than the original "one feature spec per feature" mental model).

---

## Skill file updates pending

1. **`.claude/skills/phase-complete-review/references/checklists.md`** — Checklist A: add to multi-tenancy section: "if the feature touches users, it must handle BOTH tenant types (school + independent)." Also Checklist E (RAG): mention dual-collection-namespace pattern.
2. **`.claude/skills/stack-enforcer/references/canonical_examples.md`** — add "independent user repository" canonical example (the schema-switch pattern via SQLAlchemy schema translation).
3. **`.claude/skills/frontend-master/SKILL.md`** OR **`references/notification_patterns.md` (new)** — add the notification namespace pattern (per-feature board pattern + global aggregate panel + bell icon UI).

---

## Decisions pending for future flow drafting (Flows 5-12)

These come up during Flow 5+ drafting and need to be captured here:

1. **Flow 5 — Lectures** — apply Grade-Subject offering as the lecture's parent (lecture is for a specific GradeSubjectOffering).
2. **Flow 6 — Student studies lecture** — Lecture Mode visibility scoped to student's Grade-Section enrollment.
3. **Flow 7 — Next-day review loop** — both Lecture Mode and Self-Study Mode contribute questions; both modes' AI personalization respects custom persona if active.
4. **Flow 8 — Self-Study Mode** — applies to BOTH school students (toggle to Self-Study) AND independent students (locked to Self-Study). Spec must cover both tenant types.
5. **Flow 9 — AI Intelligence Layer** — Custom Persona learning is part of this flow (per §8.16). Cognitive DNA dataflow includes diagnostic outputs from Flow 4 + interaction data from Flows 5-8.
6. **Flow 10 — Parent monitoring** — only applies to school students. Independent students no parent linking (Flow 4 Q2 decision).
7. **Flow 11 — Group study / dashboards** — Yjs CRDT for #103 group shared notes is NOT in STACK_LOCK. Flag deviation discussion needed.
8. **Flow 12 — Chatbot + VA** — Tenant-aware (works in both school and independent contexts).
9. **Flow 13 — Subscriptions (NEW thin spec)** — schema only; placeholder UI; references §3.17 + §11.18.

---

## Celery beat schedule pending (consolidated — Gap 2 fix)

To be added to ARCHITECTURE.md §10.6 (Beat schedule) and `infrastructure/celery/beat_schedule.py`:

| Task | Cadence | Owning flow | Purpose |
|---|---|---|---|
| `persona.update_custom` | Every `PERSONA_LEARNING_BATCH_DAYS` (default 7d), rolling per-student | Flow 1 §3.5 | Weekly LLM batch summarizes student-AI interactions into Custom Persona description |
| `framework.refresh_quarterly` | Every `FRAMEWORK_REFRESH_DAYS` (default 90d), per framework | Flow 4 v3 §3.5.1 | Pattern-A AI agent re-researches exam frameworks; produces new version pending Platform Admin approval |
| `graduation.migrate_eligible_students` | Daily | Flow 4 v3 §3.9 | Identifies students past `GRADUATION_GRACE_DAYS` window; fires per-student atomic migration tasks |
| `benchmark.update_weekly` | Weekly (Sunday night) | Flow 5 §3.11 | Recomputes anonymized teacher percentile rankings per (subject, grade_range, region) cohort |
| `quiz.generate_for_late_enrollment` | On-demand (NATS-triggered, not scheduled) | Flow 5 §3.3 | Auto-generates per-student quiz when a student enrolls after lecture published |
| `concept.refresh_quarterly` | Every 90d, per concept | Flow 6 §3.10 | Refreshes cached concept_applications (real-world apps + career links) |
| `flashcards.batch_notification` | Daily (nightly digest) | Flow 6 §7 | Batches "X flashcards added today" notifications instead of per-highlight pings |
| `tos.acceptance_check` | On every authenticated request (NOT scheduled; runtime check) | Flow 1 §3.6 | Validates user's accepted_tos_version against current; forces modal if outdated |
| `promotion.expire_unattended` | Daily | Flow 2 v3 §3.4 | Marks promotion requests as expired after 60d unattended; reminders at 30d |
| `stale_bulk_imports.review_sweep` | Daily (Phase 2 only) | Flow 2 v3 §9 | Lists never-logged-in students past 6 months for School Admin review |

---

## NATS event subjects pending (consolidated — Gap 3 fix)

To be added to ARCHITECTURE.md §9 (Event taxonomy):

### `student.*` family (per-student lifecycle)
- `student.onboarded`, `student.enrolled`, `student.unenrolled`
- `student.graduated`, `student.migrated_to_independent`
- `student.lecture.session_opened`, `student.lecture.session_closed`
- `student.lecture.question_asked`, `student.lecture.highlight_created`
- `student.lecture.mode_changed` (Lecture ↔ Self-Study)

### `parent.*` family
- `parent.linked`, `parent.revoked`

### `lecture.*` family (per-lecture lifecycle)
- `lecture.generation_requested`, `lecture.generation_complete`, `lecture.generation_failed`
- `lecture.version.created`, `lecture.scored`
- `lecture.published`, `lecture.linked`, `lecture.access_changed`

### `quiz.*` family
- `quiz.generated`, `quiz.regen_for_student`

### `originality.*` and `benchmark.*` families
- `originality.flagged`
- `benchmark.updated`

### `framework.*` family (Exam Framework engine)
- `framework.research_complete`, `framework.published`, `framework.deprecated`

### `curriculum.*` and `reference_book.*` families (content library)
- `curriculum.ingested`, `reference_book.ingested`

### `diagnostic.*` family
- `diagnostic.completed`

### `user.*` and `account.*` families
- `user.created`, `user.activated`, `user.suspended`, `user.reactivated`, `user.deactivated`
- `data_export.ready`, `deletion.requested`, `deletion.completed`

### `grade.*`, `section.*`, `offering.*`, `promotion.*` families (Flow 2 v3 Grade model)
- `grade.created`, `section.created`, `offering.created`, `teacher.assigned`
- `promotion.requested`, `promotion.approved`, `promotion.executed`, `promotion.failed`

### `mode.*` family (Flow 4 v3)
- `mode.changed`

**Event envelope (per §9):** every event carries `tenant_id`, `tenant_type` (school/independent), `user_id`, `session_id` (nullable), `occurred_at`, `event_type`, `payload`. Per Flow 6 v2: payload optionally includes `attached_images[]` with MinIO keys for question events.

---

## New DB tables pending (consolidated — Gap 4 fix)

To be created via Alembic migrations across two schemas (per §3.16 / §4.21). Tables grouped by owning flow.

### Flow 1 tables (platform-tier; shared via cross-schema views)
- `platform_reference_books` (Platform Library content)
- `exam_syllabi`, `syllabus_topics` (topic_tree)
- `teaching_personas` (4 named + 1 Custom slot)
- `custom_persona_profiles` (per-student Custom persona description)
- `tos_versions`, `disclaimer_versions`, `user_tos_acceptances`
- `notifications` (per-tenant with `feature_namespace` field)

### Flow 2 tables (school-tenant)
- `user_invites` (Path A admin invitation flow)
- `subjects` (school-scoped catalog)
- `grades` (Grade for academic session)
- `sections` (optional A/B/C under Grade)
- `grade_subject_offerings` (Subject offered to Grade per session, teacher assigned here)
- `class_enrollments` (student → section)
- `grade_promotion_requests` (Coordinator-initiates, School Admin-approves)
- `bulk_imports` (import job tracking)

### Flow 3 tables (school + independent)
- school: `teacher_profiles`, `teacher_grade_subject_assignments`, `school_library_content`, `teacher_content_selections`, `teacher_capacity`, `waitlist_entries`
- independent: `independent_teacher_profiles`, `independent_personal_content`

### Flow 4 tables (school + independent + platform shared)
- school: `student_profiles`, `parent_profiles`, `parent_child_links`, `exam_selections`, `mode_selections`, `diagnostic_attempts`, `data_rights_requests`, `student_framework_selections`, `graduation_migration_log`
- platform-shared: `exam_frameworks`, `framework_study_plans` (versioned), `framework_research_jobs`
- independent: `independent_student_profiles` + independent versions of data_rights_requests, diagnostic_attempts, framework_selections

### Flow 5 tables (school + independent)
- school: `lectures`, `lecture_drafts`, `lecture_versions`, `lecture_edit_sessions`, `lecture_paragraphs`, `lecture_links`, `lecture_assignments`, `lecture_voice_sessions`, `quiz_assignments`, `teacher_ai_memory`, `teacher_benchmarks`
- independent: `independent_lectures`, `independent_lecture_versions`

### Flow 6 tables (school + event store)
- school: `lecture_sessions`, `student_highlights`, `student_questions`, `student_question_conversations`, `student_flashcards`, `session_difficulty_log`, `student_simulation_progress`, `concept_applications` (cached, school-scoped), `careers` (controlled vocabulary, platform-level), `lecture_ratings`
- event store: `student_events` (partitioned monthly, 7-year retention)

### Flow 13 tables (platform-tier; mostly empty at launch)
- `subscription_tiers` (Platform Admin CRUD active)
- `subscriptions` (schema only, no rows at launch)
- `subscription_payments` (schema only, no rows at launch)

**Migration strategy:** dual Alembic heads per §4.21 — one head for `school` schema, one for `independent` schema. Platform-shared tables live in school schema with cross-schema views exposed to independent.

---

## Maintenance log

| Date | Event | Notes |
|---|---|---|
| 2026-05-14 | Ledger created and backfilled with decisions from Flows 1-4 review rounds | Backfill complete; covers ~28K tokens of conversation |
| 2026-05-14 | Flow 3 v3 + Flow 4 v2 drafted and synced to outputs | Spec files updated; ledger covers all non-spec changes pending |
| 2026-05-14 | Flow 4 v3 drafted (incorporates v3 feedback: profile mandatory trim, independent diagnostic, Exam Framework AI engine, 6-month graduation+migration) | Major additions to pending ledger: §3.19 Exam Framework engine, §8.17 quarterly refresh agent, new Celery beat tasks, new env var GRADUATION_GRACE_DAYS, new NATS events, new alumni-status concept in school dashboards |
| 2026-05-14 | Flow 5 v1 drafted (Teacher Creates a Lecture — 19 features) | Pending ledger additions: §7.13 cross-grade unidirectional retrieval weighting, env var AI_ADAPT_QUESTION_THRESHOLD (default 2 — actually Flow 6's), upload profile lecture_image (5MB JPEG/PNG/GIF), NATS events for lecture generation/versioning/scoring/originality, Celery tasks for scoring/originality/topic_relevance/tips/benchmarks, beat schedule benchmark.update_weekly + quiz.generate_for_late_enrollment, independent teacher stripped variant in §3.16 already-locked, plagiarism flag system notification |
| 2026-05-14 | Flow 6 v1 drafted (Student Studies a Lecture — 9 features including #60 NATS pipeline) | Pending ledger additions: §9.x NATS JetStream event pipeline finalization (subject pattern student.lecture.*, three-consumer fan-out), env var AI_ADAPT_QUESTION_THRESHOLD (default 2), Custom Persona + Adaptation interaction rule (persona = style, adaptation = strategy), concept_applications shared cache (school-tenant), student_events table partitioned monthly 7-year retention, hybrid voice widget #57 as canonical reusable component (frontend-master skill reference), privacy #72 inviolate (no role can override), TTS audio cache lifecycle (invalidate on lecture re-edit) |
| 2026-05-14 | Flow 1 v2 + Flow 2 v3 + Flow 13 NEW drafted | All decisions from review rounds now in permanent spec form. Flow 1 v2: Custom Persona (4 named + 1 Custom), multi-tier content library, English-only disclaimer, 7-namespace notifications, all 6 roles created from start. Flow 2 v3: Grade/Section/Subject restructure, promotion workflow with exclusion + approval, manual signup for independents only (Path B), permission inheritance matrix. Flow 13: thin subscription spec, schema-only at launch, placeholder UI, Stripe deferred. |
| 2026-05-14 | Flow 6 v2 (Awais feedback: multimodal image attachments) | New upload profile `student_question_image` in §11.17 (5MB JPEG/PNG/WEBP, EXIF stripped, MinIO scoped per-tenant, 1-year retention); vision-LLM routing in §8 (Groq Llama-3.2-Vision when `attached_images[]` present); NATS event envelope #60 includes optional `attached_images[]` field; cross-flow propagation to Flow 5 wizard chat sidebar + Flow 7 review + Flow 8 self-study widget |
| 2026-05-14 | Pre-T0 consolidation pass | Added AI_ADAPT_QUESTION_THRESHOLD env var (Gap 1); added §7.13 cross-grade RAG retrieval weighting architecture entry (Gap 5); added consolidated Celery beat schedule section with 10 tasks (Gap 2); added consolidated NATS event subjects section with ~50+ events grouped by family (Gap 3); added consolidated DB tables section with ~50+ tables grouped by owning flow + tenant (Gap 4). Ledger is now T0-ready. |
| 2026-05-14 | **=== BATCH POINT T0 — APPLIED ===** All ledger contents propagated to bootstrap files: ARCHITECTURE.md (§0.1, §3.16-3.19, §4.21-4.23, §6.19-6.23, §7.21-7.23, §8.20-8.24, §9.3 event taxonomy, §9.21-9.23, §10.6 beat schedule, §11.19-11.22 — actual numbering required renumbering existing tail subsections to accommodate aspirational ledger numbers); AMENDMENTS.md (A-001 entry); TODO.md (55+ Phase 2/3 deferrals); ENV_VARS.md (NEW file, 9 env vars); STACK_LOCK.md (4 confirmations); CLAUDE.md (tenant types paragraph + ENV_VARS.md required reads); HAMZA_START_HERE.md (§3.1 tenant types section); feature-specs/README.md (flow-based organization note); _TEMPLATE.md (tenant column in personas, inheritance header in permissions, namespace guidance in notifications); skills (frontend-master/references/hybrid_input_widget.md NEW, phase-complete-review Checklist N, stack-enforcer canonical examples extended). Spec files updated via bulk sed to match real section numbers (§6.16→§6.19, §8.16-18→§8.20-22, §9.14→§9.21, §11.17-18→§11.19-20, §7.13→§7.21). | @abdurrehman (with Claude) |
| 2026-05-20 | **Bootstrap cleanup pass (pre-M-03).** Collapsed three docker-compose files (`docker-compose.{infra,app,override}.yml`) into ONE `docker-compose.yml` at the repo root. Removed `Makefile` lock — raw `docker compose` commands are the operator interface. Collapsed split env files (`api/.env.example` + `frontend/.env.example`) into ONE `.env.example` at the repo root. Removed `docker/` subdirectory references — Dockerfiles live under `api/` and `frontend/`, observability config at top-level (`grafana/`, `prometheus/`, etc.). Updated: ARCHITECTURE.md §15.1, §15.2, §15.4, §15.16 + file tree at line 406; STACK_LOCK.md §1.4 compose layout. Rewrote `local-dev-setup.md` from scratch (390→253 lines) — now starts with "if M-00 hasn't shipped yet, there's nothing to set up; come back when `docker-compose.yml` exists at repo root." Converted `first-time-setup.md` to a deferred stub (343→53 lines) — fills in on first real VM provision post-M-23. Rewrote root `README.md` for milestone workflow + simplified Docker model. Updated `phase-complete-review/references/file_section_map.md` to drop split-file mappings. Reason: original scaffolding referenced files that didn't exist — Hamza would have hit walls on Day 1. Single-compose + no-Makefile keeps the surface area small and the failure modes obvious. | @abdurrehman (with Claude) |
| 2026-05-20 | Flow 7 v1 drafted (Next-Day Review Loop — 8 features #39,#40,#44,#45,#46,#47,#48,#49). School-tenant only. Mini-lecture = lecture_type=mini variant reusing Flow 5 pipeline; overnight aggregation 23:00 Karachi → 6am SLA; per-Grade-Subject reviews; targeted distribution; reflective prompt coaching-only (CXO lock); privacy #72 enforced. New tables lecture_reviews, review_replies, review_classification_failures; lectures gains lecture_type + parent_lecture_id. | @abdurrehman (with Claude) |
| 2026-05-20 | Flow 8 v1 drafted (Student Self-Study Mode — 10 features #62,#63,#64,#65,#66,#67,#68,#69,#70,#72). FIRST genuinely dual-tenant core flow (school toggle-in + independent locked-in). Owns canonical privacy #72. Corrects v2 doc external-service errors against STACK_LOCK: PaddleOCR not Google Vision, Jazz/Telenor not Twilio, Brevo not SendGrid, FullCalendar built-in, py-fsrs deck (scheduling deferred to Flow 9). New tables student_materials, student_goals, prep_book_topics, study_plans, study_plan_items, study_plan_days, reminder_preferences. New beat tasks check_adherence/refine_granularity/send_session_reminders. Flagged open Q: Google Calendar API vs STACK_LOCK no-GCP line (needs Abd. ruling). | @abdurrehman (with Claude) |
| 2026-05-20 | ARCH §3.18 stale-ref fix (§6.16→§6.19, §7.13→§7.21 — leftovers from T0 renumbering). M-03 backlog drafted (Subjects + Grade/Section/Subject offerings — 12 tickets T-041..T-052, source Flow 2 v3 §3.2-§3.3). Covers Subject catalog, Academic Session, Grade, Section (optional + default-internal), GradeSubjectOffering, Teacher assignment with capacity (cap 5, override audit), cross-grade unidirectional guard, scope/inheritance enforcement, notifications, audit, E2E, milestone PR. Student enrollment deferred to M-06; promotion to M-22. ROADMAP M-03 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | M-04 backlog drafted (Teacher Onboarding + school-tier Content Library — 16 tickets T-053..T-068, source Flow 3 v3 #11/#16/#17/#18, school tier only). Covers school teacher onboarding + READY_TO_TEACH derivation, content library data model, school_library_content upload + per-school dedup, RAG ingestion Pattern S (parse→chunk→embed→Qdrant), curriculum structured topic_tree parsing, curriculum upload (always public) + reference book upload (privacy toggle default private, private→public one-way), library browse/search/tag-filter, ingestion status/retry, teacher self-edit capacity, cross-grade visibility (reuses T-047 guard), soft-delete with citation retention, content_library notifications, audit, E2E, milestone PR. Independent teacher onboarding + Platform Library deferred to M-05; lecture creation to M-09+. ROADMAP M-04 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | M-05 backlog drafted (Independent Users signup + Platform Library — 8 tickets T-069..T-076, source Flow 3 v3 §3.2 + Flow 4 v3 §3.2 + Flow 1 Platform Library). Covers independent signup path (Authentik group + tenant_type JWT + schema routing), independent teacher onboarding (READY_TO_USE), independent student onboarding (exam framework REQUIRED + exam date, diagnostic deferred to M-08), Platform Library upload (platform_reference_book global dedup) reusing M-04 ingestion, Platform Library read-only access for all tenants + cross-schema views, independent private pool (always private), E2E (schema isolation asserted), milestone PR. Diagnostic execution → M-08; self-study/study-plans → M-08+; lecture creation → M-09+. ROADMAP M-05 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | M-06 backlog drafted (School Student Onboarding + Parent Linking — 14 tickets T-077..T-090, source Flow 4 v3 §3.1/§3.3/§3.7/§3.8/§3.9). Covers school student data model + Coordinator enrollment into Grade-Section, student onboarding (trimmed mandatory fields, mode pick, READY_TO_STUDY), bulk CSV enrollment (implements M-02 T-039 skeleton), parent registration, parent→student link request + student approval (§6.13 consent), revocation + multi-parent/child, exam date capture (#52), data rights (#15 export/delete), graduation 6-month school-read-only window, atomic auto-migration to independent tenant (Celery beat + 5x retry + parent sever + alumni retention), notifications, audit, E2E, PR. Exam Framework engine → M-07; diagnostic + full Mode Switcher → M-08; lecture creation → M-09+; parent monitoring → Flow 10. Highest-risk ticket T-086 (atomic migration). ROADMAP M-06 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | ARCH §3.19 stale-ref fix (§8.17→§8.21, T0 renumber leftover). M-07 backlog drafted (Exam Framework Engine, platform tier — 10 tickets T-091..T-100, source Flow 4 v3 §3.5 + ARCH §3.19/§8.21). Covers framework data model (platform-shared, cross-schema views), Platform Admin DRAFT CRUD, Pattern-A AI research agent (SearXNG→web_fetch→LLM synthesis→JSONB study plan, cost ceiling), manual approval workflow (72hr SLA + escalation), versioning + quarterly refresh (Celery beat framework.refresh_quarterly) + deprecation, student selection + study-plan rendering + region scoping + self-study hook, notifications, audit, E2E, PR. Lecture Mode overlay UI deferred to M-09+ (hook only); diagnostic → M-08; study-plan execution → Flow 8/M-08+. Heaviest ticket T-093 (first real Pattern-A agentic run). ROADMAP M-07 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | M-08 backlog drafted (Student Mode + Diagnostic + Cognitive DNA SEED — 12 tickets T-101..T-112, source Flow 4 v3 §3.4/§3.6/§3.7). Covers full Mode Switcher (school toggle, independent locked 404), provisional cognitive_dna seed store (per-tenant), diagnostic data model + lifecycle (save/resume 7d, 30d cooldown), LLM diagnostic question generation (per-subject school / per-framework independent; Question Bank #74 deferred hook), diagnostic UI with coaching-only results (never grades), diagnostic→DNA seeding, exam-date countdown (#52), mode-conditional dashboard + adaptation read-hook, notifications, audit, E2E, PR. CAUTION flagged: full Cognitive DNA engine (mistake tracking, pass prob, spaced rep, forgetting curve, Question Bank) is Flow 9/M-18 (BLOCKED, not drafted); M-08 builds seed only; soft dependency noted — DNA schema provisional, may need follow-up migration when Flow 9 drafted. ROADMAP M-08 status → drafted. | @abdurrehman (with Claude) |
| 2026-05-20 | M-09 backlog drafted (Lecture Wizard + AI Generation, Pattern S RAG — 16 tickets T-113..T-128, source Flow 5 v1 §3.1/§3.2/§3.4/§3.13/§3.14/§3.15/§3.16). Covers lecture data model (lectures/versions/drafts/paragraphs; lecture_type+parent_lecture_id Flow7-ready), 5-step wizard (topic from curriculum tree, curriculum confirm, reference selection w/ cross-grade toggle, teaching mode, confirm+estimate, draft auto-save), Pattern S dual-RAG generation (curriculum 1.5x weight, structure vs depth), WebSocket streaming + reconnect, per-paragraph source badges (#26), out-of-curriculum fallback tiers (#27 ref→SearXNG→no-info), exam framework overlay context, voice creation STS loop (#25 faster-whisper/Piper/Edge/AI4Bharat + OT draft edits), cross-grade lecture linking (#21 reuses T-047), per-lecture access (#21), delivery tips/technique/real-world (#28/#41), independent stripped variant (own refs, no auto-quiz), notifications+audit, E2E, PR. Edit+versions+scoring → M-10; auto-quiz+publish → M-11. Also: unblocked M-16 (Flow 7 drafted) + M-17 (Flow 8 drafted) in ROADMAP. ROADMAP M-09 status → drafted. | @abdurrehman (with Claude) |
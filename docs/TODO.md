# TODO.md — Deferred Work

**Status:** Living document
**Owner:** @abdurrehman-tahir
**Purpose:** Single place to track decisions and features we deliberately deferred from v2 launch. Reviewed at end of each phase to decide what's pulled forward.

Each entry:
- States what was deferred
- Why it was deferred (resource, risk, complexity, scope)
- What triggers revisiting it
- Where the original decision was made (so we can trace context)

---

## Infrastructure & Ops

### Self-hosted Sentry
- **Deferred from:** ARCHITECTURE.md §1.3 (container inventory)
- **Why:** Sentry self-hosted is 8+ containers on its own. Heavyweight to run on a single VM at launch. We have Loki (logs) + Prometheus (metrics) + Grafana (dashboards) which cover the same ground for v2.
- **Trigger to revisit:** When error volume exceeds ~50/day and Loki search becomes painful, OR when we hire a dedicated DevOps person, OR Phase 2 budget allows a dedicated observability VM.
- **Status:** Not started

### Backup strategy
- **Deferred from:** ARCHITECTURE.md §1 (deferred to later)
- **Why:** Skipped at launch per Abd. — accepting single-Postgres single-VM risk.
- **What it covers when revisited:** Postgres `pg_dump` schedule, Qdrant snapshots, MinIO mirroring, offsite copy, restore drill SOP, RPO/RTO targets.
- **Trigger to revisit:** Before first paid customer, OR before first production deployment with real student data, whichever comes first. This is a launch blocker for any real user data.
- **Status:** Not started — **flagged as Phase-2 launch blocker**

### Postgres hot standby / replication
- **Deferred from:** ARCHITECTURE.md §1.7
- **Why:** Single VM at launch — adding a replica on the same VM gives no real disaster resilience.
- **Trigger to revisit:** When a second VM is provisioned, or when uptime requirements tighten.
- **Status:** Not started

### Multi-region deployment
- **Deferred from:** ARCHITECTURE.md §1.6
- **Why:** Single region (Pakistan), single VM at launch. No business case for multi-region until international expansion.
- **Trigger to revisit:** International users, or Pakistan-wide outage history demands it.
- **Status:** Not started

---

## Backend / API

### Auto-generated TypeScript types from Pydantic models
- **Deferred from:** ARCHITECTURE.md §2.2
- **Why:** Manual typing in `frontend/src/types/api.ts` is fine for launch scope. Auto-gen adds tooling complexity (datamodel-code-generator or openapi-typescript) and a CI step.
- **Trigger to revisit:** When manual sync becomes a recurring bug source, or when we have >100 API endpoints.
- **Status:** Not started

---

## Machine Learning

### Trained ML models (vs heuristics)
- **Deferred from:** STACK_LOCK.md §4.5
- **Why:** No historical student outcome data at launch — nothing to train on. Heuristic formulas with identical API contract live in `services/ml/heuristic/`. Swap to trained models is zero-caller-change.
- **Trigger to revisit:** After 6 months of production usage with collected student outcomes (≥1000 students with completed exams).
- **What it covers:** XGBoost training pipeline for pass probability, predicted marks, guess detection. SHAP for causal topic analysis. Nightly retraining via Celery beat. Models stored in MinIO bucket `ml-models/`.
- **Status:** Heuristic stubs at launch (see STACK_LOCK §4.5 TODO list); training infrastructure scaffolded but inactive.

---

## Frontend

### Design pass on existing frontend (post design-system)
- **Deferred from:** Pre-launch operating decision (no designer available; vertical-slice build)
- **Why:** We're building vertical slices (backend + frontend per feature) before the design system / template selection happens. Frontend built before the design system lands will use shadcn defaults — functional and accessible, but visually generic. The polish pass happens after the design system PR lands.
- **What it covers:** revisit shipped pages with the design tokens, component library extensions, brand assets, and any layout refinements that the design system introduces. Not a rewrite — a styling/polish overlay.
- **Trigger to revisit:** When the design system PR is merged (target: before first government school onboarding).
- **Status:** Not started

---

## Product / Features

### (added as we hit them)

### Spec-set Phase 2+ deferrals (T0 batch, 2026-05-14)

The following items are deferred from launch per Flows 1-6 + Flow 13 spec set. Grouped by feature area.

#### Subscription module (Flow 13 — full implementation)
- Stripe integration; payment processing; cap enforcement; recurring billing; invoice generation; refund processing; webhook handling per ARCH §11.20; customer portal; tax handling; multi-currency (USD beyond PKR); per-seat pricing; subscription downgrades + prorated refunds; independent user paid tiers; manual invoicing for enterprise; annual prepayment / discounts; free trial periods; promotional pricing / coupon codes; cross-district subscription transfers.
- **Trigger:** post-pilot success (3-6 months post-launch); commercial rollout phase.

#### Custom Persona (ARCH §8.20)
- Per-school custom persona / prompt overrides (Phase 2+).
- Custom persona auto-switching after N interactions (alternative to manual selection).
- Cross-tenant aggregated persona insights (e.g., "most students of subject X prefer storyteller persona") — Phase 3+.
- Independent teacher Innovation Record (Flow 5 §3.16 deferred for independents at launch).

#### Exam Framework engine (ARCH §3.19 + §8.21)
- Region-specific syllabus variants beyond launch set (Sindh Board, KP Board, etc.) — on-demand expansion.
- AI agent fine-tuning on Pakistani exam patterns (Phase 2 if quality issues surface).
- Student-side custom framework selection (e.g., "I'm preparing for a private exam not in the catalog") — Phase 3.
- Framework comparison view ("show me Matric Punjab vs FSc Punjab side by side") — Phase 3.

#### Content Library (Flow 1 §3.3 + Flow 3 v3)
- Hard-delete of library content (soft-delete only at launch).
- Fuzzy dedup (cross-version dedup beyond SHA-256 exact-match).
- Cross-tier library dedup (Platform Library + School Library uploading same PDF).
- Public → Private "un-publish" for references (one-way at launch).
- Cross-school library sharing (Phase 2 if pilot demands).
- Per-school storage quotas — Phase 2; admin dashboard work.
- Content-aware deduplication (semantic, not just SHA) — Phase 3+.
- File preview generation (thumbnails for PDFs, audio waveforms) — Phase 2.

#### Grade / Section / Subject + Promotion (Flow 2 v3)
- Bulk-promote-all grades (per-grade only at launch).
- CSV import for exclusion list (manual checkboxes only at launch).
- Per-Section teacher assignment (Teacher assigned at GradeSubjectOffering level at launch).
- Bulk teacher import (individual invites only at launch).
- Self-service school registration (manual Platform Admin onboarding at launch).
- Co-teaching (multiple teachers per offering — one primary at launch).
- Automatic class roll-over (manual + approval-driven at launch).
- Cross-district student transfer (deactivate + recreate at launch).
- Promotion approval delegation by School Admin to a deputy.
- Section richer attributes (capacity, schedule).
- Promotion preview before submission.
- Stale bulk-imported student cleanup.
- Audit log queryable UI (last-50 only at launch).

#### Independent users (ARCH §3.16)
- Independent user parent linking (independent students don't link to parents at launch).
- Independent teacher Innovation Record (Phase 2).
- Independent teacher cross-tenant originality check (own tenant only at launch — privacy/legal complexity).

#### Lecture creation (Flow 5)
- Co-authored lectures (single-author at launch).
- Lecture templates (each lecture starts fresh).
- AI auto-generation triggered by student questions (Phase 5).
- Lecture analytics deep-dive (engagement heatmaps, drop-off points).
- Multilingual lecture mixing (single language per lecture at launch).
- Lecture-to-podcast export (audio version with TTS).
- GPU-accelerated voice path for sub-1s STS (Phase 2 if measurement justifies).
- AI diagram generation (creating new diagrams vs. flagging existing ones).
- Lecture peer-review by other teachers.
- Faster-whisper accent / multilingual fine-tuning.
- Lecture export to LMS (SCORM, Common Cartridge).
- Real-time collaborative editing for multiple admins simultaneously.

#### Lecture consumption (Flow 6)
- Real-time collaboration in lecture viewer (single-user view at launch).
- Lecture annotations / notes (highlights only).
- Word-level karaoke sync for #54 (sentence-level at launch).
- Custom voice / voice cloning for TTS.
- In-lecture quiz embeds (separate via #23b).
- Multimodal questions with non-image attachments (PDFs, slides) — image-only at launch.
- Lecture bookmarking (implicit only at launch).
- Sharing highlights with peers (private at launch).
- Career taxonomy expansion beyond Pakistani options.
- Mini-simulation save state across devices (single-device save at launch).
- AI-suggested questions ("students who studied this also asked...").
- Smart-flashcard filtering (only valuable highlights become flashcards — all at launch).
- Office hours scheduling (Phase 2 trigger after #61 angle exhaustion).
- Question rating by student ("was this answer helpful?").

#### Multilingual / i18n
- Disclaimer translations to ur/sd/ps (English-only at launch; blocks Phase 6 predictions).
- TMS integration (Crowdin/Lokalise/Weblate) — manual JSON at launch.
- URL-prefixed locales (`/en/...`, `/ur/...`) — cookie + user pref only at launch.
- Per-channel language preferences (UI in en, AI in ur) — one per user at launch.
- Eastern Arabic digit display preference.
- Hijri calendar (Gregorian only at launch).

#### Data archival + audit
- Hot/warm/cold data tiering (all hot at launch).
- Audit log queryable UI for admins (logs written; UI Phase 2).

#### Pre-launch
- Full legal review of ToS (basic industry-standard ToS at launch).
- Customer support / help desk integration.

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial file. Sentry + backup strategy + Postgres replication + multi-region + auto-gen TS types + trained ML logged. | @abdurrehman (with Claude) |
| 2026-05-14 | T0 batch: added 55+ spec-set deferrals (Flow 13 subscriptions full implementation, Custom Persona Phase 2+, Exam Framework expansion, Content Library Phase 2 features, Promotion workflow extensions, Independent user Phase 2, Lecture creation deferrals, Lecture consumption deferrals, i18n Phase 2, archival Phase 2, pre-launch legal review). | @abdurrehman (with Claude) |

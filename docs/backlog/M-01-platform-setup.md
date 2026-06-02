# M-01 — Platform Setup: Platform Admin + Languages + ToS + Personas + Exam Syllabi

**Status:** todo
**Estimated duration:** 2-3 weeks
**Tickets:** T-016 through T-027
**Spec source:** `flow-1-platform-setup.md` v2

## Goal

The first user-facing milestone. Platform Admin can log in via Authentik, accept ToS, configure base platform data (languages, exam syllabi, teaching personas), and CRUD subscription tier definitions. By milestone end, the IqbalAI platform is configured and ready to receive its first school.

**Demo at milestone end:**
- Platform Admin logs in via Authentik
- Sees + accepts ToS modal (English)
- Lands on Platform Admin dashboard
- Configures 4 launch languages
- Creates exam syllabi for Matric Punjab + FSc Punjab + O-Level Cambridge + A-Level Cambridge
- Configures 4 named teaching personas + Custom slot
- Creates 1-2 subscription tier definitions (placeholder, no Stripe)
- Disclaimer text published

---

## T-016 — Platform Admin bootstrap: first admin account from Authentik + ToS acceptance

**Layer:** 1
**Milestone:** M-01
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.1 (role hierarchy bootstrap — first Platform Admin)
- `flow-1-platform-setup.md` §3.6 (Disclaimer / ToS lifecycle)
- `flow-1-platform-setup.md` §5.1 (last Platform Admin self-demotion blocked)
- `flow-2-admin-coordinator-setup.md` §3.1 Path A (admin invitation)

### ARCH source
- `ARCHITECTURE.md` §6.2 (Role matrix; canonical 6-role list)
- `ARCHITECTURE.md` §6.6 (AuthMiddleware)
- `ARCHITECTURE.md` §6.19 (Permission inheritance)
- `ARCHITECTURE.md` §14.10 (Audit log — first admin creation)

### Depends on
- T-006 (FastAPI), T-007 (User table), T-008 (require_role), T-004 (Authentik)

### What this ticket builds

**Backend:** Bootstrap script creates first Platform Admin in Authentik (manual one-time, not API-driven for security). Endpoint `POST /api/v1/auth/post-login`: on first login, creates User record in `school.users` table with `role=platform_admin`, audit-logs creation. `GET /api/v1/tos/current` returns current ToS version. `POST /api/v1/users/me/accept-tos` records acceptance. Block any state-changing endpoint if user hasn't accepted current ToS (middleware check).

**Frontend:** Login flow page redirects via OIDC to Authentik. On callback: if first login → show ToS acceptance modal (full text scrollable, accept button at end). After acceptance → land on `/admin` dashboard (empty for now). Disclaimer link in footer.

### Acceptance (demo script)

1. [ ] Bootstrap script creates Platform Admin in Authentik
2. [ ] Visit `localhost:3000/login` → Authentik OIDC redirect
3. [ ] After login: first-login flow shows ToS modal in English
4. [ ] Decline → logged out
5. [ ] Accept → User row created in `school.users`, `user_tos_acceptances` row, audit log entry
6. [ ] Subsequent login: no ToS modal (already accepted)
7. [ ] If ToS version bumps later (T-019): force modal on next request
8. [ ] Last Platform Admin attempting self-deactivate → `PRECONDITION_FAILED`

### Out of scope

- ToS authoring UI — admin uses placeholder English text from a config file at launch (T-019 adds editor)
- Disclaimer text editor — T-019
- Multi-language ToS — TODO per Flow 1 §9

---

## T-017 — Platform Admin dashboard shell + navigation

**Layer:** 1
**Milestone:** M-01
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §2 (Platform Admin persona)
- `flow-1-platform-setup.md` §4 permissions matrix

### ARCH source
- `ARCHITECTURE.md` §12.1-§12.5 (Frontend architecture, layouts)
- `frontend-master/SKILL.md` (component patterns)
- `frontend-master/references/four_ui_states.md`

### Depends on
- T-016 (Platform Admin can log in)

### What this ticket builds

**Frontend:** `/admin` route layout with sidebar navigation. Empty pages for: Languages, Personas, Exam Syllabi, Subscription Tiers, ToS/Disclaimer, Audit Log. Header with user name + logout. Per `frontend-master`: four UI states pattern, i18n keys, responsive (mobile + desktop), RTL-safe.

**No new backend.** Pure UI scaffolding.

### Acceptance (demo script)

1. [ ] After login lands on `/admin` dashboard with sidebar
2. [ ] All 6 nav items render (Languages, Personas, Exam Syllabi, Subscription Tiers, ToS/Disclaimer, Audit Log)
3. [ ] Each section opens to a placeholder empty state ("Configuration not yet added")
4. [ ] Logout button works
5. [ ] Language switcher in header rotates through 4 languages; RTL layout works
6. [ ] Mobile responsive — sidebar collapses

### Out of scope

- Actual content for each page (T-018 to T-026)

---

## T-018 — Languages: list + (no admin UI, deployment-level per Flow 1 §3.2)

**Layer:** 1
**Milestone:** M-01
**Estimate:** 1 day
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.2 (multilingual support; 4 languages at launch; new language is deployment-level)

### ARCH source
- `ARCHITECTURE.md` §13 (i18n)

### Depends on
- T-017 (dashboard)

### What this ticket builds

**Backend:** No API. Languages are config-driven, loaded at deployment from `infrastructure/i18n/locales.yaml` listing 4 launch languages.

**Frontend:** `/admin/languages` page shows the 4 locked languages (en, ur, sd, ps) as read-only cards. Each card shows: native name, RTL status, TTS support status (placeholder until M-12 voice infra). Banner: "Adding a new language requires a deployment-level change. Contact Hamza for support."

### Acceptance (demo script)

1. [ ] `/admin/languages` shows 4 language cards
2. [ ] Each card displays in its own language (en in English, ur in Urdu, etc.)
3. [ ] RTL languages render correctly
4. [ ] No edit/delete/add controls visible
5. [ ] Banner explains deployment-level workflow

### Out of scope

- Self-service language addition — permanent out-of-scope per Flow 1 §9
- Per-channel language preferences — Phase 2 per TODO.md

---

## T-019 — ToS + Disclaimer: version table + admin editor + force-accept flow

**Layer:** 1
**Milestone:** M-01
**Estimate:** 3 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.6 (Disclaimer / ToS lifecycle)
- `flow-1-platform-setup.md` §5.6 (edge cases — user mid-session when new ToS publishes; user refuses new ToS → suspended)
- `flow-1-platform-setup.md` §6 (limits — disclaimer 500 chars)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log — every publish)

### Depends on
- T-016 (ToS infra), T-017 (dashboard)

### What this ticket builds

**Backend:** Migration adds `tos_versions` and `disclaimer_versions` tables (in school schema, but accessed by both tenants via cross-schema views per §3.16). Endpoints: `GET/POST /api/v1/admin/tos`, `GET/POST /api/v1/admin/disclaimer`. POST creates new version (immutable), publishes effective_at. `tos.acceptance_check` runtime check per §10.6 — middleware validates user's `accepted_tos_version` against current; outdated → block + force modal.

**Frontend:** `/admin/tos` page: textarea for ToS markdown editing, version history list, publish button (creates v(n+1)). Same for `/admin/disclaimer` with 500-char limit. English-only at launch with `__TODO__` markers for ur/sd/ps placeholders.

### Acceptance (demo script)

1. [ ] Platform Admin opens `/admin/tos`, sees current version (v1 from initial bootstrap)
2. [ ] Edits + publishes v2 → new row in `tos_versions`, audit log entry
3. [ ] All other admins (when they exist) get forced ToS modal on next state-changing request
4. [ ] Accept v2 → can continue
5. [ ] Decline → account suspended (`SUSPENDED` state per Flow 2 §3.5)
6. [ ] Disclaimer: similar flow, 500-char enforcement
7. [ ] Disclaimer renders inline next to prediction surfaces (test: dummy prediction component shows it)
8. [ ] Audit log row for every publish

### Out of scope

- Multi-language ToS — TODO per Flow 1 §9
- Legal review — pre-pilot TODO

---

## T-020 — Exam syllabi: data model + CRUD endpoints

**Layer:** 1
**Milestone:** M-01
**Estimate:** 3 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.4 (exam syllabi lifecycle)
- `flow-1-platform-setup.md` §5.4 (edge cases)
- `flow-1-platform-setup.md` §6 (limits — depth 4, initial launch set)

### ARCH source
- `ARCHITECTURE.md` §3.19 (Exam Framework engine — syllabi are INPUT to this engine)
- `ARCHITECTURE.md` §4.2-§4.8 (DB patterns)

### Depends on
- T-007 (DB mixins), T-017 (dashboard)

### What this ticket builds

**Backend:** Migration adds `exam_syllabi` + `syllabus_topics` tables (school schema, cross-schema views for independent). Endpoints: `POST/GET/PUT/DELETE /api/v1/admin/exam-syllabi` and nested `/topics`. Hierarchy depth limited to 4. Soft-delete blocked if students have selections (per §5.4). Versioning: editing creates v(n+1); old version retained for pinned students.

**Frontend:** `/admin/exam-syllabi` page: tree view of syllabi → levels → subjects → topics. CRUD operations with confirmation modals.

### Acceptance (demo script)

1. [ ] Platform Admin creates "Matric Punjab Board" syllabus with 3 levels (Class 9, Class 10)
2. [ ] Adds subjects: Physics, Chemistry, Math, Biology, English, Urdu, etc.
3. [ ] Adds topics under each subject (depth 1-4 tested)
4. [ ] Editing creates v2; old v1 retained for any future student pinning
5. [ ] Deletion of topic with student progress (if any) → `PRECONDITION_FAILED`
6. [ ] All 4 launch syllabi (Matric Punjab, FSc Punjab, O-Level Cambridge, A-Level Cambridge) created
7. [ ] Audit log for every change

### Out of scope

- Framework engine itself (M-07)
- Student framework selection (M-08)
- Region-specific syllabus variants beyond launch set — Phase 2 per TODO

---

## T-021 — Teaching personas: data model + 4 named + 1 Custom slot + admin editor

**Layer:** 1
**Milestone:** M-01
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.5 (teaching personas — 4 named + 1 Custom slot)
- `flow-1-platform-setup.md` §5.5 (edge cases — persona prompt edited mid-session)
- `flow-1-platform-setup.md` §6 (limits — system prompt 8000 chars; Custom desc 2000 chars)

### ARCH source
- `ARCHITECTURE.md` §8.20 (Custom Persona learning batch — schema reference)

### Depends on
- T-017 (dashboard)

### What this ticket builds

**Backend:** Migration adds `teaching_personas` table. Seed 4 named personas at launch (Strict, Friendly Tutor, Storyteller, Exam Coach) + 1 Custom row (single row, `is_custom=true`). Endpoints: `GET/PUT /api/v1/admin/personas/:id`. Editing locked: changes apply to NEW sessions only (no migration of in-flight sessions).

**Frontend:** `/admin/personas` page: 5 persona cards. Click → edit system prompt textarea (8000 char limit). Custom persona card shows: "This is the slot where students opt-in for per-student LLM-learned persona. Configured automatically via weekly batch (per ARCH §8.20)." Read-only for system prompt; only metadata editable.

### Acceptance (demo script)

1. [ ] 4 named personas seeded with default English system prompts
2. [ ] Custom persona slot exists, marked `is_custom=true`
3. [ ] Editing persona prompt → new sessions use new; cached sessions use old
4. [ ] System prompts editable in all 4 languages (i18n stored per-locale)
5. [ ] Deactivating persona blocks new student selections; existing users unaffected

### Out of scope

- `persona.update_custom` Celery beat task — added when Custom selections exist (M-08 student onboarding)
- `custom_persona_profiles` table — comes with the beat task

---

## T-022 — Subscription tiers: schema-only + Platform Admin CRUD (placeholder)

**Layer:** 1
**Milestone:** M-01
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-13-subscriptions.md` (v1 — thin spec; schema-only at launch)
- `flow-1-platform-setup.md` §3.9 (subscription tier cross-ref)

### ARCH source
- `ARCHITECTURE.md` §3.17 (subscription cross-cutting attribute, schema-only)
- `ARCHITECTURE.md` §11.20 (Stripe webhook flow placeholder)

### Depends on
- T-017 (dashboard)

### What this ticket builds

**Backend:** Migration adds `subscription_tiers`, `subscriptions` (empty at launch), `subscription_payments` (empty) tables. `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET` env vars exist as placeholders (empty values OK). No Stripe SDK installed. Endpoints: `GET/POST/PUT/DELETE /api/v1/admin/subscription-tiers`. Validation: name + caps JSONB + pricing_monthly_pkr + applies_to_role.

**Frontend:** `/admin/subscription-tiers` page: tier list, CRUD modals. Caps as JSON editor (allows free-form keys). Banner: "Subscription module is schema-only at launch. Full implementation in Phase 2."

### Acceptance (demo script)

1. [ ] Platform Admin creates 2 tier definitions (e.g., "Basic District" + "Premium School")
2. [ ] Tier rows exist in DB; `subscriptions` table remains empty
3. [ ] No Stripe imports in code (grep verifies)
4. [ ] District / School subscribe button (placeholder in M-02) shows "Coming soon" modal
5. [ ] Audit log per tier create/edit/deprecate

### Out of scope

- Stripe integration — Phase 2 per Flow 13 + TODO.md
- District/School subscribe flow — placeholder in later milestones

---

## T-023 — Notifications: schema + 7 namespaces + UI shell

**Layer:** 1
**Milestone:** M-01
**Estimate:** 3 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.7 (notification system — 7 namespaces, two-tier UI)
- `flow-1-platform-setup.md` §5.7 (edge cases — high volume, real-time push failure)
- `flow-1-platform-setup.md` §6 (limits — 90-day inbox, 99+ cap, 10/min/user push)

### ARCH source
- `ARCHITECTURE.md` §9.12 (Redis pub/sub for real-time UI push)
- `ARCHITECTURE.md` §9.21 (Notification namespaces — 7 LOCKED)
- `ARCHITECTURE.md` §10.6 (Beat: `notifications.flush_queue` every 15 min)

### Depends on
- T-007 (DB), T-009 (frontend), T-011 (Celery), T-012 (NATS)

### What this ticket builds

**Backend:** Migration adds `notifications` table per ARCH §9.21 schema with `feature_namespace` enum (7 values locked). `infrastructure/notifications/`: `publish.py` (writes to table + emits Redis pub/sub for live push), `templates/` (template registry, i18n-keyed). `notifications.flush_queue` Celery beat (15 min, sends queued out-of-band channels like push/email). FCM client stub (real push setup deferred to Phase 2). Endpoints: `GET /api/v1/notifications` (paginated), `POST /api/v1/notifications/:id/read`.

**Frontend:** Global notification bell in header (shows total unread, max "99+"). Click → panel with aggregated counts per namespace. Per-feature bell icons defined as pattern (added per feature in later milestones). Real-time updates via WebSocket subscription. Notifications cannot be turned off (no opt-out UI per Q13).

### Acceptance (demo script)

1. [ ] Platform Admin sees notification bell in header
2. [ ] Sample `system.platform_library_reference_added` notification fired → appears live in bell
3. [ ] Click bell → panel groups by namespace ("3 new in system")
4. [ ] Click namespace → opens that feature's notification board (placeholder list)
5. [ ] Click notification → marks as read
6. [ ] 90-day retention enforced (Celery task)
7. [ ] All 4 languages: notification body translated correctly
8. [ ] Audit log retention 7 years per §14.10

### Out of scope

- Per-feature notification boards inside features — added per feature in later milestones
- FCM push integration — placeholder; full setup Phase 2
- Email notification channel — Phase 2 (only in-app at launch)

---

## T-024 — Content Library: data model for Platform Library (Platform Admin uploads)

**Layer:** 1
**Milestone:** M-01
**Estimate:** 3 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §3.3 (Content Library architecture — multi-tier; Platform Library tier)
- `flow-1-platform-setup.md` §5.3 (edge cases — tag mismatch, SHA dedup, soft-delete with citations)
- `flow-1-platform-setup.md` §6 (limits — 100 MB, PDF only, OCR cost ceiling $5)

### ARCH source
- `ARCHITECTURE.md` §11.19 (Upload profiles — `platform_reference_book` profile)
- `ARCHITECTURE.md` §11.2-§11.10 (Upload pipeline)
- `ARCHITECTURE.md` §7.6 (Qdrant collection schema)
- `ARCHITECTURE.md` §7.10 (ingestion pipeline)

### Depends on
- T-013 (upload pipeline), T-010 (RAG infra)

### What this ticket builds

**Backend:** Add `platform_reference_book` to upload profiles registry per ARCH §11.19. Migration creates `platform_reference_books` table (in school schema; cross-schema view exposes to independent tenant read-only). Ingestion pipeline: PDF → PyMuPDF text extraction → chunking → BGE-M3 embeddings → Qdrant collection. Tags: subject_id, grade_range[], language, content_type=curriculum|reference. SHA-256 dedup global. Soft-delete preserves embeddings per §5.3.

**Frontend:** `/admin/library` page: upload form, tag selectors, file list with status (ingesting/available/failed). Soft-delete button.

### Acceptance (demo script)

1. [ ] Platform Admin uploads sample.pdf with tags (Physics, Grade 9, en, curriculum)
2. [ ] Upload returns 202 + tracking URL; ingestion task fires
3. [ ] After ingestion: appears in library list with status "available"
4. [ ] Chunks visible in Qdrant `platform_chunks` collection with correct payload
5. [ ] Re-upload same PDF → dedup hits, returns existing entry
6. [ ] Soft-delete: hides from default list; embeddings retained
7. [ ] Failed ingestion (e.g., corrupt PDF): status `ingestion_failed`, admin notified per `system.platform_library_ingest_failed`

### Out of scope

- School Library tier (M-04 Teacher Onboarding)
- Student personal pool (M-08 Self-Study)
- Independent personal pool (M-05)
- OCR pipeline for image-only PDFs — deferred unless launch demo requires; default text extraction only

---

## T-025 — Audit log: schema + write helper + admin viewer (last 50)

**Layer:** 1
**Milestone:** M-01
**Estimate:** 2 days
**Status:** done

### Spec source
- `flow-1-platform-setup.md` §10 (audit log retention 7 years)
- `flow-2-admin-coordinator-setup.md` §9 (audit log queryable for School Admin — last 50)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log spec)

### Depends on
- T-007 (DB), T-017 (dashboard)

### What this ticket builds

**Backend:** Migration creates `audit_log` table per ARCH §14.10. Helper `infrastructure/audit/log.py` with `audit(action, actor_id, target_type, target_id, metadata)`. Every write endpoint added in T-016 to T-024 instrumented to call audit helper. 7-year retention via Celery beat (later — for now just write, no purge).

**Frontend:** `/admin/audit-log` page: paginated table of last 50 entries (per Flow 2 v3 §9 — full queryable UI Phase 2). Filters by actor, target, action type.

### Acceptance (demo script)

1. [ ] Every action from T-016 to T-024 emits an audit row
2. [ ] Audit log page shows last 50 with most recent first
3. [ ] Filter by actor returns subset correctly
4. [ ] Audit row immutable (no UPDATE / DELETE allowed at DB level)
5. [ ] 7-year retention noted in TODO for Phase 2 purge

### Out of scope

- Full queryable UI — Phase 2 per TODO
- Audit log retention purge — Phase 2

---

## T-026 — Smoke test end-to-end: Platform Admin onboards, configures everything

**Layer:** 1
**Milestone:** M-01
**Estimate:** 1 day
**Status:** done — spec written at frontend/e2e/platform-admin-smoke.spec.ts; requires @playwright/test installation (not yet in STACK_LOCK)

### Spec source
- `flow-1-platform-setup.md` §11 (acceptance criteria)

### ARCH source
- N/A (test ticket)

### Depends on
- T-016 through T-025 all done

### What this ticket builds

E2E Playwright test: Platform Admin logs in fresh → accepts ToS → goes through every config page → creates initial data (4 syllabi, 4 personas, 2 subscription tiers, sample library content) → verifies audit log populated.

### Acceptance (demo script)

1. [ ] `npm run test:e2e -- platform-admin-smoke` passes
2. [ ] Recording shows full Platform Admin onboarding flow
3. [ ] All Flow 1 v2 §11 acceptance criteria pass

### Out of scope

- Edge case tests (added per ticket as needed)

---

## T-027 — Milestone M-01 PR + demo recording

**Layer:** 1
**Milestone:** M-01
**Estimate:** 0.5 days
**Status:** todo

### What this ticket builds

Final commits, PR opened against staging, demo video recorded (5-7 min) showing full Platform Admin flow. Update ROADMAP.md status to `done`.

### Acceptance

1. [ ] All M-01 tickets marked `done`
2. [ ] PR opened with `feat(platform-admin): M-01 milestone — Platform Setup`
3. [ ] CI green
4. [ ] Demo recording attached to PR description
5. [ ] Abd. + Awais review + approve

---

## Milestone done — when

All 12 tickets complete, PR merged to staging, ROADMAP updated. Ready to begin M-02 (School Onboarding).

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Initial M-01 milestone. 12 tickets defined. Foundation in M-00 must complete first. | @abdurrehman (with Claude) |

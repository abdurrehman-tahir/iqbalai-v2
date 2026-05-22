# M-00 — Foundation: infra + containers + base code

**Status:** todo
**Estimated duration:** 3-4 weeks
**Tickets:** T-001 through T-015

## Goal

Stand up the entire technical foundation IqbalAI runs on. By milestone end: every container is up, every base abstraction (auth middleware, DB layer, Celery, NATS, RAG, LLM client, frontend skeleton, observability) works at a smoke-test level, BUT no user-facing feature has been built yet.

**Demo at milestone end:**
- `docker compose up` brings up all services
- `curl http://localhost:8080/health` returns 200
- `alembic upgrade heads` runs cleanly across both schemas
- Authentik admin can log in to Authentik UI
- Frontend loads at `http://localhost:3000` showing landing page
- Smoke-test for: RAG pipeline (sample query returns chunk), LLM client (sample prompt returns response), Celery (sample task completes), NATS (sample event publishes + consumer logs it), MinIO (file upload + download works)

---

## T-001 — Repo scaffold + monorepo layout

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 1 day
**Status:** todo

### Spec source
- N/A (purely infra; no spec)

### ARCH source
- `ARCHITECTURE.md` §0 (Quick Index — read the table of contents)
- `ARCHITECTURE.md` §2 (Project structure — full repo layout)

### Depends on
- (none — first ticket)

### What this ticket builds

Initialize the monorepo. Create folder structure per ARCH §2: `api/` (FastAPI backend), `frontend/` (Next.js), `infrastructure/` (Authentik, Postgres, Redis, NATS, MinIO, Qdrant configs), `docs/` (move bootstrap contents in), `.claude/`, `.github/`. Initialize git on `main`; create `staging` branch per BRANCHING.md.

### Acceptance (demo script)

1. [ ] `git status` clean on `staging` branch
2. [ ] Folder structure matches ARCH §2 exactly
3. [ ] Bootstrap contents (this `docs/` folder) committed
4. [ ] `.github/PULL_REQUEST_TEMPLATE.md` exists per WORKFLOW.md §1.3 (PR description format) + .github/PULL_REQUEST_TEMPLATE.md
5. [ ] `.gitignore` excludes `node_modules`, `.env`, `__pycache__`, `.venv`, `*.pyc`, `dist/`, `build/`

### Out of scope for this ticket

- Actual code in `api/` or `frontend/` — handled by T-002 onwards
- CI/CD setup — T-014

---

## T-002 — Docker Compose: three-file skeleton + Postgres container

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 1-2 days
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `ARCHITECTURE.md` §15.1-§15.3 (Docker Compose structure, three-file layout, env handling)
- `STACK_LOCK.md` §1 (Backend — Postgres locked at 16.x)

### Depends on
- T-001 (monorepo scaffold)

### What this ticket builds

Per STACK_LOCK §1.4 + ARCH §15.4: create **ONE `docker-compose.yml` at the repo root**. Postgres 16 service with healthcheck, volume mount, named volume `pg_data`, bind to the `iqbalai_net` bridge network. Create **ONE `.env.example` at the repo root** with all required Postgres env vars (DB_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB). No Makefile. No split compose files. No `docker/` subdirectory.

### Acceptance (demo script)

1. [ ] `cp .env.example .env` works; `.env` is gitignored
2. [ ] `docker compose up -d postgres` starts cleanly from repo root
3. [ ] `docker compose ps` shows postgres healthy
4. [ ] `docker compose exec postgres psql -U iqbalai -c "SELECT version()"` returns Postgres 16.x
5. [ ] `.env.example` lists all required Postgres env vars with safe placeholders
6. [ ] `docker compose down -v` cleans up

### Out of scope

- App containers (T-005 onwards)
- Multi-schema setup (T-003)

---

## T-003 — Postgres: dual schemas (school + independent) + Alembic dual heads

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1 (role hierarchy mentions tenant types)
- N/A specific to this; primarily ARCH

### ARCH source
- `ARCHITECTURE.md` §3.16 (Independent users separate-schema tenant model)
- `ARCHITECTURE.md` §4.12 (Alembic migrations)
- `ARCHITECTURE.md` §4.21 (Dual Alembic heads — locked pattern)

### Depends on
- T-002 (Postgres container running)

### What this ticket builds

Create two Postgres schemas: `school` and `independent`. Set up Alembic with dual heads — separate version directories (`alembic/versions/school/`, `alembic/versions/independent/`), branch labels per ARCH §4.21. `alembic.ini` configured. `env.py` reads schema from branch + applies `schema_translate_map`. One initial empty migration per branch (just to validate dual-head setup).

### Acceptance (demo script)

1. [ ] `alembic upgrade heads` runs cleanly (no head conflicts)
2. [ ] `psql` shows both `school` and `independent` schemas exist
3. [ ] `alembic heads` shows two heads — one per branch — with branch labels `school` and `independent`
4. [ ] Migration in `alembic/versions/school/0001_initial.py` has `branch_labels = ("school",)`
5. [ ] Migration in `alembic/versions/independent/0001_initial.py` has `branch_labels = ("independent",)`
6. [ ] CI script (placeholder for T-014) checks `alembic upgrade heads --sql` runs without errors

### Out of scope

- Any actual tables (User, etc. come later)
- Cross-schema views (T-007)
- RLS policies (T-007)

---

## T-004 — Authentik container + base OIDC config

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2-3 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1 (role hierarchy — users come from Authentik)
- `flow-2-admin-coordinator-setup.md` §3.1 (admin invitation Path A; signup Path B)

### ARCH source
- `ARCHITECTURE.md` §6.3 (Authentik setup — locked configuration)
- `ARCHITECTURE.md` §6.4 (OIDC flow Authorization Code + PKCE)
- `ARCHITECTURE.md` §6.20 (Independent user signup path — `/independent/signup` route)

### Depends on
- T-002 (Docker Compose), T-003 (Postgres ready for Authentik's internal DB)

### What this ticket builds

Add Authentik container to `docker-compose.yml`. Configure: OIDC application for IqbalAI, OAuth2 client ID/secret, property mappers for `tenant_type`, `role`, `school_id`, `district_id`, `scoped_ids`. Set up two flows: invite-based (Path A for school users) and self-signup (Path B for independent users). Email verification flow.

### Acceptance (demo script)

1. [ ] `docker compose up authentik` starts
2. [ ] Authentik UI accessible at `http://localhost:9000`
3. [ ] OIDC application `iqbalai-api` configured with redirect URIs
4. [ ] Property mappers set `tenant_type`, `role`, `school_id` claims on issued JWTs
5. [ ] `/independent/signup` flow exists in Authentik (placeholder UI for now)
6. [ ] Sample test: manually create a user in Authentik UI, JWT contains expected claims

### Out of scope

- API integration with Authentik (T-005)
- Frontend login UI (T-006)
- Actual admin user creation flow (M-01 + M-02)

---

## T-005 — Redis + NATS + MinIO + Qdrant containers + healthchecks

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 1 day
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `STACK_LOCK.md` §3 (Database & Storage), §4 (AI / LLM Layer), §5 (Infrastructure)
- `ARCHITECTURE.md` §15.1 (Container topology)

### Depends on
- T-002 (Compose skeleton)

### What this ticket builds

Add Redis, NATS (JetStream enabled per STACK_LOCK §4), MinIO, Qdrant to `docker-compose.yml`. Each has healthcheck + named volume + appropriate env vars in `.env.example`. NATS JetStream stream config for the locked subject taxonomy (per ARCH §9.3) — initial empty streams, consumers come later.

### Acceptance (demo script)

1. [ ] `docker compose up -d` brings up all 6 infra containers (postgres, authentik, redis, nats, minio, qdrant) cleanly
2. [ ] `docker compose ps` shows all healthy
3. [ ] `redis-cli ping` returns PONG
4. [ ] `nats stream ls` shows configured streams
5. [ ] MinIO console accessible at `localhost:9001`; default buckets created
6. [ ] Qdrant `curl localhost:6333/collections` returns empty collection list

### Out of scope

- Application code that uses these (T-007 onwards)
- Collection creation in Qdrant (T-010 RAG infra)

---

## T-006 — FastAPI app skeleton + healthcheck endpoint + AuthMiddleware base

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2-3 days
**Status:** todo

### Spec source
- N/A (infra layer)

### ARCH source
- `ARCHITECTURE.md` §6.6 (AuthMiddleware spec)
- `ARCHITECTURE.md` §5.1-§5.4 (API design — routing, status codes, error envelopes, response streams)
- `ARCHITECTURE.md` §15.4 (Application container — uvicorn config)

### Depends on
- T-001 (repo), T-002 (DB), T-003 (schemas), T-004 (Authentik)

### What this ticket builds

`api/app/main.py` FastAPI app. `core/middleware/auth.py` per ARCH §6.6 (validates JWT, sets `request.state.claims`, has `PUBLIC_PATHS` allowlist). `core/dependencies.py` skeleton with `get_db()` per ARCH §3 (RLS + schema routing per T-003/§4.21). `core/exception_handlers.py` per ARCH §5.4. One endpoint: `GET /health` returns `{"status": "ok"}` — bypassed auth via `PUBLIC_PATHS`. Dockerfile + entry in `docker-compose.yml`.

### Acceptance (demo script)

1. [ ] `docker compose up api` builds + starts cleanly
2. [ ] `curl localhost:8080/health` → `{"status": "ok"}`
3. [ ] `curl localhost:8080/secret` → 401 (any non-public path requires auth)
4. [ ] With a valid JWT from Authentik: `curl -H "Authorization: Bearer ..." localhost:8080/health` works
5. [ ] Hot-reload works in dev mode (uvicorn `--reload`)
6. [ ] Logging structured (per ARCH §14.3) — visible in container logs

### Out of scope

- Any feature endpoints (M-01 onwards)
- Full RLS (T-007)
- Frontend integration (T-009)

---

## T-007 — Base DB mixins + User table + RLS policies + cross-schema views

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2-3 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1 (role hierarchy enum)

### ARCH source
- `ARCHITECTURE.md` §4.1-§4.8 (DB naming, primary keys UUIDv7, AuditMixin, SoftDeleteMixin, TenantMixin, FKs)
- `ARCHITECTURE.md` §3.9-§3.13 (RLS, three-layer defense)
- `ARCHITECTURE.md` §3.16 (cross-schema views for platform-shared tables)
- `ARCHITECTURE.md` §4.21 (Alembic for both schemas)

### Depends on
- T-003 (schemas), T-006 (FastAPI ready to model these)

### What this ticket builds

`api/app/models/mixins.py`: `AuditMixin`, `SoftDeleteMixin`, `TenantMixin`, `Base` with UUIDv7 default. `api/app/models/user.py`: User table (in school schema) per ARCH §6.2 — `authentik_id`, `email`, `role`, `school_id`, `district_id`, `scoped_ids`, `display_name`. Alembic migration in `school` branch creating users + RLS policy + cross-schema view `independent.users_readonly` for platform admin access.

### Acceptance (demo script)

1. [ ] Migration runs cleanly via `alembic upgrade heads`
2. [ ] `school.users` table exists with all columns + indices
3. [ ] RLS enabled; `current_user_id` claim required for any SELECT
4. [ ] Cross-schema view `independent.users_readonly` exists, read-only
5. [ ] Unit test: SELECT without RLS claims fails; with claims succeeds
6. [ ] Soft-delete works: `deleted_at` set, subsequent SELECT skips row
7. [ ] Audit fields populated on insert/update

### Out of scope

- Actual user creation flow (M-01)
- Other tenant-scoped tables (later milestones)

---

## T-008 — Permission primitives: require_role + require_scope + inheritance

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 1-2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1 (role hierarchy)
- `flow-2-admin-coordinator-setup.md` §4 (permissions matrix)

### ARCH source
- `ARCHITECTURE.md` §6.7 (Dependency primitives: require_role, require_scope, require_self_or_admin, require_parent_of, require_teacher_of)
- `ARCHITECTURE.md` §6.19 (Permission inheritance semantic: require_role(X) = X OR HIGHER within scope)

### Depends on
- T-006 (FastAPI deps), T-007 (User model)

### What this ticket builds

`api/app/core/dependencies.py`: full implementation of `require_role(role)` per ARCH §6.7 + §6.19 (inheritance). `ROLE_HIERARCHY` map: platform_admin=6, district_admin=5, school_admin=4, coordinator=3, teacher=2, student=1, parent=1. Other primitives stubbed. Returns 403 with `PERMISSION_DENIED` per ARCH §5.4 error envelope. Unit tests per role pair.

### Acceptance (demo script)

1. [ ] Unit tests: Platform Admin accessing teacher endpoint → 200; teacher accessing district admin endpoint → 403
2. [ ] Unit tests: District Admin can access School Admin endpoint within own district (200); cross-district (404 per §3.13)
3. [ ] Parent inherits NO automatic rights (peer to student, not above)
4. [ ] `require_role('coordinator')` allows: coordinator, school_admin, district_admin, platform_admin (in scope)
5. [ ] Error envelope: `{"error": {"code": "PERMISSION_DENIED", "message": "..."}}` per §5.4
6. [ ] `require_scope` skeleton in place (full impl can come per-feature later)

### Out of scope

- `require_parent_of`, `require_teacher_of` deep implementations — stubs only (full in M-06)
- Audit logging of permission denials — T-014

---

## T-009 — Frontend Next.js skeleton + Tailwind + i18n + 4 languages

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2-3 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.2 (4 launch languages: en, ur, sd, ps)

### ARCH source
- `ARCHITECTURE.md` §12.1-§12.5 (Frontend architecture)
- `ARCHITECTURE.md` §13 (i18n — next-intl, locale resolution, RTL handling, message file structure)

### Depends on
- T-001 (monorepo)

### What this ticket builds

`frontend/` Next.js 15 + App Router + Tailwind + TypeScript per STACK_LOCK §2. next-intl integration. Message files in `messages/en/`, `messages/ur/`, `messages/sd/`, `messages/ps/` per ARCH §13. Locale resolution via cookie. Tailwind logical utilities (`me-`, `ms-`, `text-start`) for RTL. Landing page at `/` shows i18n'd welcome + 4-language switcher.

### Acceptance (demo script)

1. [ ] `npm run dev` from `frontend/` starts cleanly
2. [ ] Landing page renders at `localhost:3000` in English
3. [ ] Language switcher rotates through 4 languages
4. [ ] Urdu/Sindhi/Pashto render in RTL with proper layout
5. [ ] No hardcoded English in landing page — all via `t('key')`
6. [ ] Sample message keys in all 4 files; missing translation falls back to English with logged warning
7. [ ] Dockerfile + entry in compose file

### Out of scope

- Actual feature pages (M-01 onwards)
- Disclaimer / ToS UI (M-01)

---

## T-010 — LLM client + RAG pipeline base (Pattern S smoke test)

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 3-4 days
**Status:** todo

### Spec source
- N/A (infra; specific feature use comes later)

### ARCH source
- `ARCHITECTURE.md` §7.1-§7.10 (RAG pipeline — Patterns S/A, embedding model BGE-M3, reranker, Qdrant config, chunking, retrieval, context assembly)
- `ARCHITECTURE.md` §8.1-§8.6 (LLM abstraction: chokepoint, task-based routing, env vars, prompts framework)
- `ARCHITECTURE.md` §8.22 (Vision-LLM routing — basic scaffolding)
- `STACK_LOCK.md` §4 (AI / LLM Layer: Groq, BGE-M3, Qdrant)

### Depends on
- T-005 (Qdrant), T-006 (FastAPI)

### What this ticket builds

`infrastructure/llm/`: `client.py` (chat function with task routing), `prompts/` folder with sample prompt, env var routing per ARCH §8.4. `infrastructure/rag/`: embedding + retrieval pipeline base (BGE-M3 via infinity-emb or sentence-transformers, reranker bge-reranker-v2-m3). Initial Qdrant collections empty. Smoke test endpoint `POST /api/v1/smoketest/rag` (internal, not user-facing) accepts a query, runs Pattern S, returns top chunks.

### Acceptance (demo script)

1. [ ] `curl POST /api/v1/smoketest/rag -d '{"query":"sample"}'` returns `{"chunks": [], "status": "ok"}` (empty since no content ingested)
2. [ ] LLM smoke test: separate endpoint hits Groq + returns response
3. [ ] All LLM calls go through `infrastructure/llm/client.py` chokepoint (per ARCH §8.1)
4. [ ] `task` parameter accepted on every call (smoke test uses `task="smoke_test"`)
5. [ ] Token counting via tiktoken works
6. [ ] Vision-LLM routing stub: if `attached_images` is non-empty, routes to vision model env var (per §8.22)
7. [ ] Prometheus metrics emitted per LLM call (provider, model, task, latency, tokens)

### Out of scope

- Actual content ingestion (T-013 for upload pipeline base; full ingestion in M-04)
- Pattern A agentic tools (later — needed in M-07 framework engine)

---

## T-011 — Celery + task queue setup + tenant_task decorator

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2 days
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `ARCHITECTURE.md` §10.1-§10.5 (Celery — what goes in jobs, four queues, task definition, tenant_task decorator, idempotency)
- `ARCHITECTURE.md` §10.6 (Beat schedule — empty at first, populated as features land)

### Depends on
- T-005 (Redis as broker), T-007 (DB models for tenant context)

### What this ticket builds

`infrastructure/celery/`: `celery_app.py` per ARCH §10. Four queues: `default`, `ingestion`, `ml`, `notifications`. `tasks/` folder. `@tenant_task` decorator per ARCH §10.4. Beat scheduler skeleton (empty for now). Worker + beat in `docker-compose.yml`. Smoke test task `tasks.smoke.ping()` that returns "pong".

### Acceptance (demo script)

1. [ ] `docker compose up celery-worker celery-beat` start cleanly
2. [ ] `python -c "from app.tasks.smoke import ping; print(ping.delay().get(timeout=10))"` returns "pong"
3. [ ] Task runs on the `default` queue
4. [ ] `@tenant_task` correctly extracts tenant context from kwargs
5. [ ] Failed tasks logged + retried per §10.9
6. [ ] Prometheus metrics emit per task (success/failure/duration)

### Out of scope

- Real beat tasks (added per feature in later milestones)
- Dead-letter queue (T-014)

---

## T-012 — NATS JetStream: event envelope + sample publish/consume

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 1-2 days
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `ARCHITECTURE.md` §9.1-§9.9 (NATS JetStream config, subject taxonomy, event envelope, publish/consume patterns)
- `ARCHITECTURE.md` §9.3 (subject list — includes all spec-set additions)

### Depends on
- T-005 (NATS), T-006 (FastAPI for event publishers)

### What this ticket builds

`infrastructure/events/`: `publisher.py`, `consumer.py`. Event envelope schema per ARCH §9 (`tenant_id`, `tenant_type`, `user_id`, `session_id`, `occurred_at`, `event_type`, `payload`). Configure JetStream streams matching ARCH §9.3 subject taxonomy. Smoke test: publish `system.smoke_test`; consumer logs receipt.

### Acceptance (demo script)

1. [ ] `nats stream ls` shows all configured streams from §9.3
2. [ ] Smoke endpoint publishes `system.smoke_test` event
3. [ ] Consumer (separate process) logs the event with full envelope
4. [ ] Event retention: 7 days for live streams (per §9)
5. [ ] Backpressure alert configured (>30s lag triggers alarm — T-014 will wire this to Grafana)

### Out of scope

- Specific feature event consumers (per feature in later milestones)
- `student_events` table for analytics (M-12 + Flow 6)

---

## T-013 — File upload pipeline base + first profile (`recovery_bundle` placeholder)

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2-3 days
**Status:** todo

### Spec source
- N/A (infra; per-profile specs come with each feature)

### ARCH source
- `ARCHITECTURE.md` §11.1-§11.10 (six upload surfaces, single pipeline, UploadProfile, MinIO key strategy, tenant scoping, streaming, dedup)
- `ARCHITECTURE.md` §11.16 (Endpoint shapes — canonical)
- `ARCHITECTURE.md` §11.19 (Upload profiles consolidated list — placeholder for now)

### Depends on
- T-005 (MinIO), T-006 (FastAPI)

### What this ticket builds

`infrastructure/storage/`: `upload_pipeline.py` (one parametrized pipeline per ARCH §11.2), `profiles.py` (UploadProfile registry — initially with `recovery_bundle` profile only; others added per feature), `client.py` (S3-compatible MinIO client). `api/app/features/uploads/router.py` with `POST /api/v1/uploads` returning 202 + tracking URL per §11.16. SHA-256 dedup, streaming, magic-byte validation, soft-delete.

### Acceptance (demo script)

1. [ ] `curl POST /api/v1/uploads -F file=@sample.pdf -F profile=recovery_bundle` returns 202 + `{"upload_id":"...","status_url":"/api/v1/uploads/{id}"}`
2. [ ] File appears in MinIO with key matching ARCH §11.4 strategy (school_id prefix, UUIDv7, date-partitioned)
3. [ ] `GET /api/v1/uploads/{id}` shows status `ready`
4. [ ] Re-uploading same file (same SHA-256) returns existing upload_id (dedup works per profile scope)
5. [ ] Magic-byte mismatch rejected
6. [ ] Profile size limit enforced (50 MB for recovery_bundle)

### Out of scope

- Other profiles (`platform_reference_book`, `school_library_content`, etc.) — added per feature
- Actual ingestion (chunking, embedding) — per profile, M-04 onwards
- OCR — T-015 if any

---

## T-014 — CI/CD: GitHub Actions + tests + alembic head check + linting

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2 days
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `WORKFLOW.md` §0 + §2.x (CI requirements)
- `BRANCHING.md` (CI must be green before merge)
- `.claude/CLAUDE.md` "CI invariants (non-negotiable)" — **this CI config MUST satisfy every invariant listed there**

### Depends on
- T-001 (repo), T-006 (API skeleton), T-009 (frontend skeleton)

### What this ticket builds

`.github/workflows/ci.yml`: runs on PR and push to staging. Steps: (1) backend lint (ruff + mypy), (2) backend tests (pytest), (3) frontend lint (eslint), (4) frontend tests (vitest), (5) `alembic upgrade heads --sql` validation, (6) docs-only PR fast-path (skip code checks). Branch protection rules per BRANCHING.md.

### Acceptance (demo script)

1. [ ] PR to staging triggers full CI; passes
2. [ ] PR with intentional Python syntax error fails ruff check → blocks merge
3. [ ] PR with alembic head conflict fails the validation
4. [ ] Docs-only PR (`docs/**` paths only) skips code checks per BRANCHING.md §8.1
5. [ ] Staging branch protected — no direct push allowed; only PR merges
6. [ ] Every lint/test/type/coverage job installs dev deps before invoking the tool (CLAUDE.md CI invariant 1); job command names match `pyproject.toml` + `frontend/package.json` exactly (invariant 2); frontend jobs guard on `frontend/` via a post-checkout detect step, not job-level `hashFiles` (invariant 4)

### Out of scope

- Deployment pipeline (later)
- End-to-end tests (added incrementally per feature)

---

## T-015 — Observability: Prometheus + Grafana base + smoke dashboards

**Layer:** Foundation
**Milestone:** M-00
**Estimate:** 2 days
**Status:** todo

### Spec source
- N/A (infra)

### ARCH source
- `ARCHITECTURE.md` §14.1-§14.10 (Observability + logging + PII scrubbing + audit log)
- `ARCHITECTURE.md` §9.19 (NATS metrics)
- `ARCHITECTURE.md` §10.10 (Celery metrics)
- `ARCHITECTURE.md` §11.18 (Upload pipeline metrics)

### Depends on
- T-002 (compose), T-006 (FastAPI), T-011 (Celery), T-012 (NATS)

### What this ticket builds

Prometheus + Grafana containers in `docker-compose.yml`. Locked metrics per ARCH §14: HTTP latency, error rate, NATS lag, Celery queue depth, LLM token cost, upload pipeline funnel. Grafana base dashboards: "Platform Health", "RAG Performance", "LLM Observability". PII scrubber on logs per §14.3-§14.4.

### Acceptance (demo script)

1. [ ] Prometheus scrapes API + Celery + NATS + Qdrant
2. [ ] Grafana accessible at `localhost:3001`; admin dashboards visible
3. [ ] Sample request to `/health` shows up in HTTP latency metric
4. [ ] PII scrubber: a log line with sample email gets `email=<redacted>` in stored log
5. [ ] Alert rule sample: NATS consumer lag > 30s fires alert (verified by simulating lag)

### Out of scope

- Sentry integration (TODO — Phase 2 per TODO.md)
- Full alerting routes (Slack/email) — Phase 2

---

## Milestone done — when

All 15 tickets above are complete. The platform "runs empty" — all infra works, all base abstractions function at smoke-test level, but no user-facing feature exists yet. Ready to begin M-01 (Platform Setup).

**Pre-M-01 checklist before opening milestone PR:**
- [ ] `docker compose up` brings up entire stack
- [ ] All smoke tests pass
- [ ] CI green on the milestone branch
- [ ] Demo recording (5-min video) showing each component working
- [ ] ROADMAP.md M-00 status → `done`

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Initial M-00 milestone. 15 foundation tickets defined. | @abdurrehman (with Claude) |
# ENV_VARS.md — Environment Variable Reference

**Status:** Living document
**Owner:** @abdurrehman-tahir
**Purpose:** Single canonical list of every environment variable used by IqbalAI. Each entry: variable name, default, purpose, source (which spec or ARCH section), where it's read in code.

---

## Conventions

- All env var names: `SCREAMING_SNAKE_CASE`.
- Boolean values: `true` / `false` (lowercase).
- Time durations: integer seconds OR `_DAYS` / `_HOURS` / `_SECONDS` suffix matching the unit in the name.
- Costs / monetary: `_USD` suffix, decimal-as-string allowed.
- Optional vars: documented with `(optional)` tag.

---

## Core platform (existing — pre-T0)

These are already documented in ARCHITECTURE.md §15.2 and `infrastructure/config/`. Re-listed here for completeness; canonical source is ARCH §15.2 + `api/app/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | (required) | Primary Postgres connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection (cache, Celery broker, pub/sub) |
| `NATS_URL` | `nats://nats:4222` | NATS JetStream connection |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3-compatible storage |
| `WEBSEARCH_URL` | `http://searxng:8080` (compose) / `http://localhost:8888` (host API) | Self-hosted SearXNG base URL for RAG tier-3 + exam-framework research (ARCH §7.12) |
| `AUTHENTIK_URL` | (required) | Authentik IDP base URL |
| `AUTHENTIK_CLIENT_ID` | (required) | OIDC client ID |
| `AUTHENTIK_CLIENT_SECRET` | (required) | OIDC client secret |
| `LLM_*` (suite) | varies | LLM provider routing (see ARCH §8.4) |
| ... | | (see ARCH §15.2 for full list) |

---

## Spec-set additions (T0 batch, 2026-05-14)

These were introduced during Flows 1-6 + Flow 13 review rounds. Each entry includes the source spec / ARCH section.

### Custom Persona (ARCH §8.20)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `PERSONA_LEARNING_BATCH_DAYS` | `7` | Cadence (in days) of the per-student Custom persona summary batch. The Celery beat `persona.update_custom` runs daily and picks up students whose `last_batch_run_at` is older than this value. | Flow 1 §3.5 + ARCH §8.20 + §10.6 |

### Exam Framework engine (ARCH §3.19 + §8.21)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `FRAMEWORK_REFRESH_DAYS` | `90` | Cadence (in days) for the Pattern-A exam framework refresh agent. The Celery beat `framework.refresh_quarterly` runs daily and picks up frameworks whose `last_research_run_at` is older than this. | Flow 4 v3 §3.5 + ARCH §8.21 + §10.6 |
| `FRAMEWORK_RESEARCH_COST_CEILING_USD` | `10` | Hard cap (in USD) per framework research run. Agent halts and preserves partial results if exceeded. Platform Admin alerted. | Flow 4 v3 §3.5.2 + ARCH §8.21 |
| `FRAMEWORK_RESEARCH_USD_PER_1K_TOKENS` | `0.001` | Blended token price used to estimate a research run's USD spend from LLM usage (a safety knob for the ceiling above, not billing-grade). | T-093 + ARCH §8.21 |
| `FRAMEWORK_RESEARCH_MAX_SOURCES` | `15` | Number of top search results the Pattern-A run fetches + synthesises per framework (§8.21 target 10–20). | T-093 + ARCH §8.21 |
| `FRAMEWORK_APPROVAL_SLA_HOURS` | `72` | Target SLA for Platform Admin to approve AI-generated framework plans. 7-day reminder; 14-day escalation. | Flow 4 v3 Q-EF7 + ARCH §8.21 |

### Graduation lifecycle (Flow 4 v3 §3.9)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `GRADUATION_GRACE_DAYS` | `180` | School read-only window (in days) for graduated Grade 12 students before atomic auto-migration to independent tenant. Daily Celery beat `graduation.migrate_eligible_students` picks up students past this window. | Flow 4 v3 §3.9 |

### AI session adaptation (Flow 6 §3.9 + ARCH §8.22)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `AI_ADAPT_QUESTION_THRESHOLD` | `2` | Number of questions on the same sub-topic in a single session that triggers the per-session angle-switch (Flow 6 §3.9). Read in `infrastructure/llm/session_adapter.py`. | Flow 6 v1 §3.9 + ARCH §8.22 |
| `LIVE_FEEDBACK_TICK_SECONDS` | `60` | Cadence for live-feedback WebSocket ticks (T-177). | Flow 6 §3.7 |
| `LIVE_FEEDBACK_PANEL_DELAY_SECONDS` | `120` | Seconds of activity before the live feedback panel auto-shows (T-180). | Flow 6 §3.7 |
| `STUCK_NUDGE_SECONDS` | `600` | Same-page idle with 0 questions before one-time stuck nudge (T-181). | Flow 6 §3.7 |
| `EVENT_PIPELINE_LAG_SECONDS` | `30` | Consumer lag threshold before `system.event_pipeline_lag` (T-178). | Flow 6 §3.8 |
| `EVENT_PIPELINE_LAG_CHECK_SECONDS` | `15` | How often the lag monitor polls durable consumers. | T-178 |

### Concept enrichment (Flow 6 §3.10 + ARCH §10.6)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `CONCEPT_ENRICHMENT_CACHE_DAYS` | `90` | Age (in days, 1–365) after which a per-concept enrichment entry (real-world uses, career links, mini-sim) is regenerated. The Celery beat `concept.refresh_quarterly` runs daily and picks up entries whose `generated_at` is older than this. Read in `features/concept_enrichment/cache.py`. | Flow 6 §3.10 + ARCH §10.6 + M-15 T-189 |

### Vision-LLM routing (ARCH §8.22)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `LLM_VISION_MODEL` | `groq:llama-3.2-90b-vision-preview` | The vision-capable model used when a request payload contains `attached_images[]`. Overrides per-task default model for that single call. | Flow 6 v2 + ARCH §8.22 |
| `VISION_QA_DAILY_SOFT_CEILING` | `20` | Soft per-student/day ceiling on vision-model Q&A calls (T-170). Excess image-bearing questions are rejected before the LLM call to bound ~2–3× vision cost. | Flow 6 §3.5 + M-13 T-170 |
| `VISION_QA_USD_PER_CALL` | `0.01` | Approximate USD cost used when logging vision-call observability (not billing-grade). | Flow 6 §3.5 + M-13 T-170 |

### Subscription module — Phase 2 placeholders (ARCH §3.17 + §11.20 + Flow 13)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `STRIPE_API_KEY` | (placeholder; empty at launch) | Stripe Secret Key for the subscription module. At launch: env var EXISTS as placeholder; NOT used (no Stripe SDK installed). Phase 2: real Stripe key required. | Flow 13 + ARCH §3.17 + §11.20 |
| `STRIPE_WEBHOOK_SECRET` | (placeholder; empty at launch) | Stripe webhook signing secret. At launch: env var EXISTS as placeholder. Phase 2: required for webhook signature verification per ARCH §11.20. | Flow 13 + ARCH §11.20 |

### Authentik OIDC bootstrap (M-07a T-247, ARCH §6.4)

| Variable | Default | Purpose | Source |
|---|---|---|---|
| `AUTHENTIK_BOOTSTRAP_TOKEN` | (dev/CI only; empty in prod) | Consumed by Authentik at first container init to mint an akadmin API token with this exact value. Set `AUTHENTIK_API_TOKEN` equal to it so the API + `scripts/seed_e2e_auth_users.py` provision users with no manual `ak shell` step. Dev/CI only — generate a fresh random value per environment. | M-07a T-247 + Authentik docs |
| `OIDC_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/callback` | Redirect target Authentik returns the browser to after login. Per ARCH §6.4 the API owns the code exchange, so this is the API callback route. Consumed by the OIDC blueprint (`infrastructure/authentik/blueprints/iqbalai-oidc.yaml`) and must match the provider's registered redirect URI. | M-07a T-247 + ARCH §6.4 |
| `OIDC_POST_LOGOUT_REDIRECT_URI` | `http://localhost:3000/login` | Allowed `redirect_uri` for Authentik's OIDC end-session endpoint after logout (T-246). Must be listed on the OIDC provider's redirect URIs (blueprint) and match what `getLogoutUrl()` passes. | M-07a T-246 + ARCH §6.8 |

---

## Validation rules

- All required env vars validated at app startup via `api/app/config.py` (Pydantic `BaseSettings`).
- Placeholder env vars (STRIPE_*) at launch: empty string OK; presence checked but value not used.
- Numeric env vars: validated as integers OR floats per documentation above.
- Time-duration env vars: never negative; sensible upper bounds enforced (e.g., `GRADUATION_GRACE_DAYS` must be ≤ 365).

---

## Adding a new env var

1. Add to this file (under appropriate section).
2. Update `api/app/config.py` Pydantic `Settings` class.
3. Update `.env.example` (per ARCH §15.2).
4. Document the source spec / ARCH section in this file.
5. PR review checks: presence in all three files.

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Initial file created during T0 batch. Lists 9 spec-set additions (Custom Persona, Exam Framework engine, Graduation, AI adaptation, Vision-LLM, Stripe placeholders). | @abdurrehman (with Claude) |
| 2026-10-03 | Added `CONCEPT_ENRICHMENT_CACHE_DAYS` (M-15 T-189). | M-15 (with Claude) |

# STACK_LOCK.md — IqbalAI v2

**Status:** Locked
**Owner:** @abdurrehman
**Last reviewed:** 2026-05-11
**Purpose:** This document is the non-negotiable technology stack for IqbalAI v2. Every library, service, and tool used in this codebase must appear in this file. Anything not listed here is forbidden unless explicitly approved in `docs/DEVIATIONS.md`.

---

## How to read this document

1. **Locked** items are non-negotiable. Claude Code and human developers must use exactly these.
2. **Default** items are the recommended choice. Use them unless a written deviation is approved.
3. **Forbidden** items are banned outright. Pre-commit hooks and CI will reject them.
4. **Pending** items require a separate decision documented in `docs/ARCHITECTURE.md` before use.

To deviate from anything in this file:
1. Open a PR that adds an entry to `docs/DEVIATIONS.md` with: import path, file scope, reason, approver.
2. Get explicit `@abdurrehman` approval on that PR.
3. Only after merge can the deviation be used in subsequent PRs.

---

## 1. Backend

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Web framework | **FastAPI** (latest stable) | MIT | Async-native. WebSockets, streaming, OpenAPI built in. |
| ASGI server | **Uvicorn** with `--workers` via Gunicorn in production | BSD-3 / MIT | Gunicorn supervises Uvicorn workers inside the app container. |
| Process orchestration | **docker-compose** (everything except nginx) | Apache-2.0 | See section 5 for compose file layout. |
| Language version | **Python 3.12** | — | Locked via the app's Dockerfile base image. |
| Dependency manager | **uv** (Astral) | Apache-2.0/MIT | Replaces pip + pip-tools + venv. Single `pyproject.toml`. Lockfile committed. |
| Linter / formatter | **ruff** (lint + format both) | MIT | Replaces black, isort, flake8. |
| Type checker | **mypy** in `--strict` mode | MIT | Enforced in CI. |
| Validation / models | **Pydantic v2** | MIT | Every API request/response model is a Pydantic model. **Every endpoint MUST declare `response_model=`** so the generated OpenAPI (and the FE typed client) stays accurate. Missing `response_model` fails CI. |
| Testing | **pytest** + **pytest-asyncio** + **pytest-cov** | MIT | Coverage target: 70% on `app/services/`, 50% overall. |
| HTTP client | **httpx** (async) | BSD-3 | `requests` is forbidden. |

**Forbidden:** Flask, Django, aiohttp, requests (sync), pipenv, poetry, black (standalone), isort (standalone), flake8.

---

## 2. Frontend

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Framework | **Next.js** (latest stable, App Router) | MIT | Self-hosted via Node. No Vercel deploy required. |
| Language | **TypeScript** (`strict: true`) | Apache-2.0 | No plain JS in `frontend/src/`. |
| Package manager | **pnpm** | MIT | Faster than npm, deterministic, less disk. |
| UI components | **shadcn/ui** | MIT | Copy-paste components into `frontend/src/components/ui/`. |
| Styling | **Tailwind CSS** | MIT | Design tokens in `tailwind.config.ts`. No inline styles. |
| Primitives | **Radix UI** (via shadcn) | MIT | Accessibility foundation. |
| State management | **Zustand** for client state, **TanStack Query** for server state | MIT | No Redux. No MobX. |
| Forms | **react-hook-form** + **Zod** validation | MIT | Every form uses both. |
| Rich-text editor | **TipTap** (core + free extensions only) | MIT | Headless, ProseMirror-based; emits JSON stored as `lecture_versions.content_jsonb` (immutable version-on-save, Flow 5). No CRDT/real-time co-editing for lectures. (Group collaborative notes use Yjs — separate scoped deviation, see below.) |
| Collaborative notes (Flow 11 only) | **Yjs** (CRDT) | MIT | Group shared notes #103 **only**; syncs over FastAPI WebSocket + Redis; persisted as binary doc in `group_notes.yjs_doc`. Authorized via DEVIATIONS.md; NOT for lecture editing. |
| Charts | **Recharts** (standard charts) + **Apache ECharts** (heatmaps, complex viz) | MIT / Apache-2.0 | ECharts only where Recharts can't do the job (e.g., geographic heatmap). |
| Calendar | **FullCalendar** (MIT core only, no premium plugins) | MIT | Used for study plan view. |
| Icons | **lucide-react** | ISC | Default icon set. |
| Animation | **Framer Motion** (sparingly) + Tailwind transitions | MIT | No bouncing, no fade-everything. Purposeful only. |
| i18n | **next-intl** | MIT | All visible strings via translation keys. No hardcoded English in JSX. |
| Voice UI | Native Web Speech API (browser) + WebRTC for streaming | — | STT/TTS wrappers in `frontend/src/lib/voice/`. |
| FE testing | **Vitest** + **React Testing Library** (component/unit); **Playwright** (E2E) | MIT | `pnpm test` = Vitest+RTL (components/hooks); `pnpm e2e` = Playwright. Coverage target: 60% on `frontend/src/features/`. Playwright smoke-on-PR, full suite nightly. |
| API types | **openapi-typescript** (generated from FastAPI OpenAPI) | MIT | `frontend/src/lib/api/schema.d.ts` generated from `/openapi.json`; feature `types.ts` re-exports from it. Hand-mirrored request/response types forbidden (see AMENDMENTS A-002). Regenerated in CI; drift fails the build. |

**Forbidden:** Material UI, Chakra UI, Ant Design, Bootstrap, plain CSS modules, styled-components, Redux, MobX, Recoil, Jotai, react-query (use TanStack Query v5).

---

## 3. Database & Storage

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Primary DB | **PostgreSQL 16** | PostgreSQL License | Self-hosted on the VM. |
| ORM | **SQLAlchemy 2.0** (async) | MIT | `AsyncSession` everywhere. No sync sessions. |
| Migrations | **Alembic** | MIT | Every schema change has a migration. No manual SQL in code. |
| Connection pooling | **PgBouncer** (transaction mode) in front of Postgres | ISC | Required for production. |
| Object storage | **MinIO** (S3-compatible) | AGPL-3.0 | Self-hosted. Buckets: `pdfs/`, `audio/`, `ml-models/`, `exports/`. AGPL accepted by @abdurrehman. |
| File access in app | **boto3** with custom endpoint pointing to MinIO | Apache-2.0 | Same code works against AWS S3 if ever needed. |
| Cache | **Redis 7** | BSD-3 | Single instance, used for: cache, Celery broker, Redis pub/sub, ephemeral session data. |
| Vector store | **Qdrant** (latest stable) | Apache-2.0 | Self-hosted single binary. Collections per knowledge type (curriculum, reference_books, lectures, student_uploads). |

**Forbidden:** SQLite (any environment), MySQL, MongoDB, Milvus, Pinecone, Weaviate, Chroma, FAISS, pgvector (we use Qdrant instead).

---

## 4. AI / LLM Layer

### 4.1 LLM serving (abstracted, env-var switchable)

All LLM calls go through `app/services/llm/client.py`. The client speaks OpenAI-compatible API and routes to a provider based on env vars.

| Env var | Purpose |
|---|---|
| `LLM_PROVIDER` | One of: `vllm`, `groq`, `openai`, `anthropic`, `ollama` |
| `LLM_BASE_URL` | Provider endpoint |
| `LLM_API_KEY` | Provider key |
| `LLM_MODEL` | Model identifier |
| `LLM_FALLBACK_PROVIDER` | Provider for fallback on failure |
| `LLM_FALLBACK_BASE_URL` | Fallback endpoint |
| `LLM_FALLBACK_API_KEY` | Fallback key |
| `LLM_FALLBACK_MODEL` | Fallback model |
| `LECTURE_GEN_MODEL` | Override for lecture generation (optional) |
| `CHATBOT_MODEL` | Override for chatbot (optional) |
| `STUDENT_QA_MODEL` | Override for student Q&A (optional) |
| `VA_MODEL` | Override for virtual assistant (optional) |
| `SCORING_MODEL` | Override for lecture scoring (optional) |

**Default at launch:** `LLM_PROVIDER=groq` (no GPU on VM at launch).
**Future state:** When GPU is provisioned, swap to `LLM_PROVIDER=vllm` with no code change.

**Locked client library:** `openai` Python SDK (≥1.0). It's the SDK; all providers above expose OpenAI-compatible endpoints. **Not used as "OpenAI as a provider"** — used as the client library that speaks the OpenAI API protocol.

| Concern | Locked Choice | License |
|---|---|---|
| LLM client | **openai** SDK ≥1.0 (as OpenAI-compatible client) | Apache-2.0 |
| Local LLM server (when GPU available) | **vLLM** | Apache-2.0 |
| Dev/local model serving | **Ollama** | MIT |

**Forbidden:** direct use of `anthropic`, `groq`, `cohere`, `mistralai` Python SDKs anywhere outside `app/services/llm/`. Anywhere else, import from the LLM abstraction.

### 4.2 Orchestration

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Graph / state workflows | **LangGraph** | MIT | Used for: lecture generation pipeline, next-day review pipeline, recovery bundle pipeline, any multi-step LLM flow with branching. |
| Typed agents with tools | **Pydantic AI** | MIT | Used for: chatbot, virtual assistant, agentic RAG surfaces (student self-study, complex Q&A), guess-detection LLM classifiers, error-type classifiers. |
| Structured outputs | **Pydantic v2** models passed to LangGraph nodes and Pydantic AI agents | MIT | Never parse LLM output by regex or string split. Always `response_model=PydanticModel`. |

**When to use which:**
- If the flow has explicit ordered steps and conditional branching → **LangGraph**
- If the flow is "agent decides which tool to call" → **Pydantic AI**
- If unsure → **LangGraph** (more predictable, easier to debug)

**Forbidden:** LangChain (any module — use LangGraph + Pydantic AI), LlamaIndex, Haystack, CrewAI, AutoGen, semantic-kernel.

### 4.3 RAG pipeline

| Stage | Locked Choice | License | Notes |
|---|---|---|---|
| Embeddings (multilingual) | **BGE-M3** via **Infinity** server | MIT (model) / MIT (server) | ONNX-optimized, runs on CPU. Languages: Urdu, Sindhi, Pashto, English, 100+ others. |
| Reranker | **bge-reranker-v2-m3** via Infinity | MIT | Top-50 retrieval → rerank → top-5. CPU-acceptable. |
| Sparse retrieval | **Qdrant hybrid mode** (BGE-M3 sparse output) | Apache-2.0 | No separate BM25 engine. |
| Vector retrieval | **Qdrant hybrid mode** (BGE-M3 dense output) | Apache-2.0 | Same instance as sparse. |
| Chunking | **LangChain RecursiveCharacterTextSplitter** | MIT | **DEVIATION pre-approved:** used only in `app/services/ingestion/chunker.py`. No other LangChain imports anywhere else in the codebase. |
| PDF text + tables + images | **MinerU** | Apache-2.0 | Deep-learning-based, handles equations, multilingual. Primary extractor for curriculum + reference books. |
| PDF lightweight fallback | **pdfplumber** | MIT | Simple typed PDFs only. |
| OCR (primary) | **PaddleOCR** | Apache-2.0 | Multilingual including Urdu. State-of-the-art OSS 2026. |
| OCR (fallback) | **Tesseract 5** | Apache-2.0 | For simple typed text only. |
| DOCX | **python-docx** + **docx2txt** | MIT | |
| PPTX | **python-pptx** | MIT | |

**RAG pattern (standard, used for: lecture gen, mini-lecture gen, lecture Q&A):**
1. Query → BGE-M3 embed (dense + sparse)
2. Qdrant hybrid search → top 50
3. bge-reranker-v2-m3 → top 5
4. Assemble context with source tags
5. LLM generation with citation enforcement

**RAG pattern (agentic, used for: chatbot, VA, student self-study, recovery bundle):**
Same as standard, but wrapped in a Pydantic AI agent with tools: `search_curriculum`, `search_reference_books`, `search_lectures`, `web_search` (3rd tier), `lookup_concept`, `traverse_knowledge_graph`.

### 4.4 Speech

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| STT (primary) | **faster-whisper** with `whisper-large-v3` | MIT | GPU when available, CPU `medium` model otherwise. |
| STT (CPU fallback) | **whisper.cpp** | MIT | For edge cases or batch jobs. |
| TTS — English & Urdu | **Piper TTS** | MIT | Fast, self-hosted, CPU. |
| TTS — Pashto | **Edge-TTS** | MIT (client lib) | Microsoft public endpoint. Free, unsupported. Afghan accent — flag to product. |
| TTS — Sindhi | **AI4Bharat Indic-TTS** | Apache-2.0 | Self-hosted, slower on CPU. |
| Voice routing | `app/services/voice/router.py` | — | Language detection → provider routing. Single abstraction. |

**Forbidden:** ElevenLabs, OpenAI TTS, Google Cloud TTS, AWS Polly, Coqui XTTS (license issue), F5-TTS (non-commercial), MeloTTS (no Urdu/Sindhi/Pashto).

### 4.5 ML (pass probability, cognitive DNA, etc.)

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| ML framework (Phase 2+) | **scikit-learn** + **XGBoost** | BSD-3 / Apache-2.0 | For pass probability, predicted marks, guess detection. |
| Model interpretability | **SHAP** | MIT | For causal topic analysis. |
| Spaced repetition | **py-fsrs** (FSRS algorithm) | MIT | Replaces SM-2. Personalized forgetting curves. |
| Job scheduling for ML | Celery beat | BSD-3 | Nightly retraining, prediction recalculation. |
| Model storage | MinIO bucket `ml-models/` | — | Models loaded into memory on app startup. |

**Phase 1 (v2 launch through first 6 months):**
Heuristic formulas only — no trained models. Live in `app/services/ml/heuristic/`. Same API contract as future ML models will expose, so swap is zero-caller-change.

**TODO (logged here, not forgotten):**
- [ ] Build `app/services/ml/heuristic/pass_probability.py` — weighted formula
- [ ] Build `app/services/ml/heuristic/cognitive_dna.py` — aggregated heuristics
- [ ] Build `app/services/ml/heuristic/predicted_marks.py` — regression-shaped heuristic
- [ ] Build `app/services/ml/heuristic/guess_detection.py` — threshold-based
- [ ] Build same-shape API endpoints in `app/routes/predictions.py`
- [ ] Build `app/services/ml/training/` skeleton (empty modules, real implementations in Phase 2)
- [ ] Build `app/services/ml/features/` for feature extraction logic
- [ ] Build Celery beat job `app/tasks/ml_tasks.py:recalculate_predictions_nightly`
- [ ] Build Celery beat job `app/tasks/ml_tasks.py:retrain_models_weekly` (stub for Phase 1)
- [ ] Document the contract in `docs/ARCHITECTURE.md` so the API never changes when we swap heuristic → trained model

**Forbidden in Phase 1:** any trained model file. Heuristic only.

---

## 5. Infrastructure

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| OS | Ubuntu 24.04 LTS | — | Single VM, 16 vCPU / 64 GB RAM at launch. |
| Reverse proxy | **nginx** (on host, **not** in container) | BSD-2 | HTTPS termination, rate limiting, static asset serving. Installed via apt. Sits in front of all containers. |
| TLS | **Let's Encrypt** via certbot (on host) | — | Auto-renewal cron. Certs live at `/etc/letsencrypt/`. |
| Process orchestration | **docker-compose** | Apache-2.0 | Every service except nginx runs in a container. See "Compose file layout" below. |
| Container runtime | **Docker Engine** | Apache-2.0 | Installed on the VM via official Docker repo. |
| Event streaming | **NATS JetStream** | Apache-2.0 | Single binary. Durable streams + KV + object store. Runs as a compose service. |
| Job queue | **Celery 5** + **Redis** broker | BSD-3 | Workers and beat scheduler run as separate compose services using the same app image with different commands. |
| Real-time transport | FastAPI native **WebSockets** + **Redis pub/sub** for cross-worker | — | No Socket.io, no Pusher. |
| Auth | **Authentik** (self-hosted IDP) | MIT | From day 1. OIDC. Runs as a compose service with its own Postgres DB. |
| Auth in FastAPI | **authlib** for OIDC client | BSD-3 | Talks to Authentik via OIDC. |
| Embeddings server | **Infinity** | MIT | Serves BGE-M3 + bge-reranker-v2-m3. Runs as a compose service. CPU-optimized via ONNX. |

**Forbidden:** Kubernetes (any flavor), Helm, Istio, AWS-specific services (use S3-compatible only), Kafka, Zookeeper, RabbitMQ, systemd unit files for any of the above services.

### Compose file layout (locked)

The repo uses **ONE `docker-compose.yml` at the repo root**. All services in one file. Dev defaults built in (hot-reload, source mounts on `api/` and `frontend/`).

**Startup (dev or staging or production):**
```bash
docker compose up -d
```

**Rules:**
- All services share a single bridge network defined inside `docker-compose.yml`.
- Named volumes for all persistent data: `pg_data`, `qdrant_data`, `minio_data`, `redis_data`, `nats_data`, `authentik_data`, `prometheus_data`, `loki_data`, `grafana_data`, `sentry_data`.
- nginx on the host proxies to `127.0.0.1:<published_port>` for each exposed compose service. Only nginx-exposed ports are published; internal services bind only to the compose network.
- Dev vs staging vs production differ only via env vars in the single `.env` file at the repo root. The compose definitions themselves are identical across environments.
- A `docker-compose.prod.yml` override file is **deferred** until the first VM deployment (post-M-23). Until then, one file handles everything.
- **No `Makefile`.** Raw `docker compose` commands are the operator interface.

---

## 6. External APIs (env-gated, optional)

These are external services. The application must work without them — degrade gracefully when their env vars are absent.

| Service | Locked Choice | Env vars | Notes |
|---|---|---|---|
| SMS | **Jazz** + **Telenor** direct APIs | `SMS_PROVIDER`, `SMS_API_URL`, `SMS_API_KEY`, `SMS_SENDER_ID` | If env vars missing → SMS code path is bypassed silently. Full integration logic implemented regardless. |
| Email | **Brevo** free tier (default), with Resend + Mailgun as alternates | `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM` | `EMAIL_PROVIDER` accepts `brevo`/`resend`/`mailgun`. Abstraction in `app/services/notifications/email.py`. |
| Push notifications | **Firebase Cloud Messaging (FCM)** | `FCM_SERVER_KEY`, `FCM_PROJECT_ID` | Web + mobile push. |
| Web search (RAG tier 3 fallback) | **SearXNG** (self-hosted) | `WEBSEARCH_URL` | Self-hosted meta-search engine. AGPL-3.0. |

**Forbidden as managed-service dependencies:** Twilio, SendGrid (paid tier), Pinecone, Vercel hosting, Auth0, Clerk, Supabase, Firebase Auth/Firestore (FCM only is allowed), AWS managed services, GCP managed services.

---

## 7. Observability

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Metrics | **Prometheus** + **prometheus-fastapi-instrumentator** | Apache-2.0 / MIT | All routes auto-instrumented. |
| Dashboards | **Grafana** (self-hosted) | AGPL-3.0 | Postgres-backed Grafana DB. |
| Logs | **Loki** + **promtail** | AGPL-3.0 | Structured JSON logs from all services. |
| Tracing | **OpenTelemetry** SDK + **Tempo** | Apache-2.0 / AGPL-3.0 | Traces in Grafana. |
| Error tracking | **Sentry** (self-hosted, OSS edition) | BSL (free for self-host) | Frontend + backend SDKs. |
| Structured logging | **structlog** | Apache-2.0/MIT | Every log is JSON. No `print()`. No raw `logger.info("user %s", id)` — use kwargs. |
| Log PII scrubbing | Custom filter in `app/utils/logging.py` | — | Scrub email, phone, name from logs before write. |

**Forbidden:** Datadog, New Relic, Splunk, AppDynamics, paper-print debugging.

---

## 8. Development tooling

| Concern | Locked Choice | License | Notes |
|---|---|---|---|
| Pre-commit framework | **pre-commit** | MIT | `.pre-commit-config.yaml` at repo root. |
| Git hooks | ruff, mypy, custom `check_imports.py`, custom `check_envvars.py`, custom `check_stack_lock.py`, custom `update_ticket_status.py` (post-commit ledger writer), pytest collect-only, conventional-commits check | — | All enforced locally + in CI. Ticket-status also verified at PR time by `check_ticket_status.py`. |
| CI | **GitHub Actions** (free tier on private repo) | — | 2000 minutes/month sufficient. |
| Commit convention | **Conventional Commits** | — | `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`. Stack-touching commits must include `## Stack-touching` section. |
| Branching | trunk-based with feature branches | — | Base: `staging`. Feature branches: `feature/<phase>-<name>`. |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` | — | Auto-filled by `phase-complete-review` skill. |
| Skills | `.claude/skills/` | — | `stack-enforcer`, `frontend-master`, `phase-complete-review`. |

### Pinned tool versions (single source of truth)

Lint/format/type tools are pinned to ONE version each, used identically in `.pre-commit-config.yaml`, `pyproject.toml` (`uv run`), and CI. This alignment is mandatory (CLAUDE.md CI invariant 6) — drift causes the write→CI-fail→reformat loop.

| Tool | Pinned version | Config home | Used by |
|---|---|---|---|
| ruff (lint + format) | **0.6.9** | `[tool.ruff]` in `pyproject.toml` (authoritative rules) | pre-commit, `uv run ruff`, CI |
| mypy (strict) | **1.11.2** | `[tool.mypy]` in `pyproject.toml` | pre-commit, `uv run mypy`, CI |
| prettier | **mirrors-prettier v4.0.0-alpha.8** (frontend) | `frontend/.prettierrc` | pre-commit, `pnpm format`, CI |
| pre-commit framework | per `.pre-commit-config.yaml` | repo root | local + CI (`pre-commit run`) |

**Canonical ruff config** (`[tool.ruff]`): `line-length = 100`, double quotes, isort with first-party `app`, the rule set declared in `pyproject.toml`. When bumping any version, bump it in all three locations in the same PR.

---

## 9. Forbidden imports (machine-enforced)

The script `scripts/check_stack_lock.py` runs in pre-commit and CI. It rejects any commit/PR that imports from this list anywhere except files listed in `docs/DEVIATIONS.md`.

```
# Old/legacy
langchain          # use langgraph + pydantic-ai
faiss              # use qdrant
pymilvus           # use qdrant
flask              # use fastapi
sqlite3            # use postgres
aiosqlite          # use postgres
requests           # use httpx

# Wrong vector stores
chromadb
weaviate-client
pinecone
pgvector

# Wrong LLM clients (use the abstraction)
anthropic          # except in app/services/llm/
groq               # except in app/services/llm/
mistralai          # except in app/services/llm/
cohere             # except in app/services/llm/

# Wrong frameworks
llama-index
haystack
crewai
autogen
semantic-kernel

# Wrong TTS
elevenlabs
TTS                # Coqui
melo

# Wrong SR algorithms
sm2
supermemo

# Wrong observability
datadog
newrelic

# Wrong auth
auth0
clerk
supabase

# Sync stuff in async codebase
celery.task        # use shared_task only
```

**Soft-warned (allowed in specific paths only):**

```
pandas             # only in app/services/ml/, app/tasks/ml_tasks.py
numpy              # only in app/services/ml/, app/services/rag/
scikit-learn       # only in app/services/ml/
xgboost            # only in app/services/ml/
shap               # only in app/services/ml/
langchain.text_splitter  # only in app/services/ingestion/chunker.py (pre-approved deviation)
```

---

## 10. Decisions deferred to ARCHITECTURE.md

These are real decisions but they're *design decisions* not *stack decisions* — they belong in `ARCHITECTURE.md`. Listed here so they're not forgotten:

- [x] Multi-tenancy data isolation strategy — **RESOLVED:** dual Postgres schemas + 3-layer defense (router dep → repo filter → RLS) per ARCH §3.16 (AMENDMENTS A-001 #13).
- [ ] Database connection pooling sizing — **DEFER · owner: Abd. · resolve-before pilot** (PgBouncer locked; only sizing numbers are tuning).
- [ ] Qdrant collection design — **NEEDS-TRIAGE · owner: Abd. · resolve-before M-09** (first heavy RAG retrieval milestone).
- [x] Chunking strategy — **RESOLVED:** `RecursiveCharacterTextSplitter` (DEVIATIONS `langchain.text_splitter`) + sizes/overlap per ARCH §7.
- [ ] Embedding cache strategy — **DEFER · owner: Abd. · resolve-before pilot.**
- [ ] Real-time event topic taxonomy in NATS — **DEFER · owner: Abd. · resolve-before M-12** (first real-time milestone).
- [ ] WebSocket connection lifecycle (auth, reconnect, heartbeat) — **DEFER · owner: Abd. · resolve-before M-12.**
- [x] File upload pipeline — **RESOLVED (owner: Abd.):** presigned **direct-to-MinIO** (browser→MinIO via presigned PUT; API issues the presigned URL + records metadata). No large-file proxying through FastAPI.
- [ ] Background job priority tiers (Celery queues) — **DEFER · owner: Abd. · resolve-before M-14** (load/event pipeline).
- [x] API versioning strategy — **RESOLVED (owner: Abd.):** URL-prefix `/api/v1` (already in use across M-00/M-01); breaking changes → `/api/v2`.
- [x] Frontend folder structure — **RESOLVED:** feature-based (`frontend/src/features/<feature>/` with components/hooks/api.ts/types.ts) per ARCH §12.
- [x] Design tokens specification — **RESOLVED (owner: Abd.):** tokens in `tailwind.config.ts` (colors, spacing, radius, typography scale); formalized + shadcn base set wired in M-01a. No inline styles / ad-hoc hex.
- [x] i18n key structure and translation workflow — **RESOLVED (owner: Abd.):** next-intl namespaced keys `<feature>.<area>.<key>`; en source, ur/sd/ps translation files; no hardcoded JSX strings (CI-checked). Convention doc in M-01a.
- [x] Audit log schema — **RESOLVED:** built M-01 T-025 + ARCH §14.10.
- [ ] PII handling for Pakistan PDPB 2025 compliance — **DEFER · owner: Abd. · resolve-before pilot** (minors' data; pre-pilot legal gate).
- [ ] Rate limiting strategy per role — **DEFER · owner: Abd. · resolve-before pilot.**
- [ ] Backup and restore procedures — **DEFER · owner: Abd. · resolve-before pilot.**

---

## 11. License acceptance log

By using this stack, the project accepts the following non-permissive licenses:

| License | Components | Approved by | Date |
|---|---|---|---|
| AGPL-3.0 | MinIO, Grafana, Loki, Tempo, SearXNG, Authentik | @abdurrehman | 2026-05-11 |
| BSL | Sentry (self-hosted, free) | @abdurrehman | 2026-05-11 |

AGPL is acceptable because we don't modify and redistribute these components. We use them as services.

---

## 12. Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial lock | @abdurrehman (with Claude) |
| 2026-05-11 | Switched process orchestration from systemd to docker-compose for everything except nginx. Locked three-file compose layout (`infra` / `app` / `override`). | @abdurrehman (with Claude) |
| 2026-05-14 | T0 batch spec-set confirmations (no stack changes, just affirmations of existing locks against spec-set decisions): (1) TTS path confirmed self-hosted Piper + Edge-TTS fallback + AI4Bharat for sd/ps — no ElevenLabs / no paid TTS at launch. (2) Subscription module is schema-only at launch; no Stripe SDK installed; placeholder env vars only (per Flow 13 + ARCH §3.17 + §11.20). (3) Authentik remains single IDP for BOTH school and independent tenants; property mapper sets `tenant_type` JWT claim (per ARCH §3.16 + §6.20). (4) Postgres remains single DB instance with dual schemas (`school` and `independent`); dual Alembic heads (per ARCH §4.21). | @abdurrehman (with Claude) |

Future changes require a PR to this file, reviewed by @abdurrehman.

---

**End of STACK_LOCK.md. Anything not in this file requires a documented deviation in `docs/DEVIATIONS.md`.**
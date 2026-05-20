# Runbook: local dev setup

**Use this when:** you want a working local IqbalAI stack on your laptop.

**Time:** ~30 minutes for a clean machine, assuming M-00 has been merged.

**OS coverage:** macOS, Linux. Windows users use WSL2.

---

## ⚠ Before you read further

This runbook **assumes M-00 Foundation has been merged to `staging`**. M-00 is the milestone that creates the actual `docker-compose.yml`, `.env.example`, `api/`, `frontend/` and the entire scaffolding this runbook references.

**If M-00 has NOT been merged yet:**

1. There is nothing to set up locally.
2. Open `docs/backlog/M-00-foundation.md` and implement the tickets ticket-by-ticket per `docs/WORKFLOW.md`.
3. Once M-00 ships (PR merged to `staging`), come back to this runbook.

**To check if M-00 has shipped:** look for the existence of `docker-compose.yml` at the repo root. If it's there, M-00 is done. If it's not, you're pre-M-00.

---

## Phase 1 — Install prerequisites (skip what you have)

### Required

- **Git** ≥ 2.40
- **Docker Desktop** (macOS, Windows) or **Docker Engine + Compose plugin** (Linux). Verify with `docker compose version` (note: space, not hyphen — Compose v2 is required).
- **Node.js** ≥ 20.x — needed for the frontend toolchain (Next.js)
- **pnpm** ≥ 9.x — `npm install -g pnpm` after Node is in place
- **Python** ≥ 3.12 — needed for some scripts and local API debugging (the containers don't need it on your host, but it's helpful)
- **uv** (fast Python package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Recommended

- An editor with TypeScript and Python support. VSCode, Cursor, or Zed.
- `gh` (GitHub CLI) for PRs from the terminal: `brew install gh` or [cli.github.com](https://cli.github.com).

### NOT needed

- `make` — we don't use a Makefile. Raw `docker compose` commands only.
- A separate Postgres / Redis / NATS install — all services run as containers.

---

## Phase 2 — Clone the repo

```bash
git clone https://github.com/abdurrehman-tahir/iqbalai-v2.git
cd iqbalai-v2
git checkout staging   # always work off staging
```

---

## Phase 3 — Create your local `.env`

```bash
cp .env.example .env
```

Open `.env` in your editor. For local dev, the defaults in `.env.example` should work out of the box — they're tuned for the compose stack on `localhost`. The only thing you may need to adjust:

- **LLM provider keys.** If you want the AI features to actually respond (not just be stubbed), fill in `GROQ_API_KEY` and/or `OPENAI_API_KEY`. Without them, RAG endpoints return a clear "no provider configured" error but the rest of the stack works.
- **`AUTHENTIK_BOOTSTRAP_PASSWORD`** — set this to anything you'll remember. You'll use it once to log into Authentik admin and create the OIDC client; subsequent logins use that.

Everything else can stay at defaults for local work.

`.env` is gitignored. Never commit it.

---

## Phase 4 — Bring up the stack

ONE command brings everything up:

```bash
docker compose up -d
```

This pulls the images for Postgres, Redis, NATS, MinIO, Qdrant, Authentik, Infinity (embeddings), Grafana, Prometheus, and builds the local images for the `api` and `frontend` services.

First run takes 5–10 minutes depending on your network. Subsequent runs take 10–30 seconds.

### Check that everything is healthy

```bash
docker compose ps
```

Every service should show `healthy` or `running` after about 60 seconds. If something's `unhealthy`, check its logs:

```bash
docker compose logs --tail=50 <service-name>
```

---

## Phase 5 — Run migrations

```bash
docker compose exec api alembic upgrade head
```

This applies both the `school` and `independent` schema migrations (dual Alembic heads per ARCH §4.21).

You'll see Alembic output for each migration as it runs. If you see errors mentioning "schema does not exist", the Postgres init script in M-00 T-003 hasn't been merged yet — check the M-00 progress.

---

## Phase 6 — Bootstrap Authentik (one-time)

The first time you bring up the stack, Authentik needs initial configuration:

```bash
docker compose exec authentik-server ak shell -c "
from authentik.flows.models import Flow
print('Authentik ready' if Flow.objects.exists() else 'Setup needed')
"
```

If it says "Setup needed", open `http://localhost:9000/if/flow/initial-setup/` in your browser. Use the email `admin@localhost` and the password from `AUTHENTIK_BOOTSTRAP_PASSWORD` in your `.env`.

Then run the bootstrap script that creates the OIDC client for IqbalAI:

```bash
docker compose exec api python scripts/bootstrap_authentik.py
```

This is documented in detail in `docs/runbooks/authentik-bootstrap.md` (stub at launch, fills in as we discover edge cases).

---

## Phase 7 — Open the app

| What | URL |
|---|---|
| Frontend (Next.js) | `http://localhost:3000` |
| API (FastAPI docs) | `http://localhost:8000/docs` |
| API health check | `http://localhost:8000/api/v1/health/ready` |
| Authentik admin | `http://localhost:9000` |
| Grafana | `http://localhost:3001` (admin/admin first login) |
| MinIO console | `http://localhost:9001` |
| Qdrant dashboard | `http://localhost:6333/dashboard` |

---

## The 4 commands you'll use daily

```bash
docker compose up -d                         # start everything
docker compose down                          # stop everything (keeps data)
docker compose logs --tail=100 -f api        # follow api logs
docker compose exec api bash                 # shell into the api container
```

That's it. Memorize these four.

---

## Common operations

### Restart one service after a code change

If you've edited `api/` code, the volume mount + `uvicorn --reload` should pick it up automatically. If something seems stuck:

```bash
docker compose restart api
```

For frontend changes, Next.js dev server hot-reloads. If not, `docker compose restart frontend`.

### Run a one-off command (migration, script, etc.)

```bash
docker compose exec api alembic upgrade head           # run pending migrations
docker compose exec api alembic revision -m "name"     # create a new migration
docker compose exec api python -m pytest tests/        # run backend tests
docker compose exec frontend pnpm test                 # run frontend tests
```

### Reset the database (nuclear option)

```bash
docker compose down -v        # stop + remove ALL volumes (data lost)
docker compose up -d
docker compose exec api alembic upgrade head
```

Use this when migrations get into a weird state during development. Never run `down -v` on staging or production.

### Free up disk space

```bash
docker compose down
docker system prune -a --volumes        # removes unused images + volumes
```

---

## Troubleshooting

**`docker compose up -d` says "port already in use"**
Another process is using port 5432 (Postgres), 6379 (Redis), 8000 (api), or 3000 (frontend). Either stop the other process or edit the port mappings in `docker-compose.yml` (but commit nothing).

**Frontend can't reach API ("CORS error" or "Network error")**
Check `NEXT_PUBLIC_API_URL` in `.env` — it should be `http://localhost:8000` for local dev. The frontend reads `NEXT_PUBLIC_*` vars at build time, so if you change one, `docker compose restart frontend` to rebuild.

**API container crashes on startup**
99% of the time: `.env` is missing a required var. Compare to `.env.example` and check every uncommented line is filled. The startup logs will name the missing var (the API uses Pydantic Settings which fails loudly).

**Postgres won't accept connections**
First wait 60 seconds — Postgres initializes its data dir on first run. If still failing after a minute: `docker compose logs postgres` and look for errors. Most common: corrupted volume from a previous broken run — fix with `docker compose down -v && docker compose up -d`.

**Authentik OIDC isn't working**
Re-run the bootstrap script: `docker compose exec api python scripts/bootstrap_authentik.py`. If it's idempotent (it should be after M-00 T-006) this is safe.

**Embeddings (Infinity) is slow on first request**
First request to Infinity downloads the BGE-M3 model (~2GB). Subsequent requests are fast. Pre-warm on dev with: `curl http://localhost:7997/embeddings -X POST -H 'content-type: application/json' -d '{"input":["warmup"],"model":"BAAI/bge-m3"}'`.

**I want to skip the heavy services for fast iteration**
Bring up only what you need:
```bash
docker compose up -d postgres redis api frontend     # skip NATS, Qdrant, embeddings, Authentik
```
Some features will fail (RAG, auth, events) but for pure CRUD work this is fast.

---

## Where this runbook is incomplete

This runbook reflects the M-00 baseline. As later milestones land, additional setup may be required:

- **M-06+ (Authentik flows for invite vs self-signup):** Authentik bootstrap script gets richer — covered when M-06 ships.
- **M-09+ (Lecture pipeline):** may require pre-warming Qdrant indices — covered when M-09 ships.

When a milestone adds new local-dev steps, this runbook MUST be updated as part of that milestone's PR (per `WORKFLOW.md` Step 2).

---

## See also

- `docs/HAMZA_START_HERE.md` — overall onboarding flow
- `docs/WORKFLOW.md` — how features get built
- `docs/backlog/M-00-foundation.md` — the milestone that bootstraps everything
- `docs/runbooks/postgres-down.md` — when Postgres is misbehaving
- `docs/runbooks/authentik-down.md` — when Authentik is misbehaving

---

**Last updated:** 2026-05-20 (rewritten for milestone workflow + single-compose-file simplification)

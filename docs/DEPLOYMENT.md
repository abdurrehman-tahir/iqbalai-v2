# Production deployment — 69.28.84.37

End-to-end runbook for a fresh server. Every command is run as root from the repo
root on the server unless stated otherwise.

The deploy is **two phases** and it cannot be collapsed into one. Authentik must be
running before it can mint an OIDC client ID, and that client ID is compiled into the
frontend bundle at *build* time (`NEXT_PUBLIC_*` are inlined by Next.js, not read at
container start). So: bring the stack up → configure Authentik → rebuild the frontend
with the real client ID.

---

## 0. Server prep (once)

```bash
# Docker Engine + compose plugin (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh

# Firewall: only SSH + the two public ports. Postgres/Redis/Qdrant/MinIO are NOT
# published to the host by docker-compose.prod.yml, but a firewall is still the
# backstop that keeps a future misconfiguration from exposing them.
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 9000/tcp   # Authentik (the browser is redirected here to log in)
ufw --force enable

docker --version && docker compose version
```

## 1. Get the code and the env file

```bash
git clone <your-repo-url> iqbalai-v2
cd iqbalai-v2

cp .env.prod.example .env.prod
chmod 600 .env.prod

# Generate the four secrets and paste them in:
openssl rand -hex 32   # AUTHENTIK_SECRET_KEY
openssl rand -hex 16   # POSTGRES_PASSWORD   (keep it alphanumeric)
openssl rand -hex 16   # REDIS_PASSWORD      (keep it alphanumeric)
openssl rand -hex 16   # MINIO_PASSWORD      (keep it alphanumeric)

nano .env.prod
```

Filling in `.env.prod` — the parts that actually break things:

| Field | Rule |
|---|---|
| `POSTGRES_PASSWORD` | Must also appear verbatim inside `DB_URL`. |
| `REDIS_PASSWORD` | Must also appear verbatim inside `REDIS_URL`. Alphanumeric only — a raw `@`, `:`, `/` or `#` corrupts the URL. |
| `MINIO_ROOT_PASSWORD` | Must equal `MINIO_SECRET_KEY` (same credential, two names). |
| `NEXT_PUBLIC_*` | Must use `69.28.84.37`, never `localhost` — they run in the *user's* browser. |
| `NEXT_PUBLIC_AUTHENTIK_CLIENT_ID` | Set to `placeholder` for now; you get the real value in step 3. |
| `LLM_API_KEY` | Your real Groq/OpenAI key. |

## 2. First boot

```bash
./scripts/deploy.sh
```

This validates the compose file, builds both images, starts the data stores, creates
the MinIO buckets, runs `alembic upgrade heads`, then starts the app behind nginx.
First run pulls ~2 GB of embedding weights for Infinity, so give it time.

Check it:

```bash
curl -s http://69.28.84.37/api/v1/health     # -> {"status":"ok"}
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

The app answers on `http://69.28.84.37` but **login will not work yet** — that's step 3.

## 3. Configure Authentik (once, via the UI)

Open **http://69.28.84.37:9000** and sign in as `akadmin` with the
`AUTHENTIK_BOOTSTRAP_PASSWORD` from `.env.prod`. (If it asks you to set the password
instead, use `http://69.28.84.37:9000/if/flow/initial-setup/`.)

**3a. Create the provider** — *Admin interface → Applications → Providers → Create →
OAuth2/OpenID Provider*:

| Setting | Value | Why |
|---|---|---|
| Name | `iqbalai-frontend` | — |
| Authorization flow | `default-provider-authorization-explicit-consent` | Either flow works. |
| **Client type** | **Public** | The browser exchanges the code with **no client secret** (`OidcCallbackClient.tsx`). A *Confidential* provider rejects that exchange with a 401. |
| **Signing Key** | **`authentik Self-signed Certificate`** | Without a signing key Authentik issues **HS256** tokens and publishes an empty JWKS. The API only accepts **RS256** (`api/app/core/security.py`), so every request would 401 with `no_matching_signing_key`. This is the single most common cause of "login works but the API rejects me". |
| Redirect URIs (strict) | `http://69.28.84.37/auth/callback`<br>`http://69.28.84.37/login` | First is the OIDC callback; second is where logout returns. |
| Scopes | `openid`, `profile`, `email` | Exactly what `getLoginUrl()` requests. |

**3b. Create the application** — *Applications → Applications → Create*:

| Setting | Value |
|---|---|
| Name | `IqbalAI` |
| **Slug** | **`iqbalai-frontend`** |
| Provider | the provider from 3a |

> The slug is **not** a free label. `getLogoutUrl()` hardcodes
> `/application/o/iqbalai-frontend/end-session/`, and the slug is what forms
> `OIDC_JWKS_URL`. A different slug breaks logout and JWT validation.

**3c. Copy the Client ID** — reopen the provider; copy the generated **Client ID**.

**3d. Mint the API token** (used by the API for invite/user management):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -T authentik-server ak shell < scripts/create_authentik_api_token.py
```

Copy the printed token.

## 4. Second phase — bake in the real client ID

Put both values into `.env.prod`:

```
NEXT_PUBLIC_AUTHENTIK_CLIENT_ID=<client id from 3c>
OIDC_CLIENT_ID=<same client id>
AUTHENTIK_API_TOKEN=<token from 3d>
```

Then rebuild the frontend (the client ID is compiled in) and restart the API (it
reads the token at start):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build frontend
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d frontend api
```

Log in at **http://69.28.84.37**.

---

## Everyday operations

All commands assume the alias:

```bash
alias dc='docker compose -f docker-compose.prod.yml --env-file .env.prod'
```

```bash
# Redeploy after a git pull (rebuilds, migrates, restarts what changed)
git pull && ./scripts/deploy.sh

# Logs
dc logs -f api
dc logs -f celery-worker
dc ps

# Migrations — note `heads`, plural (two branches: school + independent).
# `alembic upgrade head` fails with "Multiple heads are present".
dc run --rm migrate
dc run --rm --entrypoint alembic api current
dc run --rm --entrypoint alembic api heads

# Postgres shell / backup
dc exec postgres psql -U iqbalai -d iqbalai
dc exec -T postgres pg_dump -U iqbalai iqbalai | gzip > backup-$(date +%F).sql.gz

# Restart one service
dc restart api

# Full stop (volumes are preserved)
dc down
```

## Things that will bite you

- **Changing any `NEXT_PUBLIC_*` requires a rebuild, not a restart.** They are inlined
  into the browser bundle at build time. `dc restart frontend` will appear to do
  nothing. Run `dc build frontend && dc up -d frontend`.
- **`alembic upgrade head` is wrong for this repo.** `alembic.ini` declares two version
  branches (`school`, `independent`). Always `heads`.
- **The dev `docker-compose.yml` publishes Postgres (5432) and Redis (6379) on
  `0.0.0.0`.** On a public IP that is an internet-exposed database. Never run the dev
  compose file on this server — `docker-compose.prod.yml` publishes only nginx.
- **Infinity's first boot downloads ~2 GB** of BGE-M3 weights and needs ~4 GB RAM. If
  the server is memory-starved, set `EMBEDDING_PROVIDER=local` in `.env.prod` and stop
  the `infinity` service.
- **`init.sh` only runs on an empty `pg_data` volume.** If you ever recreate Postgres
  against an existing volume, the `authentik` database and the `school`/`independent`
  schemas will not be re-created. Re-apply by hand:
  ```bash
  dc exec -T postgres psql -U iqbalai -d iqbalai -c \
    "CREATE SCHEMA IF NOT EXISTS school; CREATE SCHEMA IF NOT EXISTS independent;"
  ```

## TLS

The stack currently serves plain HTTP because it is reached by raw IP, and public CAs
do not issue certificates for IP addresses. **OIDC access tokens cross the network in
the clear.** Before real users touch it, point a domain at `69.28.84.37` and terminate
TLS in nginx (Let's Encrypt / certbot), then update `APP_URL`, `CORS_ALLOWED_ORIGINS`
and every `NEXT_PUBLIC_*` to `https://<domain>` and rebuild the frontend.

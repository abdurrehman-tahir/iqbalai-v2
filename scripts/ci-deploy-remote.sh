#!/usr/bin/env bash
# Runs on the staging server after CI syncs application code.
# Rebuilds images, migrates DB, restarts app services.
# Never modifies .env.prod, compose, or nginx prod files.
set -euo pipefail

APP_DIR="${APP_DIR:-/root/iqbalai-v2}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
HEALTH_URL="${HEALTH_URL:-https://abcdef.iqbalai.com/api/v1/health}"

cd "$APP_DIR"

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod missing in $APP_DIR" >&2
  exit 1
fi
if [[ ! -f docker-compose.prod.yml ]]; then
  echo "ERROR: docker-compose.prod.yml missing in $APP_DIR" >&2
  exit 1
fi

echo "==> Validating compose"
$COMPOSE config --quiet

echo "==> Ensuring data stores + Authentik are up"
$COMPOSE up -d postgres redis minio qdrant authentik-redis authentik-server authentik-worker

echo "==> Waiting for Postgres"
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env.prod | cut -d= -f2)"
until $COMPOSE exec -T postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
  sleep 2
done

echo "==> Building api + frontend"
$COMPOSE build api frontend

echo "==> Running migrations (alembic upgrade heads)"
$COMPOSE run --rm migrate

echo "==> Restarting application services"
# Do not force infinity — this host uses EMBEDDING_PROVIDER=local.
$COMPOSE up -d api celery-worker celery-beat frontend nginx

echo "==> Health check"
ok=0
for _ in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "    API healthy at $HEALTH_URL"
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: API did not become healthy" >&2
  $COMPOSE ps
  $COMPOSE logs --tail=80 api || true
  exit 1
fi

echo "==> Deploy status"
$COMPOSE ps
echo "Deploy complete"

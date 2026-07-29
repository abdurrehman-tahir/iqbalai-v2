#!/usr/bin/env python3
"""Authentik OIDC bootstrap — verify the IqbalAI application/provider exists.

T-247 (ARCH §6.4): the OIDC application + provider are now provisioned
DECLARATIVELY by the blueprint at `infrastructure/authentik/blueprints/
iqbalai-oidc.yaml`, which docker-compose mounts into the Authentik server +
worker under /blueprints. Authentik auto-applies it on boot (idempotent), so
there is no longer any manual "create the OIDC app" step — this script is no
longer a stub that tells you to click through the admin UI.

What it does now: a read-only sanity check that the blueprint actually applied
(the `iqbalai` application + `iqbalai-api` provider are present). Safe to re-run.

Run (after `docker compose up`):
    docker compose exec api python scripts/bootstrap_authentik.py

Requires AUTHENTIK_API_TOKEN (equal to AUTHENTIK_BOOTSTRAP_TOKEN is the zero-step
path — see .env.example). Without it, the check is skipped with guidance rather
than failing, since a fresh dev box may not have wired the token yet.

UNVERIFIED end-to-end: written without a live Authentik available. The endpoints
used are Authentik's documented v3 admin API; confirm on first real run.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

import httpx  # noqa: E402
import structlog  # noqa: E402

from app.config import get_settings  # noqa: E402

logger = structlog.get_logger(__name__)

APPLICATION_SLUG = "iqbalai"
PROVIDER_NAME = "iqbalai-api"


def main() -> None:
    settings = get_settings()
    token = settings.AUTHENTIK_API_TOKEN
    if not token:
        logger.warning(
            "authentik_bootstrap_check_skipped",
            reason="AUTHENTIK_API_TOKEN unset",
            hint=(
                "Set AUTHENTIK_API_TOKEN (equal to AUTHENTIK_BOOTSTRAP_TOKEN) to verify. "
                "The blueprint still applies automatically regardless — this is only the check."
            ),
        )
        return

    base_url = settings.AUTHENTIK_API_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        app_resp = client.get(f"{base_url}/core/applications/", params={"slug": APPLICATION_SLUG})
        app_resp.raise_for_status()
        apps = app_resp.json().get("results", [])

        prov_resp = client.get(
            f"{base_url}/providers/oauth2/", params={"name": PROVIDER_NAME}
        )
        prov_resp.raise_for_status()
        providers = prov_resp.json().get("results", [])

    if apps and providers:
        logger.info(
            "authentik_bootstrap_ok",
            application_slug=APPLICATION_SLUG,
            provider_name=PROVIDER_NAME,
            client_id=providers[0].get("client_id"),
        )
        return

    logger.error(
        "authentik_bootstrap_missing",
        application_present=bool(apps),
        provider_present=bool(providers),
        hint=(
            "The OIDC blueprint has not applied. Check the authentik-worker logs for "
            "blueprint errors and that /blueprints/iqbalai/iqbalai-oidc.yaml is mounted."
        ),
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()

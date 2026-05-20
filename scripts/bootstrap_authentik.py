#!/usr/bin/env python3
"""
Authentik bootstrap script — configures the OIDC application for IqbalAI.

Run ONCE after first `docker compose up`:
    docker compose exec api python scripts/bootstrap_authentik.py

This script is idempotent — safe to re-run.

Implementation: stubbed for T-004. Full implementation added when M-01 Authentik
flows are built (invite vs self-signup paths).
"""
import sys


def main() -> None:
    """Bootstrap Authentik with IqbalAI OIDC configuration."""
    print("Authentik bootstrap: stub — full implementation in M-01.")
    print("For now, configure Authentik manually:")
    print("  1. Open http://localhost:9000/if/flow/initial-setup/")
    print("  2. Create OIDC application 'iqbalai-api'")
    print("  3. Set redirect URI to http://localhost:8000/api/v1/auth/callback")
    sys.exit(0)


if __name__ == "__main__":
    main()

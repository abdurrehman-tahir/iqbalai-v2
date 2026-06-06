"""Offline OpenAPI schema exporter.

Dumps the FastAPI OpenAPI document to stdout as JSON **without** starting a
server or touching the database / network: ``create_app()`` wires routes
synchronously and the lifespan (which connects to infra) only runs on a real
startup, so this is safe to run in CI with no services up.

Consumed by the frontend ``gen:api`` script (openapi-typescript) so the frontend
API types are *generated* from the backend contract, never hand-mirrored
(AMENDMENTS A-002).

Usage (from ``api/``)::

    uv run python -m app.openapi_export > ../frontend/openapi.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.main import create_app


def export_openapi() -> dict[str, Any]:
    """Build the app and return its OpenAPI document."""
    application = create_app()
    return application.openapi()


def main() -> None:
    # Write to stdout (not structlog — this is a data export, not app logging).
    # sort_keys keeps the generated schema.d.ts diff-stable across runs so the
    # typed-client-drift CI gate only fires on real contract changes.
    sys.stdout.write(json.dumps(export_openapi(), indent=2, sort_keys=True))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

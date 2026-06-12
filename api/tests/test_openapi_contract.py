"""OpenAPI contract tests (T-225).

Builds the real OpenAPI document (offline, no DB) and asserts the response-model
gate's intent holds at the schema level: every operation carries an operationId,
and the success routes advertise a typed `SuccessEnvelope[...]` (with a real
`data` shape) rather than a bare `dict`. This is what keeps the generated
frontend client (A-002) typed.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.openapi_export import export_openapi

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    return export_openapi()


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method in _HTTP_METHODS:
                out.append((method, path, op))
    return out


def test_every_operation_has_operation_id(openapi: dict[str, Any]) -> None:
    missing = [
        f"{method.upper()} {path}"
        for method, path, op in _operations(openapi)
        if "operationId" not in op
    ]
    assert missing == [], f"Operations missing operationId: {missing}"


def test_users_me_returns_typed_success_envelope(openapi: dict[str, Any]) -> None:
    op = openapi["paths"]["/api/v1/users/me"]["get"]
    assert op["operationId"] == "get_me"
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/SuccessEnvelope_UserRead_"

    envelope = openapi["components"]["schemas"]["SuccessEnvelope_UserRead_"]
    # The envelope's `data` must point at the real UserRead schema, not a bare object.
    assert envelope["properties"]["data"]["$ref"] == "#/components/schemas/UserRead"


def test_success_envelope_components_exist(openapi: dict[str, Any]) -> None:
    schemas = openapi["components"]["schemas"]
    envelopes = [name for name in schemas if name.startswith("SuccessEnvelope_")]
    # T-225 wired ~12 distinct envelope specialisations across the routers.
    assert len(envelopes) >= 10
    assert "PaginatedEnvelope_AuditLogEntryRead_" in schemas


def test_no_success_route_returns_bare_object(openapi: dict[str, Any]) -> None:
    """No 2xx JSON body may resolve to an untyped empty object schema."""
    offenders: list[str] = []
    schemas = openapi["components"]["schemas"]
    for method, path, op in _operations(openapi):
        for code, resp in op.get("responses", {}).items():
            if not code.startswith("2"):
                continue
            schema = resp.get("content", {}).get("application/json", {}).get("schema")
            if schema is None:
                continue
            ref = schema.get("$ref")
            if ref is None:
                continue
            name = ref.rsplit("/", 1)[-1]
            target = schemas.get(name, {})
            # A typed dict response_model resolves to {} with no properties; the
            # envelope routes must instead carry properties (data/message/items).
            if name.startswith(("SuccessEnvelope_", "PaginatedEnvelope_")):
                if "properties" not in target:
                    offenders.append(f"{method.upper()} {path} -> {name}")
    assert offenders == [], f"Envelope routes without a typed body: {offenders}"

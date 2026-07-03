"""Tenant routing helpers — school vs independent schema per ARCH §3.16."""

from __future__ import annotations

from typing import Literal

TenantType = Literal["school", "independent"]

INDEPENDENT_ROLES = frozenset({"independent_teacher", "independent_student"})


def get_tenant_type(claims: dict[str, object]) -> TenantType:
    """Resolve tenant type from JWT claims (explicit claim or role prefix)."""
    explicit = claims.get("tenant_type")
    if explicit in ("school", "independent"):
        return explicit  # type: ignore[return-value]

    role = str(claims.get("role", ""))
    if role in INDEPENDENT_ROLES:
        return "independent"
    return "school"


def is_independent_role(role: object) -> bool:
    return str(role or "") in INDEPENDENT_ROLES

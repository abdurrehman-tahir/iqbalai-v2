"""Tests for tenant routing helpers."""

from __future__ import annotations

from app.core.tenant import get_tenant_type, is_independent_role


def test_get_tenant_type_from_explicit_claim() -> None:
    assert get_tenant_type({"tenant_type": "independent"}) == "independent"
    assert get_tenant_type({"tenant_type": "school"}) == "school"


def test_get_tenant_type_from_independent_role() -> None:
    assert get_tenant_type({"role": "independent_teacher"}) == "independent"
    assert get_tenant_type({"role": "independent_student"}) == "independent"


def test_get_tenant_type_defaults_to_school() -> None:
    assert get_tenant_type({"role": "teacher"}) == "school"
    assert get_tenant_type({}) == "school"


def test_is_independent_role() -> None:
    assert is_independent_role("independent_teacher") is True
    assert is_independent_role("teacher") is False

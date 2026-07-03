"""Repository tenant routing tests for platform library — T-073."""

from __future__ import annotations

from app.features.library.models import PlatformReferenceBook
from app.features.library.platform_read_models import PlatformReferenceBookReadonly
from app.features.library.repository import _read_model


def test_independent_tenant_uses_cross_schema_view_model() -> None:
    assert _read_model("independent") is PlatformReferenceBookReadonly


def test_school_tenant_uses_platform_table_model() -> None:
    assert _read_model("school") is PlatformReferenceBook

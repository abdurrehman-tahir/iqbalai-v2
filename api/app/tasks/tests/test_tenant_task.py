"""Unit tests for tenant_task decorator — T-056."""

from __future__ import annotations

import inspect

import pytest

from app.tasks.base import tenant_task


def test_tenant_task_requires_school_id_parameter() -> None:
    with pytest.raises(TypeError, match="school_id"):

        @tenant_task(name="bad.task")
        def bad_task(item_id: str) -> None:
            pass


def test_tenant_task_preserves_school_id_in_signature() -> None:
    @tenant_task(name="good.task", bind=True)
    def good_task(self: object, item_id: str, school_id: str) -> str:
        return school_id

    params = inspect.signature(good_task).parameters
    assert "school_id" in params

"""Audit action registry tests — T-066."""

from __future__ import annotations

from app.features.audit.actions import M04_AUDIT_ACTIONS, SCHOOL_LIBRARY_ITEM_UPLOADED


def test_m04_actions_registered() -> None:
    assert SCHOOL_LIBRARY_ITEM_UPLOADED in M04_AUDIT_ACTIONS
    assert len(M04_AUDIT_ACTIONS) == 7

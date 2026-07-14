"""Audit-registration tests — T-098 (ARCH §14.10).

Asserts every M-07 framework lifecycle action the service emits is registered in the
audit action registry (Acceptance #1), and that approval + publish (plus deprecation and
escalation, which also change what students see) are marked elevated (Acceptance #2).
"""

from __future__ import annotations

from app.features.audit.actions import (
    ELEVATED_AUDIT_ACTIONS,
    M07_AUDIT_ACTIONS,
    REGISTERED_AUDIT_ACTIONS,
)

# The exact action strings the exam_frameworks service passes to audit(...).
_EMITTED_BY_SERVICE = {
    "framework.created",
    "framework.updated",
    "framework.deleted",
    "framework.research_triggered",
    "framework.approved",
    "framework.rejected",
    "framework.published",
    "framework.refresh_triggered",
    "framework.deprecated",
    "framework.approval_reminder",
    "framework.approval_escalated",
}


def test_every_emitted_action_is_registered() -> None:
    assert _EMITTED_BY_SERVICE <= M07_AUDIT_ACTIONS
    assert _EMITTED_BY_SERVICE <= REGISTERED_AUDIT_ACTIONS


def test_registry_matches_emitted_set_exactly() -> None:
    # Guards against a registered-but-never-emitted (or renamed) action drifting.
    assert M07_AUDIT_ACTIONS == _EMITTED_BY_SERVICE


def test_approval_and_publish_are_elevated() -> None:
    assert "framework.approved" in ELEVATED_AUDIT_ACTIONS
    assert "framework.published" in ELEVATED_AUDIT_ACTIONS
    # Deprecation + escalation also change what students may select / need urgency.
    assert "framework.deprecated" in ELEVATED_AUDIT_ACTIONS
    assert "framework.approval_escalated" in ELEVATED_AUDIT_ACTIONS


def test_routine_crud_is_not_elevated() -> None:
    assert "framework.created" not in ELEVATED_AUDIT_ACTIONS
    assert "framework.updated" not in ELEVATED_AUDIT_ACTIONS
    assert "framework.rejected" not in ELEVATED_AUDIT_ACTIONS

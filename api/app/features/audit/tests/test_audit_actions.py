"""Audit action registry tests — T-066, T-140."""

from __future__ import annotations

from app.features.audit.actions import (
    ADMIN_METRICS_ACCESSED,
    ADMIN_METRICS_EXPORTED,
    BENCHMARK_OPT_OUT_TOGGLED,
    ELEVATED_AUDIT_ACTIONS,
    LECTURE_PLAGIARISM_FLAGGED,
    M04_AUDIT_ACTIONS,
    M10_AUDIT_ACTIONS,
    REGISTERED_AUDIT_ACTIONS,
    SCHOOL_LIBRARY_ITEM_UPLOADED,
)


def test_m04_actions_registered() -> None:
    assert SCHOOL_LIBRARY_ITEM_UPLOADED in M04_AUDIT_ACTIONS
    assert len(M04_AUDIT_ACTIONS) == 7


def test_m10_actions_registered() -> None:
    assert M10_AUDIT_ACTIONS <= REGISTERED_AUDIT_ACTIONS
    assert M10_AUDIT_ACTIONS == {
        ADMIN_METRICS_ACCESSED,
        ADMIN_METRICS_EXPORTED,
        BENCHMARK_OPT_OUT_TOGGLED,
        LECTURE_PLAGIARISM_FLAGGED,
    }


def test_m10_sensitive_reads_and_flags_are_elevated() -> None:
    assert ADMIN_METRICS_ACCESSED in ELEVATED_AUDIT_ACTIONS
    assert ADMIN_METRICS_EXPORTED in ELEVATED_AUDIT_ACTIONS
    assert LECTURE_PLAGIARISM_FLAGGED in ELEVATED_AUDIT_ACTIONS


def test_m10_benchmark_opt_out_is_a_routine_setting_not_elevated() -> None:
    assert BENCHMARK_OPT_OUT_TOGGLED not in ELEVATED_AUDIT_ACTIONS


def test_m11_publish_actions_registered() -> None:
    from app.features.audit.actions import (
        LECTURE_OVERRIDE_PUBLISHED,
        LECTURE_PUBLISHED,
        M11_AUDIT_ACTIONS,
        QUIZ_GENERATION_FAILED,
        QUIZ_RESULTS_ACCESSED,
    )

    assert M11_AUDIT_ACTIONS <= REGISTERED_AUDIT_ACTIONS
    assert LECTURE_PUBLISHED in M11_AUDIT_ACTIONS
    assert QUIZ_GENERATION_FAILED in M11_AUDIT_ACTIONS
    assert QUIZ_RESULTS_ACCESSED in M11_AUDIT_ACTIONS
    assert LECTURE_OVERRIDE_PUBLISHED in ELEVATED_AUDIT_ACTIONS
    assert QUIZ_RESULTS_ACCESSED in ELEVATED_AUDIT_ACTIONS
    assert LECTURE_PUBLISHED not in ELEVATED_AUDIT_ACTIONS

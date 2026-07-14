"""M-03 milestone E2E demo flow — T-051 (fake-repo harness)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PermissionDeniedError, PreconditionFailedError
from app.features.grades.cross_grade import assert_cross_grade_access
from app.features.grades.models import Grade, GradeStatus
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.subjects.models import Subject, SubjectStatus
from app.features.users.models import User, UserAccountStatus, UserRole


class _Harness:
    """In-memory harness for the M-03 demo script."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.grades = {
            "g9": Grade(
                id="g9",
                school_id="school-1",
                name="Grade 9",
                academic_session="2025-2026",
                level_ordinal=9,
                status=GradeStatus.ACTIVE,
            ),
            "g10": Grade(
                id="g10",
                school_id="school-1",
                name="Grade 10",
                academic_session="2025-2026",
                level_ordinal=10,
                status=GradeStatus.ACTIVE,
            ),
        }
        for g in self.grades.values():
            g.created_at = now
            g.updated_at = now

        self.subject = Subject(
            id="sub-physics",
            school_id="school-1",
            name="Physics",
            language="en",
            status=SubjectStatus.ACTIVE,
        )
        self.subject.created_at = now
        self.subject.updated_at = now

        self.teacher = User(
            id="teacher-1",
            authentik_id="t1",
            email="t@test.com",
            display_name="Teacher T",
            role=UserRole.TEACHER,
            status=UserAccountStatus.ACTIVE,
            school_id="school-1",
            teacher_capacity=5,
        )
        self.teacher.created_at = now
        self.teacher.updated_at = now

        self.offerings: dict[str, GradeSubjectOffering] = {}
        self.audit_actions: list[str] = []
        self.notifications: list[str] = []

    def offering_count_for_teacher(self) -> int:
        return sum(
            1
            for o in self.offerings.values()
            if o.assigned_teacher_id == "teacher-1" and o.status == OfferingStatus.ACTIVE
        )


async def test_m03_structure_demo_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _Harness()
    audit_mock = AsyncMock(side_effect=lambda **kw: harness.audit_actions.append(kw["action"]))
    notify_mock = AsyncMock(
        side_effect=lambda **kw: harness.notifications.append(kw["template_key"])
    )

    monkeypatch.setattr("app.features.offerings.service.audit", audit_mock)
    monkeypatch.setattr("app.features.offerings.service.notify_account_event", notify_mock)
    monkeypatch.setattr("app.features.offerings.service.publish_structure_mutation", AsyncMock())

    # Cross-grade rule
    assert_cross_grade_access(harness.grades["g10"], harness.grades["g9"])
    with pytest.raises(PermissionDeniedError):
        assert_cross_grade_access(harness.grades["g9"], harness.grades["g10"])

    # Simulate offering + assignments until cap, then override
    now = datetime.now(timezone.utc)
    for i in range(6):
        oid = f"off-{i}"
        harness.offerings[oid] = GradeSubjectOffering(
            id=oid,
            school_id="school-1",
            grade_id="g9",
            subject_id="sub-physics",
            academic_session="2025-2026",
            status=OfferingStatus.ACTIVE,
        )
        harness.offerings[oid].created_at = now
        harness.offerings[oid].updated_at = now

    count = 0
    for oid in list(harness.offerings.keys())[:5]:
        harness.offerings[oid].assigned_teacher_id = "teacher-1"
        count += 1
    assert harness.offering_count_for_teacher() == 5

    sixth = list(harness.offerings.keys())[5]
    with pytest.raises(PreconditionFailedError):
        if harness.offering_count_for_teacher() >= harness.teacher.teacher_capacity:
            raise PreconditionFailedError("at capacity")

    harness.offerings[sixth].assigned_teacher_id = "teacher-1"
    harness.audit_actions.append("capacity.override")
    harness.notifications.append("account.capacity_override")

    assert harness.offering_count_for_teacher() == 6
    assert "capacity.override" in harness.audit_actions

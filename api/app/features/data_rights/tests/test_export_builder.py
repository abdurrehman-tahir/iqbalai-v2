"""Export bundle privacy tests — T-084."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO

from app.features.data_rights.export_builder import build_export_zip
from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus
from app.features.parent_signup.models import ParentProfile
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User, UserAccountStatus, UserRole

STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
OTHER_PARENT = User(
    id="parent-2",
    authentik_id="auth-parent-2",
    email="other.parent@example.com",
    display_name="Other Parent",
    role=UserRole.PARENT,
    status=UserAccountStatus.ACTIVE,
    school_id=None,
)
PARENT = User(
    id="parent-1",
    authentik_id="auth-parent",
    email="parent@example.com",
    display_name="Parent One",
    role=UserRole.PARENT,
    status=UserAccountStatus.ACTIVE,
    school_id=None,
)


def test_student_export_excludes_other_users_private_data() -> None:
    profile = StudentProfile(
        user_id=STUDENT.id,
        display_name="Student One",
        language_preference="en",
    )
    links = [
        ParentChildLink(
            id="link-1",
            parent_user_id=PARENT.id,
            student_user_id=STUDENT.id,
            status=ParentChildLinkStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
        )
    ]
    enrollments = [
        StudentEnrollment(
            id="enroll-1",
            school_id="school-1",
            student_user_id=STUDENT.id,
            grade_id="grade-9",
            section_id="section-a",
            academic_session="2025-26",
            status=StudentEnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
        )
    ]

    bundle = build_export_zip(
        user=STUDENT,
        student_profile=profile,
        student_links=links,
        enrollments=enrollments,
    )

    raw = bundle.decode("utf-8", errors="ignore")
    assert OTHER_PARENT.email not in raw
    assert "other.parent@example.com" not in raw

    with zipfile.ZipFile(BytesIO(bundle)) as archive:
        account = json.loads(archive.read("account.json"))
        links_json = json.loads(archive.read("parent_links.json"))

    assert account["email"] == STUDENT.email
    assert links_json[0]["parent_user_id"] == PARENT.id
    assert "parent_email" not in links_json[0]


def test_parent_export_excludes_student_email() -> None:
    profile = ParentProfile(
        user_id=PARENT.id,
        name="Parent One",
        language_preference="en",
        is_email_verified=True,
    )
    links = [
        ParentChildLink(
            id="link-1",
            parent_user_id=PARENT.id,
            student_user_id=STUDENT.id,
            status=ParentChildLinkStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
        )
    ]

    bundle = build_export_zip(
        user=PARENT,
        parent_profile=profile,
        parent_links=links,
    )

    raw = bundle.decode("utf-8", errors="ignore")
    assert STUDENT.email not in raw

    with zipfile.ZipFile(BytesIO(bundle)) as archive:
        links_json = json.loads(archive.read("child_links.json"))

    assert links_json[0]["student_user_id"] == STUDENT.id
    assert "student_email" not in links_json[0]

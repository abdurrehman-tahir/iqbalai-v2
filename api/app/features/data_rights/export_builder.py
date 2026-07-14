"""Build machine-readable export bundles — T-084."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from typing import Any

from app.features.data_rights.models import DataRightsRequestType
from app.features.parent_child_links.models import ParentChildLink
from app.features.parent_signup.models import ParentProfile
from app.features.student_enrollments.models import StudentEnrollment
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User, UserRole


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _dump_json(data: object) -> bytes:
    return json.dumps(data, indent=2, default=_json_default).encode("utf-8")


def _account_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "status": user.status.value,
        "school_id": user.school_id,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _student_profile_payload(profile: StudentProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "display_name": profile.display_name,
        "language_preference": profile.language_preference,
        "lecture_mode_enabled": profile.lecture_mode_enabled,
        "self_study_mode_enabled": profile.self_study_mode_enabled,
        "exam_date": profile.exam_date,
        "profile_basic_completed_at": profile.profile_basic_completed_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _parent_profile_payload(profile: ParentProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "name": profile.name,
        "language_preference": profile.language_preference,
        "is_email_verified": profile.is_email_verified,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _student_links_payload(links: list[ParentChildLink]) -> list[dict[str, Any]]:
    return [
        {
            "link_id": link.id,
            "parent_user_id": link.parent_user_id,
            "status": link.status.value,
            "requested_at": link.created_at,
            "approved_at": link.approved_at,
            "revoked_at": link.revoked_at,
        }
        for link in links
    ]


def _parent_links_payload(links: list[ParentChildLink]) -> list[dict[str, Any]]:
    return [
        {
            "link_id": link.id,
            "student_user_id": link.student_user_id,
            "status": link.status.value,
            "requested_at": link.created_at,
            "approved_at": link.approved_at,
            "revoked_at": link.revoked_at,
        }
        for link in links
    ]


def _enrollments_payload(enrollments: list[StudentEnrollment]) -> list[dict[str, Any]]:
    return [
        {
            "enrollment_id": enrollment.id,
            "grade_id": enrollment.grade_id,
            "section_id": enrollment.section_id,
            "academic_session": enrollment.academic_session,
            "status": enrollment.status.value,
            "enrolled_at": enrollment.enrolled_at,
        }
        for enrollment in enrollments
    ]


def _summary_text(*, user: User, request_type: DataRightsRequestType) -> str:
    role_label = user.role.value.replace("_", " ")
    return (
        "IqbalAI Personal Data Export\n"
        "============================\n\n"
        f"Account: {user.email}\n"
        f"Role: {role_label}\n"
        f"Export generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        "This bundle contains only your personal data stored in IqbalAI. "
        "Other users' private information is excluded.\n\n"
        "Under Pakistan's Personal Data Protection Bill (PDPB) 2025, you have the right "
        "to access and export your data. Deletion requests are reviewed separately and "
        "subject to legal retention requirements (including audit logs).\n"
    )


def build_export_zip(
    *,
    user: User,
    student_profile: StudentProfile | None = None,
    parent_profile: ParentProfile | None = None,
    student_links: list[ParentChildLink] | None = None,
    parent_links: list[ParentChildLink] | None = None,
    enrollments: list[StudentEnrollment] | None = None,
) -> bytes:
    """Assemble a ZIP bundle with JSON + CSV summaries for the requesting user only."""
    account = _account_payload(user)
    summary = _summary_text(user=user, request_type=DataRightsRequestType.EXPORT)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", summary)
        archive.writestr("account.json", _dump_json(account))

        if user.role == UserRole.STUDENT:
            archive.writestr(
                "student_profile.json",
                _dump_json(_student_profile_payload(student_profile)),
            )
            archive.writestr(
                "parent_links.json",
                _dump_json(_student_links_payload(student_links or [])),
            )
            archive.writestr(
                "enrollments.json",
                _dump_json(_enrollments_payload(enrollments or [])),
            )
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(
                ["enrollment_id", "grade_id", "section_id", "academic_session", "status"]
            )
            for row in _enrollments_payload(enrollments or []):
                writer.writerow(
                    [
                        row["enrollment_id"],
                        row["grade_id"],
                        row["section_id"],
                        row["academic_session"],
                        row["status"],
                    ]
                )
            archive.writestr("enrollments.csv", csv_buffer.getvalue())

        if user.role == UserRole.PARENT:
            archive.writestr(
                "parent_profile.json",
                _dump_json(_parent_profile_payload(parent_profile)),
            )
            archive.writestr(
                "child_links.json",
                _dump_json(_parent_links_payload(parent_links or [])),
            )

    return buffer.getvalue()

"""Targeted mini-lecture distribution — T-204 (Flow 7 §3.7 #47).

Recipients are the union of students whose questions triggered the published
clusters — never a broadcast. One ``lecture_assignments`` row per recipient
restricts the mini-lecture to exactly them; students who have left the
Grade-Subject offering's grade are dropped at publish time (§5.4), and if
nobody is left the publish is refused with ``PRECONDITION_FAILED``.
Auto-quiz is not generated for minis (guarded in quizzes/generation.py) and
cross-grade linking of a mini is blocked in the lecture service.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PreconditionFailedError
from app.features.lectures.models import (
    LectureAssignmentScope,
    SchoolLecture,
    SchoolLectureAssignment,
)
from app.features.lectures.repository import LectureAssignmentRepository
from app.features.next_day_review.schemas import ReviewClusterSnapshot
from app.features.offerings.repository import OfferingRepository
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.users.repository import UserRepository
from app.infrastructure.notifications.lectures import notify_lecture_event

logger = structlog.get_logger(__name__)

MINI_ASSIGNED_TEMPLATE = "lectures.mini_lecture_assigned"
# Event subject on the content stream bound for mini_lecture.> (A-004).
MINI_LECTURE_ASSIGNED_EVENT = "mini_lecture.assigned"


def triggering_students(
    snapshots: list[ReviewClusterSnapshot], *, mini_lecture_id: str, skipped: set[str]
) -> set[str]:
    """Union of students behind the clusters this mini-lecture answers.

    A mini is generated per cluster (T-198), so it targets the clusters that
    reference it; a legacy card without per-cluster refs falls back to every
    non-skipped cluster on the review.
    """
    live = [s for s in snapshots if s.cluster_ref not in skipped]
    targeted = [s for s in live if s.mini_lecture_id == mini_lecture_id] or live
    return {q.student_user_id for s in targeted for q in s.questions if q.student_user_id}


async def enrolled_recipients(
    session: AsyncSession, *, gso_id: str, candidates: set[str]
) -> set[str]:
    """Keep only students still actively enrolled in the offering's grade."""
    offering = await OfferingRepository(session).get_by_id(gso_id)
    if offering is None:
        return set()
    enrollments = await StudentEnrollmentRepository(session).list_active_for_grade(
        offering.grade_id, offering.academic_session
    )
    active = {e.student_user_id for e in enrollments}
    return candidates & active


async def assign_recipients(
    session: AsyncSession,
    *,
    mini: SchoolLecture,
    gso_id: str,
    candidates: set[str],
    actor_user_id: str,
) -> list[str]:
    """Replace the mini's assignments with the enrolled triggering students."""
    recipients = sorted(await enrolled_recipients(session, gso_id=gso_id, candidates=candidates))
    if not recipients:
        raise PreconditionFailedError(
            "None of the students who asked these questions are still enrolled"
        )
    rows = [
        SchoolLectureAssignment(
            lecture_id=mini.id,
            scope=LectureAssignmentScope.STUDENT,
            student_user_id=student_id,
            created_by_user_id=actor_user_id,
        )
        for student_id in recipients
    ]
    # Replace-all: a re-publish targets the current set (§5.4).
    await LectureAssignmentRepository(session).replace_for_lecture(mini.id, rows)
    logger.info(
        "mini_lecture_assigned",
        lecture_id=mini.id,
        recipients=len(recipients),
        dropped=len(candidates) - len(recipients),
    )
    return recipients


async def notify_recipients(
    session: AsyncSession, *, mini: SchoolLecture, recipients: list[str]
) -> int:
    """In-app notification to each recipient; best-effort per student."""
    users = UserRepository(session)
    sent = 0
    for student_id in recipients:
        try:
            student = await users.get_by_id(student_id)
            if student is None or not student.authentik_id:
                continue
            await notify_lecture_event(
                session=session,
                template_key=MINI_ASSIGNED_TEMPLATE,
                recipient_user_id=student.authentik_id,
                school_id=mini.school_id,
                params={"topic": mini.topic or mini.title},
                metadata={"lecture_id": mini.id},
            )
            sent += 1
        except Exception as exc:
            # One failed delivery must not block the rest of the recipients.
            logger.warning("mini_assigned_notify_failed", student_id=student_id, error=str(exc))
    return sent

"""Quiz + lecture-publish fan-out notifications (T-149)."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture
from app.features.offerings.repository import OfferingRepository
from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus
from app.features.quizzes.models import QuizAssignmentStatus, SchoolQuiz, SchoolQuizAssignment
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.infrastructure.notifications.lectures import notify_lecture_event
from app.infrastructure.notifications.quiz import notify_quiz_event
from app.infrastructure.notifications.templates.lectures import DEFAULT_LOCALE
from app.infrastructure.notifications.templates.quiz import DEFAULT_LOCALE as QUIZ_DEFAULT_LOCALE

logger = structlog.get_logger(__name__)


async def notify_publish_fanout(session: AsyncSession, *, lecture: SchoolLecture) -> None:
    """Notify enrolled students (+ linked parents) and quiz-available (T-149)."""
    if lecture.school_id is None or lecture.grade_subject_offering_id is None:
        return

    offering = await OfferingRepository(session).get_by_id(lecture.grade_subject_offering_id)
    if offering is None:
        return

    enrollments = await StudentEnrollmentRepository(session).list_active_for_grade(
        offering.grade_id, offering.academic_session
    )
    users = UserRepository(session)
    for enrollment in enrollments:
        student = await users.get_by_id(enrollment.student_user_id)
        if student is None or not student.authentik_id:
            continue
        locale = DEFAULT_LOCALE
        try:
            await notify_lecture_event(
                session=session,
                template_key="lectures.published",
                recipient_user_id=student.authentik_id,
                school_id=lecture.school_id,
                locale=locale,
                variant="student",
                params={"topic": lecture.topic},
                metadata={"lecture_id": lecture.id},
            )
        except Exception as exc:
            logger.warning(
                "lecture_published_student_notify_failed",
                student_id=student.id,
                error=str(exc),
            )

        await _notify_linked_parents(
            session,
            student=student,
            lecture=lecture,
            locale=locale,
        )

    # Quiz-available for students whose assignments flipped to published
    quiz_ids = (
        await session.execute(
            select(SchoolQuiz.id).where(
                SchoolQuiz.lecture_id == lecture.id,
                SchoolQuiz.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    if not quiz_ids:
        return

    assignments = (
        await session.execute(
            select(SchoolQuizAssignment).where(
                SchoolQuizAssignment.quiz_id.in_(list(quiz_ids)),
                SchoolQuizAssignment.status == QuizAssignmentStatus.PUBLISHED,
                SchoolQuizAssignment.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    for assignment in assignments:
        student = await users.get_by_id(assignment.student_user_id)
        if student is None or not student.authentik_id:
            continue
        try:
            await notify_quiz_event(
                session=session,
                template_key="quiz.available",
                recipient_user_id=student.authentik_id,
                school_id=lecture.school_id,
                locale=QUIZ_DEFAULT_LOCALE,
                params={"topic": lecture.topic},
                metadata={
                    "lecture_id": lecture.id,
                    "assignment_id": assignment.id,
                },
            )
        except Exception as exc:
            logger.warning(
                "quiz_available_notify_failed",
                student_id=student.id,
                error=str(exc),
            )


async def _notify_linked_parents(
    session: AsyncSession,
    *,
    student: User,
    lecture: SchoolLecture,
    locale: str,
) -> None:
    links = (
        await session.execute(
            select(ParentChildLink).where(
                ParentChildLink.student_user_id == student.id,
                ParentChildLink.status == ParentChildLinkStatus.APPROVED,
                ParentChildLink.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    users = UserRepository(session)
    for link in links:
        parent = await users.get_by_id(link.parent_user_id)
        if parent is None or not parent.authentik_id:
            continue
        try:
            await notify_lecture_event(
                session=session,
                template_key="lectures.published",
                recipient_user_id=parent.authentik_id,
                school_id=lecture.school_id,
                locale=locale,
                variant="parent",
                params={"topic": lecture.topic},
                metadata={"lecture_id": lecture.id, "student_user_id": student.id},
            )
        except Exception as exc:
            logger.warning(
                "lecture_published_parent_notify_failed",
                parent_id=parent.id,
                error=str(exc),
            )


async def notify_quiz_results_ready_for_teacher(
    session: AsyncSession,
    *,
    lecture: SchoolLecture,
) -> None:
    if lecture.teacher_user_id is None:
        return
    teacher = await UserRepository(session).get_by_id(lecture.teacher_user_id)
    if teacher is None or not teacher.authentik_id:
        return
    try:
        await notify_quiz_event(
            session=session,
            template_key="quiz.results_ready",
            recipient_user_id=teacher.authentik_id,
            school_id=lecture.school_id,
            locale=QUIZ_DEFAULT_LOCALE,
            params={"topic": lecture.topic},
            metadata={"lecture_id": lecture.id},
        )
    except Exception as exc:
        logger.warning(
            "quiz_results_ready_notify_failed",
            lecture_id=lecture.id,
            error=str(exc),
        )

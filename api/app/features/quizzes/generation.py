"""Per-student Pattern-S quiz generation (T-143 + T-144)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import (
    LectureAssignmentScope,
    LectureStatus,
    SchoolLecture,
    SchoolLectureParagraph,
    SchoolLectureVersion,
)
from app.features.offerings.models import GradeSubjectOffering
from app.features.offerings.repository import OfferingRepository
from app.features.quizzes.calibration import get_default_calibration_provider
from app.features.quizzes.models import (
    QuizAssignmentStatus,
    QuizQuestionDifficulty,
    QuizStatus,
    SchoolQuiz,
    SchoolQuizAssignment,
    SchoolQuizQuestion,
)
from app.features.quizzes.schemas import (
    QuestionSourceMetadata,
    QuizOptionsList,
    QuizQuestionOption,
)
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.users.repository import UserRepository
from app.infrastructure.llm.client import chat
from app.infrastructure.llm.prompts import quiz_generate_v1

logger = structlog.get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK.search(text)
    if match:
        text = match.group(0)
    return cast(dict[str, Any], json.loads(text))


async def run_quiz_generation_for_student(
    session: AsyncSession,
    *,
    lecture_id: str,
    school_id: str,
    student_user_id: str,
    lecture_version_id: str | None = None,
) -> str | None:
    """Generate one calibrated quiz for a student. Returns quiz_id or None if skipped.

    Idempotent: if a quiz already exists for (lecture_version, student), returns its id.
    """
    lecture = await session.get(SchoolLecture, lecture_id)
    if lecture is None or lecture.school_id != school_id:
        logger.warning("quiz_gen_lecture_not_found", lecture_id=lecture_id)
        return None

    version_id = lecture_version_id or lecture.current_version_id
    if version_id is None:
        logger.warning("quiz_gen_no_version", lecture_id=lecture_id)
        return None

    existing = await session.execute(
        select(SchoolQuiz).where(
            SchoolQuiz.lecture_version_id == version_id,
            SchoolQuiz.student_user_id == student_user_id,
            SchoolQuiz.deleted_at.is_(None),
        )
    )
    prior = existing.scalar_one_or_none()
    if prior is not None:
        logger.info("quiz_gen_already_exists", quiz_id=prior.id, student_user_id=student_user_id)
        return prior.id

    version = await session.get(SchoolLectureVersion, version_id)
    if version is None:
        return None

    paragraphs = (
        await session.execute(
            select(SchoolLectureParagraph)
            .where(SchoolLectureParagraph.lecture_version_id == version_id)
            .order_by(SchoolLectureParagraph.ordinal)
        )
    ).scalars().all()

    excerpt_parts: list[str] = []
    if paragraphs:
        for para in paragraphs[:12]:
            excerpt_parts.append(para.text)
    else:
        excerpt_parts.append(version.body[:8000])
    lecture_excerpt = "\n\n".join(excerpt_parts)[:12000]

    subject_id: str | None = None
    if lecture.grade_subject_offering_id:
        offering = await session.get(GradeSubjectOffering, lecture.grade_subject_offering_id)
        if offering is not None:
            subject_id = offering.subject_id

    calibration = await get_default_calibration_provider(session).resolve(
        student_user_id=student_user_id,
        subject_id=subject_id,
        lecture_topic=lecture.topic,
    )

    quiz = SchoolQuiz(
        lecture_id=lecture.id,
        lecture_version_id=version_id,
        student_user_id=student_user_id,
        status=QuizStatus.GENERATING,
    )
    session.add(quiz)
    await session.flush()

    try:
        prompt_input = quiz_generate_v1.QuizGenerateInput(
            topic=lecture.topic,
            lecture_excerpt=lecture_excerpt,
            target_difficulty=calibration.target_difficulty.value,  # type: ignore[arg-type]
            question_count=7,
        )
        raw = await chat(
            quiz_generate_v1.render(prompt_input),
            task="quiz_gen",
            temperature=0.4,
            max_tokens=4096,
        )
        parsed = quiz_generate_v1.QuizGenerateOutput.model_validate(_parse_json(raw))
        questions = parsed.questions
        if len(questions) < 5:
            raise ValueError(f"Expected 5–10 questions, got {len(questions)}")

        for ordinal, q in enumerate(questions[:10], start=1):
            options = QuizOptionsList(
                options=[QuizQuestionOption(key=o["key"], text=o["text"]) for o in q.options]
            )
            difficulty = QuizQuestionDifficulty(q.difficulty)
            source = QuestionSourceMetadata(
                lecture_id=lecture.id,
                lecture_version_id=version_id,
                paragraph_ordinal=ordinal,
                excerpt=q.source_excerpt,
                tier="lecture_body",
            )
            session.add(
                SchoolQuizQuestion(
                    quiz_id=quiz.id,
                    ordinal=ordinal,
                    stem=q.stem,
                    options_jsonb=options.to_jsonb(),
                    correct_answer=q.correct_answer,
                    difficulty=difficulty,
                    source_metadata_jsonb=source.to_jsonb(),
                )
            )

        assignment_status = QuizAssignmentStatus.PENDING
        if lecture.status == LectureStatus.PUBLISHED:
            assignment_status = QuizAssignmentStatus.PUBLISHED

        session.add(
            SchoolQuizAssignment(
                quiz_id=quiz.id,
                student_user_id=student_user_id,
                status=assignment_status,
                calibration_jsonb=calibration.profile.to_jsonb(),
                assigned_at=datetime.now(timezone.utc),
            )
        )
        quiz.status = QuizStatus.READY
        await session.commit()
        logger.info(
            "quiz_gen_complete",
            quiz_id=quiz.id,
            student_user_id=student_user_id,
            difficulty=calibration.target_difficulty.value,
            question_count=len(questions),
        )
        return quiz.id
    except Exception as exc:
        logger.exception("quiz_gen_failed", lecture_id=lecture_id, student_user_id=student_user_id)
        quiz.status = QuizStatus.FAILED
        await session.commit()
        from app.features.audit.actions import QUIZ_GENERATION_FAILED
        from app.infrastructure.audit.log import audit

        await audit(
            session=session,
            action=QUIZ_GENERATION_FAILED,
            actor_id=student_user_id,
            actor_role="system",
            target_type="lecture",
            target_id=lecture_id,
            school_id=school_id,
            metadata={"student_user_id": student_user_id, "error": str(exc)[:500]},
        )
        raise


async def enqueue_quiz_generation_for_lecture(
    session: AsyncSession,
    *,
    lecture: SchoolLecture,
) -> int:
    """Enqueue one Celery quiz task per enrolled student (parallel). Returns task count."""
    if lecture.school_id is None or lecture.grade_subject_offering_id is None:
        return 0
    if lecture.current_version_id is None:
        return 0

    from app.features.lectures.repository import LectureAssignmentRepository
    from app.features.quizzes.tasks import generate_quiz_for_student

    offering = await OfferingRepository(session).get_by_id(
        lecture.grade_subject_offering_id
    )
    if offering is None:
        return 0

    enrollments = await StudentEnrollmentRepository(session).list_active_for_grade(
        offering.grade_id, offering.academic_session
    )
    assignments = await LectureAssignmentRepository(session).list_by_lecture(lecture.id)
    users = UserRepository(session)
    count = 0
    for enrollment in enrollments:
        student = await users.get_by_id(enrollment.student_user_id)
        if student is None:
            continue
        if assignments:
            allowed = False
            for row in assignments:
                if (
                    row.scope == LectureAssignmentScope.STUDENT
                    and row.student_user_id == student.id
                ):
                    allowed = True
                    break
                if (
                    row.scope == LectureAssignmentScope.SECTION
                    and row.section_id == enrollment.section_id
                ):
                    allowed = True
                    break
            if not allowed:
                continue

        generate_quiz_for_student.apply_async(
            kwargs={
                "lecture_id": lecture.id,
                "school_id": lecture.school_id,
                "student_user_id": student.id,
                "lecture_version_id": lecture.current_version_id,
            }
        )
        count += 1

    logger.info("quiz_gen_enqueued", lecture_id=lecture.id, student_count=count, parallel=True)
    return count

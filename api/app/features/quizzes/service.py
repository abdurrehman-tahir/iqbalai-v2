"""Quiz service — student attempt + teacher aggregates (T-145–T-147)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import not_deleted
from app.features.audit.actions import QUIZ_RESULTS_ACCESSED
from app.features.lectures.models import LectureStatus, SchoolLecture
from app.features.quizzes.api_schemas import (
    QuizAggregateHotspotRead,
    QuizAttemptResultRead,
    QuizOfferingAggregateRead,
    QuizOptionRead,
    QuizQuestionResultRead,
    QuizSubmitRequest,
    StudentQuizCardRead,
    StudentQuizDetailRead,
    StudentQuizQuestionRead,
    TeacherStudentQuizResultRead,
)
from app.features.quizzes.models import (
    QuizAssignmentStatus,
    SchoolQuiz,
    SchoolQuizAssignment,
    SchoolQuizAttempt,
    SchoolQuizQuestion,
)
from app.features.quizzes.schemas import QuizAnswersMap
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.events.publisher import publish


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def _require_user(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        return user

    async def list_my_quizzes(self, claims: dict[str, object]) -> list[StudentQuizCardRead]:
        """Student dashboard: own published+ quizzes only (T-145)."""
        user = await self._require_user(claims)
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")

        rows = (
            await self._session.execute(
                select(SchoolQuizAssignment, SchoolQuiz, SchoolLecture)
                .join(SchoolQuiz, SchoolQuiz.id == SchoolQuizAssignment.quiz_id)
                .join(SchoolLecture, SchoolLecture.id == SchoolQuiz.lecture_id)
                .where(
                    SchoolQuizAssignment.student_user_id == user.id,
                    not_deleted(SchoolQuizAssignment),
                    not_deleted(SchoolQuiz),
                    SchoolQuizAssignment.status.in_(
                        [
                            QuizAssignmentStatus.PUBLISHED,
                            QuizAssignmentStatus.ATTEMPTED,
                            QuizAssignmentStatus.COMPLETED,
                        ]
                    ),
                    SchoolLecture.status == LectureStatus.PUBLISHED,
                )
                .order_by(SchoolQuizAssignment.assigned_at.desc())
            )
        ).all()

        cards: list[StudentQuizCardRead] = []
        for assignment, quiz, lecture in rows:
            q_count = (
                await self._session.execute(
                    select(func.count())
                    .select_from(SchoolQuizQuestion)
                    .where(
                        SchoolQuizQuestion.quiz_id == quiz.id,
                        not_deleted(SchoolQuizQuestion),
                    )
                )
            ).scalar_one()
            cards.append(
                StudentQuizCardRead(
                    assignment_id=assignment.id,
                    quiz_id=quiz.id,
                    lecture_id=lecture.id,
                    lecture_topic=lecture.topic,
                    lecture_title=lecture.title,
                    question_count=int(q_count),
                    status=assignment.status,
                    assigned_at=assignment.assigned_at,
                )
            )
        return cards

    async def get_my_quiz(
        self, claims: dict[str, object], assignment_id: str
    ) -> StudentQuizDetailRead:
        user = await self._require_user(claims)
        assignment, quiz, lecture = await self._owned_assignment(user, assignment_id)
        if assignment.status == QuizAssignmentStatus.PENDING:
            raise NotFoundError("Quiz not available")
        if lecture.status != LectureStatus.PUBLISHED:
            raise NotFoundError("Quiz not available")
        questions = (
            (
                await self._session.execute(
                    select(SchoolQuizQuestion)
                    .where(
                        SchoolQuizQuestion.quiz_id == quiz.id,
                        not_deleted(SchoolQuizQuestion),
                    )
                    .order_by(SchoolQuizQuestion.ordinal)
                )
            )
            .scalars()
            .all()
        )
        return StudentQuizDetailRead(
            assignment_id=assignment.id,
            quiz_id=quiz.id,
            lecture_id=lecture.id,
            lecture_topic=lecture.topic,
            status=assignment.status.value,
            questions=[
                StudentQuizQuestionRead(
                    id=q.id,
                    ordinal=q.ordinal,
                    stem=q.stem,
                    options=[
                        QuizOptionRead(key=str(o["key"]), text=str(o["text"]))
                        for o in (q.options_jsonb or [])
                        if isinstance(o, dict)
                    ],
                )
                for q in questions
            ],
        )

    async def submit_my_quiz(
        self, claims: dict[str, object], assignment_id: str, payload: QuizSubmitRequest
    ) -> QuizAttemptResultRead:
        """Idempotent submit — returns existing attempt if already completed (T-146)."""
        user = await self._require_user(claims)
        assignment, quiz, _lecture = await self._owned_assignment(user, assignment_id)
        if assignment.status not in (
            QuizAssignmentStatus.PUBLISHED,
            QuizAssignmentStatus.ATTEMPTED,
            QuizAssignmentStatus.COMPLETED,
        ):
            raise ValidationError("Quiz is not available for submission")

        existing = (
            await self._session.execute(
                select(SchoolQuizAttempt).where(
                    SchoolQuizAttempt.quiz_assignment_id == assignment.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await self._result_from_attempt(assignment, quiz, existing)

        questions = (
            (
                await self._session.execute(
                    select(SchoolQuizQuestion)
                    .where(
                        SchoolQuizQuestion.quiz_id == quiz.id,
                        not_deleted(SchoolQuizQuestion),
                    )
                    .order_by(SchoolQuizQuestion.ordinal)
                )
            )
            .scalars()
            .all()
        )
        answers = QuizAnswersMap.from_jsonb(payload.answers).answers
        score = 0
        for q in questions:
            if answers.get(q.id) == q.correct_answer:
                score += 1
        max_score = max(len(questions), 1)
        attempt = SchoolQuizAttempt(
            quiz_assignment_id=assignment.id,
            answers_jsonb=answers,
            score=score,
            max_score=max_score,
            attempted_at=datetime.now(timezone.utc),
        )
        assignment.status = QuizAssignmentStatus.COMPLETED
        self._session.add(attempt)
        await self._session.commit()
        await self._session.refresh(attempt)

        try:
            await publish(
                "student.quiz.completed",
                "student.quiz.completed",
                {
                    "assignment_id": assignment.id,
                    "quiz_id": quiz.id,
                    "student_user_id": user.id,
                    "score": score,
                    "max_score": max_score,
                    "school_id": user.school_id,
                },
                tenant_id=str(user.school_id or ""),
                tenant_type="school",
                user_id=user.id,
            )
        except Exception:
            pass

        try:
            lecture = await self._session.get(SchoolLecture, quiz.lecture_id)
            if lecture is not None:
                from app.features.quizzes.quiz_notifications import (
                    notify_quiz_results_ready_for_teacher,
                )

                await notify_quiz_results_ready_for_teacher(self._session, lecture=lecture)
        except Exception:
            pass

        return await self._result_from_attempt(assignment, quiz, attempt)

    async def teacher_results_for_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[TeacherStudentQuizResultRead]:
        user = await self._require_user(claims)
        lecture = await self._session.get(SchoolLecture, lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        await self._require_teacher_scope(user, lecture)

        quizzes = (
            (
                await self._session.execute(
                    select(SchoolQuiz).where(
                        SchoolQuiz.lecture_id == lecture_id,
                        not_deleted(SchoolQuiz),
                    )
                )
            )
            .scalars()
            .all()
        )
        results: list[TeacherStudentQuizResultRead] = []
        for quiz in quizzes:
            assignment = (
                await self._session.execute(
                    select(SchoolQuizAssignment).where(
                        SchoolQuizAssignment.quiz_id == quiz.id,
                        not_deleted(SchoolQuizAssignment),
                    )
                )
            ).scalar_one_or_none()
            if assignment is None:
                continue
            student = await self._users.get_by_id(assignment.student_user_id)
            attempt = (
                await self._session.execute(
                    select(SchoolQuizAttempt).where(
                        SchoolQuizAttempt.quiz_assignment_id == assignment.id
                    )
                )
            ).scalar_one_or_none()
            results.append(
                TeacherStudentQuizResultRead(
                    student_user_id=assignment.student_user_id,
                    student_display_name=(
                        student.display_name if student is not None else assignment.student_user_id
                    ),
                    assignment_id=assignment.id,
                    status=assignment.status.value,
                    score=attempt.score if attempt else None,
                    max_score=attempt.max_score if attempt else None,
                    calibration=assignment.calibration_jsonb,
                )
            )
        await audit(
            session=self._session,
            action=QUIZ_RESULTS_ACCESSED,
            actor_id=user.id,
            actor_role=user.role.value,
            target_type="lecture",
            target_id=lecture_id,
            school_id=lecture.school_id,
            metadata={"view": "per_student"},
        )
        return results

    async def teacher_aggregate_for_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> QuizOfferingAggregateRead:
        user = await self._require_user(claims)
        lecture = await self._session.get(SchoolLecture, lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        await self._require_teacher_scope(user, lecture, allow_coordinator_admin=True)

        assignments = (
            (
                await self._session.execute(
                    select(SchoolQuizAssignment)
                    .join(SchoolQuiz, SchoolQuiz.id == SchoolQuizAssignment.quiz_id)
                    .where(
                        SchoolQuiz.lecture_id == lecture_id,
                        not_deleted(SchoolQuizAssignment),
                        not_deleted(SchoolQuiz),
                    )
                )
            )
            .scalars()
            .all()
        )
        assigned = len(assignments)
        completed = [a for a in assignments if a.status == QuizAssignmentStatus.COMPLETED]
        scores: list[float] = []
        for a in completed:
            attempt = (
                await self._session.execute(
                    select(SchoolQuizAttempt).where(SchoolQuizAttempt.quiz_assignment_id == a.id)
                )
            ).scalar_one_or_none()
            if attempt and attempt.max_score:
                scores.append(attempt.score / attempt.max_score)

        # Hotspots: per-ordinal incorrect rate across completed attempts
        # (use first quiz's questions as the template).
        hotspots: list[QuizAggregateHotspotRead] = []
        if completed:
            first_quiz_id = (
                await self._session.execute(
                    select(SchoolQuizAssignment.quiz_id).where(
                        SchoolQuizAssignment.id == completed[0].id
                    )
                )
            ).scalar_one()
            questions = (
                (
                    await self._session.execute(
                        select(SchoolQuizQuestion)
                        .where(SchoolQuizQuestion.quiz_id == first_quiz_id)
                        .order_by(SchoolQuizQuestion.ordinal)
                    )
                )
                .scalars()
                .all()
            )
            for q in questions:
                incorrect = 0
                total = 0
                for a in completed:
                    attempt = (
                        await self._session.execute(
                            select(SchoolQuizAttempt).where(
                                SchoolQuizAttempt.quiz_assignment_id == a.id
                            )
                        )
                    ).scalar_one_or_none()
                    if attempt is None:
                        continue
                    # Match by ordinal across per-student quizzes
                    peer_q = (
                        await self._session.execute(
                            select(SchoolQuizQuestion).where(
                                SchoolQuizQuestion.quiz_id == a.quiz_id,
                                SchoolQuizQuestion.ordinal == q.ordinal,
                            )
                        )
                    ).scalar_one_or_none()
                    if peer_q is None:
                        continue
                    total += 1
                    ans = (attempt.answers_jsonb or {}).get(peer_q.id)
                    if ans != peer_q.correct_answer:
                        incorrect += 1
                if total:
                    hotspots.append(
                        QuizAggregateHotspotRead(
                            question_ordinal=q.ordinal,
                            difficulty=q.difficulty.value,
                            incorrect_rate=incorrect / total,
                        )
                    )

        await audit(
            session=self._session,
            action=QUIZ_RESULTS_ACCESSED,
            actor_id=user.id,
            actor_role=user.role.value,
            target_type="lecture",
            target_id=lecture_id,
            school_id=lecture.school_id,
            metadata={"view": "aggregate"},
        )
        return QuizOfferingAggregateRead(
            lecture_id=lecture.id,
            lecture_topic=lecture.topic,
            assigned_count=assigned,
            completed_count=len(completed),
            completion_rate=(len(completed) / assigned) if assigned else 0.0,
            average_score=(sum(scores) / len(scores)) if scores else None,
            hotspots=hotspots,
        )

    async def _owned_assignment(
        self, user: User, assignment_id: str
    ) -> tuple[SchoolQuizAssignment, SchoolQuiz, SchoolLecture]:
        assignment = await self._session.get(SchoolQuizAssignment, assignment_id)
        if (
            assignment is None
            or assignment.deleted_at is not None
            or assignment.student_user_id != user.id
        ):
            raise NotFoundError("Quiz assignment not found")
        quiz = await self._session.get(SchoolQuiz, assignment.quiz_id)
        if quiz is None or quiz.deleted_at is not None:
            raise NotFoundError("Quiz not found")
        lecture = await self._session.get(SchoolLecture, quiz.lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        return assignment, quiz, lecture

    async def _require_teacher_scope(
        self,
        user: User,
        lecture: SchoolLecture,
        *,
        allow_coordinator_admin: bool = False,
    ) -> None:
        if user.role == UserRole.TEACHER:
            if lecture.teacher_user_id != user.id or lecture.school_id != user.school_id:
                raise NotFoundError("Lecture not found")
            return
        if allow_coordinator_admin and user.role in (
            UserRole.COORDINATOR,
            UserRole.SCHOOL_ADMIN,
            UserRole.DISTRICT_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ):
            if user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
                if lecture.school_id != user.school_id:
                    raise NotFoundError("Lecture not found")
            return
        raise PermissionDeniedError("Not allowed to view quiz results")

    async def _result_from_attempt(
        self,
        assignment: SchoolQuizAssignment,
        quiz: SchoolQuiz,
        attempt: SchoolQuizAttempt,
    ) -> QuizAttemptResultRead:
        questions = (
            (
                await self._session.execute(
                    select(SchoolQuizQuestion)
                    .where(
                        SchoolQuizQuestion.quiz_id == quiz.id,
                        not_deleted(SchoolQuizQuestion),
                    )
                    .order_by(SchoolQuizQuestion.ordinal)
                )
            )
            .scalars()
            .all()
        )
        answers = attempt.answers_jsonb or {}
        results: list[QuizQuestionResultRead] = []
        for q in questions:
            selected = answers.get(q.id) if isinstance(answers, dict) else None
            selected_s = str(selected) if selected is not None else None
            meta = q.source_metadata_jsonb or {}
            excerpt = meta.get("excerpt") if isinstance(meta, dict) else None
            results.append(
                QuizQuestionResultRead(
                    question_id=q.id,
                    ordinal=q.ordinal,
                    stem=q.stem,
                    selected=selected_s,
                    correct_answer=q.correct_answer,
                    is_correct=selected_s == q.correct_answer,
                    source_excerpt=str(excerpt) if excerpt else None,
                )
            )
        return QuizAttemptResultRead(
            assignment_id=assignment.id,
            attempt_id=attempt.id,
            score=attempt.score,
            max_score=attempt.max_score,
            status=assignment.status.value,
            questions=results,
        )

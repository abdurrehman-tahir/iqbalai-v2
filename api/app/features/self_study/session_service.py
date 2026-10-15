"""Self-study session start/end + due-flashcards surface — T-210."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.events import (
    publish_self_study_session_ended,
    publish_self_study_session_started,
    should_forward_to_flow7,
)
from app.features.self_study.retrieval import build_self_study_retrieval_plan
from app.features.self_study.schemas import (
    DueFlashcardRead,
    DueFlashcardsListRead,
    SelfStudySessionRead,
    SelfStudySessionStart,
)
from app.features.self_study.sessions import (
    IndependentSelfStudySession,
    SchoolSelfStudySession,
    SelfStudySessionStatus,
    event_reaches_flow7,
)
from app.features.student_highlights.models import FlashcardStatus, SchoolStudentFlashcard
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)


class SelfStudySessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    def _to_read(
        self,
        *,
        session_id: str,
        tenant_type: Literal["school", "independent"],
        status: SelfStudySessionStatus,
        material_id: str | None,
        study_plan_id: str | None,
        has_exam_syllabus: bool = False,
        teacher_share: str = "share",
    ) -> SelfStudySessionRead:
        plan = build_self_study_retrieval_plan(
            tenant_type=tenant_type,
            has_exam_syllabus=has_exam_syllabus,
        )
        return SelfStudySessionRead(
            id=session_id,
            tenant_type=tenant_type,
            mode="self_study",
            status=status.value,  # type: ignore[arg-type]
            material_id=material_id,
            study_plan_id=study_plan_id,
            retrieval_primary=plan.primary_collection,
            retrieval_overlays=list(plan.overlays),
            reaches_flow7=event_reaches_flow7(
                tenant_type=tenant_type,
                mode="self_study",
                teacher_activity_share=teacher_share,
            ),
        )

    async def start_session(
        self,
        payload: SelfStudySessionStart,
        claims: dict[str, object],
    ) -> SelfStudySessionRead:
        tenant = get_tenant_type(claims)
        now = datetime.now(timezone.utc)
        if tenant == "independent":
            user = await self._require_independent_student(claims)
            row = IndependentSelfStudySession(
                student_user_id=user.id,
                started_at=now,
                material_id=payload.material_id,
                study_plan_id=payload.study_plan_id,
            )
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
            event_payload = {
                "student_user_id": user.id,
                "session_id": row.id,
                "tenant_type": "independent",
                "mode": "self_study",
                "school_id": "",
            }
            await publish_self_study_session_started(payload=event_payload)
            assert not should_forward_to_flow7(event_payload)
            logger.info("self_study_session_started", tenant="independent", session_id=row.id)
            return self._to_read(
                session_id=row.id,
                tenant_type="independent",
                status=row.status,
                material_id=row.material_id,
                study_plan_id=row.study_plan_id,
            )

        user = await self._require_school_student(claims)
        row = SchoolSelfStudySession(
            student_user_id=user.id,
            started_at=now,
            material_id=payload.material_id,
            study_plan_id=payload.study_plan_id,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        event_payload = {
            "student_user_id": user.id,
            "session_id": row.id,
            "tenant_type": "school",
            "mode": "self_study",
            "school_id": user.school_id or "",
            "teacher_activity_share": "share",
        }
        await publish_self_study_session_started(payload=event_payload)
        logger.info("self_study_session_started", tenant="school", session_id=row.id)
        return self._to_read(
            session_id=row.id,
            tenant_type="school",
            status=row.status,
            material_id=row.material_id,
            study_plan_id=row.study_plan_id,
        )

    async def end_session(
        self,
        session_id: str,
        claims: dict[str, object],
    ) -> SelfStudySessionRead:
        tenant = get_tenant_type(claims)
        now = datetime.now(timezone.utc)
        if tenant == "independent":
            user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(IndependentSelfStudySession).where(
                    IndependentSelfStudySession.id == session_id,
                    IndependentSelfStudySession.student_user_id == user.id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise NotFoundError("Self-study session not found")
            row.status = SelfStudySessionStatus.ENDED
            row.ended_at = now
            await self._session.commit()
            await self._session.refresh(row)
            await publish_self_study_session_ended(
                payload={
                    "student_user_id": user.id,
                    "session_id": row.id,
                    "tenant_type": "independent",
                    "mode": "self_study",
                    "school_id": "",
                }
            )
            return self._to_read(
                session_id=row.id,
                tenant_type="independent",
                status=row.status,
                material_id=row.material_id,
                study_plan_id=row.study_plan_id,
            )

        user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolSelfStudySession).where(
                SchoolSelfStudySession.id == session_id,
                SchoolSelfStudySession.student_user_id == user.id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Self-study session not found")
        row.status = SelfStudySessionStatus.ENDED
        row.ended_at = now
        await self._session.commit()
        await self._session.refresh(row)
        await publish_self_study_session_ended(
            payload={
                "student_user_id": user.id,
                "session_id": row.id,
                "tenant_type": "school",
                "mode": "self_study",
                "school_id": user.school_id or "",
            }
        )
        return self._to_read(
            session_id=row.id,
            tenant_type="school",
            status=row.status,
            material_id=row.material_id,
            study_plan_id=row.study_plan_id,
        )

    async def list_due_flashcards(self, claims: dict[str, object]) -> DueFlashcardsListRead:
        """Surface flashcards as a read-only deck — no py-fsrs schedule (Flow 9)."""
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            # Independent flashcard table not shipped yet (M-15 school-only).
            return DueFlashcardsListRead(items=[], schedule_computed=False)

        user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolStudentFlashcard)
            .where(
                SchoolStudentFlashcard.student_user_id == user.id,
                SchoolStudentFlashcard.status == FlashcardStatus.ACTIVE,
                not_deleted(SchoolStudentFlashcard),
            )
            .order_by(SchoolStudentFlashcard.created_at.desc())
            .limit(100)
        )
        rows = list(result.scalars().all())
        items = [
            DueFlashcardRead(
                id=r.id,
                front_text=r.front_text,
                back_text=r.back_text,
                concept_tag=r.concept_tag,
                due_at=None,
            )
            for r in rows
        ]
        return DueFlashcardsListRead(items=items, schedule_computed=False)

"""Self-study session start/end + due-flashcards surface — T-210."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, cast

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
            status=cast(Literal["active", "ended"], status.value),
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
            ind_user = await self._require_independent_student(claims)
            ind_row = IndependentSelfStudySession(
                student_user_id=ind_user.id,
                started_at=now,
                material_id=payload.material_id,
                study_plan_id=payload.study_plan_id,
            )
            self._session.add(ind_row)
            await self._session.commit()
            await self._session.refresh(ind_row)
            event_payload = {
                "student_user_id": ind_user.id,
                "session_id": ind_row.id,
                "tenant_type": "independent",
                "mode": "self_study",
                "school_id": "",
            }
            await publish_self_study_session_started(payload=event_payload)
            assert not should_forward_to_flow7(event_payload)
            logger.info(
                "self_study_session_started",
                tenant="independent",
                session_id=ind_row.id,
            )
            return self._to_read(
                session_id=ind_row.id,
                tenant_type="independent",
                status=ind_row.status,
                material_id=ind_row.material_id,
                study_plan_id=ind_row.study_plan_id,
            )

        school_user = await self._require_school_student(claims)
        # T-220 — stamp current #72 preference (canonical owner: Flow 8 / user_settings).
        from app.features.student_privacy.service import student_allows_teacher_share

        allows_share = await student_allows_teacher_share(self._session, school_user.id)
        teacher_share = "share" if allows_share else "private"
        school_row = SchoolSelfStudySession(
            student_user_id=school_user.id,
            started_at=now,
            material_id=payload.material_id,
            study_plan_id=payload.study_plan_id,
        )
        self._session.add(school_row)
        await self._session.commit()
        await self._session.refresh(school_row)
        event_payload = {
            "student_user_id": school_user.id,
            "session_id": school_row.id,
            "tenant_type": "school",
            "mode": "self_study",
            "school_id": school_user.school_id or "",
            "teacher_activity_share": teacher_share,
        }
        await publish_self_study_session_started(payload=event_payload)
        logger.info("self_study_session_started", tenant="school", session_id=school_row.id)
        return self._to_read(
            session_id=school_row.id,
            tenant_type="school",
            status=school_row.status,
            material_id=school_row.material_id,
            study_plan_id=school_row.study_plan_id,
            teacher_share=teacher_share,
        )

    async def end_session(
        self,
        session_id: str,
        claims: dict[str, object],
    ) -> SelfStudySessionRead:
        tenant = get_tenant_type(claims)
        now = datetime.now(timezone.utc)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            result = await self._session.execute(
                select(IndependentSelfStudySession).where(
                    IndependentSelfStudySession.id == session_id,
                    IndependentSelfStudySession.student_user_id == ind_user.id,
                )
            )
            ind_row = result.scalar_one_or_none()
            if ind_row is None:
                raise NotFoundError("Self-study session not found")
            ind_row.status = SelfStudySessionStatus.ENDED
            ind_row.ended_at = now
            await self._session.commit()
            await self._session.refresh(ind_row)
            await publish_self_study_session_ended(
                payload={
                    "student_user_id": ind_user.id,
                    "session_id": ind_row.id,
                    "tenant_type": "independent",
                    "mode": "self_study",
                    "school_id": "",
                }
            )
            return self._to_read(
                session_id=ind_row.id,
                tenant_type="independent",
                status=ind_row.status,
                material_id=ind_row.material_id,
                study_plan_id=ind_row.study_plan_id,
            )

        school_user = await self._require_school_student(claims)
        result = await self._session.execute(
            select(SchoolSelfStudySession).where(
                SchoolSelfStudySession.id == session_id,
                SchoolSelfStudySession.student_user_id == school_user.id,
            )
        )
        school_row = result.scalar_one_or_none()
        if school_row is None:
            raise NotFoundError("Self-study session not found")
        school_row.status = SelfStudySessionStatus.ENDED
        school_row.ended_at = now
        await self._session.commit()
        await self._session.refresh(school_row)
        await publish_self_study_session_ended(
            payload={
                "student_user_id": school_user.id,
                "session_id": school_row.id,
                "tenant_type": "school",
                "mode": "self_study",
                "school_id": school_user.school_id or "",
            }
        )
        return self._to_read(
            session_id=school_row.id,
            tenant_type="school",
            status=school_row.status,
            material_id=school_row.material_id,
            study_plan_id=school_row.study_plan_id,
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

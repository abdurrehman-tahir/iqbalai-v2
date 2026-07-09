"""Academic Session service — business logic (T-042)."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.features.academic_sessions.models import AcademicSession
from app.features.academic_sessions.repository import AcademicSessionRepository
from app.features.academic_sessions.schemas import AcademicSessionCreate, ActiveSessionRead
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


def _caller_school_id(claims: dict[str, object]) -> str:
    raw = claims.get("school_id")
    if raw is None or raw == "":
        raise PermissionDeniedError("School scope required to manage academic sessions")
    return str(raw)


class AcademicSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AcademicSessionRepository(session)

    async def list_sessions(self, claims: dict[str, object]) -> list[AcademicSession]:
        school_id = _caller_school_id(claims)
        return await self._repo.list_by_school(school_id)

    async def get_active(self, claims: dict[str, object]) -> ActiveSessionRead:
        school_id = _caller_school_id(claims)
        active = await self._repo.get_active(school_id)
        label = await self._repo.get_school_active_label(school_id)
        from app.features.academic_sessions.schemas import AcademicSessionRead

        return ActiveSessionRead(
            label=label,
            session=AcademicSessionRead.model_validate(active) if active else None,
        )

    async def create_session(
        self, payload: AcademicSessionCreate, claims: dict[str, object], actor_id: str
    ) -> AcademicSession:
        school_id = _caller_school_id(claims)
        existing = await self._repo.get_by_label(school_id, payload.label)
        if existing is not None:
            raise ConflictError(
                f"An academic session labeled '{payload.label}' already exists in this school"
            )

        row = AcademicSession(
            school_id=school_id,
            label=payload.label,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=False,
        )
        created = await self._repo.create(row)

        if payload.set_active:
            created = await self._repo.set_active(created, school_id, payload.label)

        await audit(
            session=self._session,
            action="academic_session.created",
            actor_id=actor_id,
            target_type="academic_session",
            target_id=created.id,
            school_id=school_id,
            metadata={"label": created.label, "is_active": created.is_active},
        )
        logger.info(
            "academic_session_created",
            session_id=created.id,
            school_id=school_id,
            by=actor_id,
        )
        return created

    async def activate_session(
        self, id: str, claims: dict[str, object], actor_id: str
    ) -> AcademicSession:
        school_id = _caller_school_id(claims)
        row = await self._repo.get_by_id(id)
        if row is None or row.deleted_at is not None or row.school_id != school_id:
            raise NotFoundError(f"Academic session '{id}' not found")

        activated = await self._repo.set_active(row, school_id, row.label)
        await audit(
            session=self._session,
            action="academic_session.activated",
            actor_id=actor_id,
            target_type="academic_session",
            target_id=activated.id,
            school_id=school_id,
            metadata={"label": activated.label},
        )
        logger.info("academic_session_activated", session_id=activated.id, by=actor_id)
        return activated

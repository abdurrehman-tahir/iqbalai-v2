"""Subject service — business logic for the school subject catalogue (T-041).

Coordinator owns subject creation AND management; School Admin and higher inherit the
right per §6.19. Subjects are school-scoped: the caller's ``school_id`` (from the JWT)
determines the catalogue acted on — it is never taken from the request body, so a
caller cannot create a subject in another school. A duplicate ``(school_id, name)`` is
surfaced as a ``ConflictError`` (409) rather than letting the DB IntegrityError bubble.
Every mutation is audit-logged (ARCH §14.10).
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
)
from app.features.offerings.repository import OfferingRepository
from app.features.subjects.models import Subject, SubjectStatus
from app.features.subjects.repository import SubjectRepository
from app.features.subjects.schemas import SubjectCreate, SubjectUpdate
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


def _caller_school_id(claims: dict[str, object]) -> str:
    """Return the caller's school scope from the JWT, or 403 if none is present.

    Subjects only exist inside a school; a caller without a ``school_id`` claim (e.g.
    a Platform/District Admin acting without a school context) has no catalogue to act
    on, so the request is rejected rather than silently broadened.
    """
    raw = claims.get("school_id")
    if raw is None or raw == "":
        raise PermissionDeniedError("School scope required to manage subjects")
    return str(raw)


class SubjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SubjectRepository(session)
        self._offering_repo = OfferingRepository(session)

    async def list_subjects(
        self, claims: dict[str, object], include_archived: bool = False
    ) -> list[Subject]:
        """List the caller's school subjects (archived hidden unless requested)."""
        school_id = _caller_school_id(claims)
        return await self._repo.list_by_school(school_id, include_archived=include_archived)

    async def get_subject(self, id: str, claims: dict[str, object]) -> Subject:
        """Fetch a subject in the caller's school; 404 if missing/deleted/cross-school.

        Cross-school access is surfaced as 404 (not 403) so callers cannot probe other
        schools' subject IDs (§5.3 — don't leak existence).
        """
        school_id = _caller_school_id(claims)
        subject = await self._repo.get_by_id(id)
        if subject is None or subject.deleted_at is not None or subject.school_id != school_id:
            raise NotFoundError(f"Subject '{id}' not found")
        return subject

    async def create_subject(
        self, payload: SubjectCreate, claims: dict[str, object], actor_id: str
    ) -> Subject:
        """Create a subject in the caller's school. Rejects a duplicate name (409)."""
        school_id = _caller_school_id(claims)
        existing = await self._repo.get_active_by_name(school_id, payload.name)
        if existing is not None:
            raise ConflictError(f"A subject named '{payload.name}' already exists in this school")

        subject = Subject(
            school_id=school_id,
            name=payload.name,
            language=payload.language,
            status=SubjectStatus.ACTIVE,
        )
        created = await self._repo.create(subject)
        await audit(
            session=self._session,
            action="subject.created",
            actor_id=actor_id,
            target_type="subject",
            target_id=created.id,
            school_id=created.school_id,
            metadata={"name": created.name, "language": created.language},
        )
        logger.info("subject_created", subject_id=created.id, school_id=school_id, by=actor_id)
        return created

    async def update_subject(
        self, id: str, payload: SubjectUpdate, claims: dict[str, object], actor_id: str
    ) -> Subject:
        """Edit a subject's name/language. Rejects a duplicate name (409)."""
        subject = await self.get_subject(id, claims)

        if payload.name is not None and payload.name != subject.name:
            clash = await self._repo.get_active_by_name(subject.school_id, payload.name)
            if clash is not None:
                raise ConflictError(
                    f"A subject named '{payload.name}' already exists in this school"
                )
            subject.name = payload.name
        if payload.language is not None:
            subject.language = payload.language

        updated = await self._repo.update(subject)
        await audit(
            session=self._session,
            action="subject.updated",
            actor_id=actor_id,
            target_type="subject",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"name": updated.name, "language": updated.language},
        )
        logger.info("subject_updated", subject_id=updated.id, by=actor_id)
        return updated

    async def archive_subject(self, id: str, claims: dict[str, object], actor_id: str) -> Subject:
        """Archive a subject (status -> archived); blocked while active offerings exist."""
        subject = await self.get_subject(id, claims)
        active_offerings = await self._offering_repo.count_active_by_subject(subject.id)
        if active_offerings > 0:
            raise PreconditionFailedError(
                f"Cannot archive subject '{subject.name}' while {active_offerings} active "
                "grade offering(s) exist — archive those offerings first"
            )
        subject.status = SubjectStatus.ARCHIVED
        updated = await self._repo.update(subject)
        await audit(
            session=self._session,
            action="subject.archived",
            actor_id=actor_id,
            target_type="subject",
            target_id=updated.id,
            school_id=updated.school_id,
            metadata={"name": updated.name},
        )
        logger.info("subject_archived", subject_id=updated.id, by=actor_id)
        return updated

"""Exam Syllabi service — business logic for syllabi and topic management."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.features.exam_syllabi.models import ExamSyllabus, SyllabusTopic
from app.features.exam_syllabi.repository import ExamSyllabiRepository
from app.features.exam_syllabi.schemas import (
    ExamSyllabusCreate,
    ExamSyllabusUpdate,
    SyllabusTopicCreate,
)

logger = structlog.get_logger(__name__)

# Maximum nesting depth enforced per ARCH §3 curriculum hierarchy rules
_MAX_TOPIC_DEPTH = 4


class ExamSyllabiService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ExamSyllabiRepository(session)

    async def list_syllabi(self) -> list[ExamSyllabus]:
        """List all active (non-deleted) syllabi."""
        return await self._repo.list_syllabi()

    async def get_syllabus(self, id: str) -> ExamSyllabus:
        """Fetch a syllabus by ID; raises NotFoundError if missing or soft-deleted."""
        syllabus = await self._repo.get_by_id(id)
        if syllabus is None or syllabus.deleted_at is not None:
            raise NotFoundError(f"Exam syllabus '{id}' not found")
        return syllabus

    async def create_syllabus(
        self,
        payload: ExamSyllabusCreate,
        created_by: str,
    ) -> ExamSyllabus:
        """Create a new exam syllabus at version_number=1."""
        syllabus = ExamSyllabus(
            name=payload.name,
            exam_board=payload.exam_board,
            region=payload.region,
            grade_range_min=payload.grade_range_min,
            grade_range_max=payload.grade_range_max,
            language=payload.language,
            version_number=1,
            is_active=True,
        )
        created = await self._repo.create(syllabus)
        logger.info(
            "exam_syllabus_created",
            syllabus_id=created.id,
            name=created.name,
            by=created_by,
        )
        return created

    async def update_syllabus(
        self,
        id: str,
        payload: ExamSyllabusUpdate,
        updated_by: str,
    ) -> ExamSyllabus:
        """Update a syllabus and bump its version_number by 1 (immutable audit trail).

        Per versioning rule: every mutation creates a logical v(n+1) by incrementing
        version_number in-place. If a full immutable row strategy is later adopted,
        this service method is the single place to change.
        """
        syllabus = await self.get_syllabus(id)
        prev_version = syllabus.version_number

        if payload.name is not None:
            syllabus.name = payload.name
        if payload.exam_board is not None:
            syllabus.exam_board = payload.exam_board
        if payload.region is not None:
            syllabus.region = payload.region
        if payload.grade_range_min is not None:
            syllabus.grade_range_min = payload.grade_range_min
        if payload.grade_range_max is not None:
            syllabus.grade_range_max = payload.grade_range_max
        if payload.language is not None:
            syllabus.language = payload.language

        syllabus.version_number = prev_version + 1

        updated = await self._repo.update(syllabus)
        logger.info(
            "exam_syllabus_updated",
            syllabus_id=updated.id,
            prev_version=prev_version,
            new_version=updated.version_number,
            by=updated_by,
        )
        return updated

    async def delete_syllabus(self, id: str) -> None:
        """Soft-delete a syllabus.

        Student-pin guard deferred: before deleting, check whether any students have
        this syllabus pinned to their profile and raise PreconditionFailedError if so.
        Skipped at launch — student-syllabus linking is implemented in a later ticket.
        """
        syllabus = await self.get_syllabus(id)
        await self._repo.soft_delete(syllabus)
        logger.info("exam_syllabus_deleted", syllabus_id=id)

    # ── Topics ────────────────────────────────────────────────────────────────

    async def list_topics(self, syllabus_id: str) -> list[SyllabusTopic]:
        """List topics for a syllabus; raises NotFoundError if syllabus is missing."""
        await self.get_syllabus(syllabus_id)
        return await self._repo.list_topics(syllabus_id)

    async def create_topic(
        self,
        syllabus_id: str,
        payload: SyllabusTopicCreate,
    ) -> SyllabusTopic:
        """Create a topic under a syllabus.

        Validates that depth does not exceed _MAX_TOPIC_DEPTH (4).
        The caller must compute depth from the parent topic before calling this method.
        If parent_id is provided, the topic's depth must be parent.depth + 1.
        """
        await self.get_syllabus(syllabus_id)

        # Resolve depth from parent when parent_id is given
        depth = 0
        if payload.parent_id is not None:
            parent = await self._repo.get_topic_by_id(payload.parent_id)
            if parent is None or parent.deleted_at is not None:
                raise NotFoundError(f"Parent topic '{payload.parent_id}' not found")
            depth = parent.depth + 1

        if depth > _MAX_TOPIC_DEPTH:
            raise ValidationError(
                f"Topic depth {depth} exceeds the maximum allowed depth of {_MAX_TOPIC_DEPTH}"
            )

        topic = SyllabusTopic(
            syllabus_id=syllabus_id,
            parent_id=payload.parent_id,
            title=payload.title,
            depth=depth,
            order_index=payload.order_index,
        )
        created = await self._repo.create_topic(topic)
        logger.info(
            "syllabus_topic_created",
            topic_id=created.id,
            syllabus_id=syllabus_id,
            depth=depth,
        )
        return created

    async def delete_topic(self, topic_id: str) -> None:
        """Soft-delete a topic.

        Progress guard deferred: before deleting, verify no student progress records
        reference this topic and raise PreconditionFailedError if so.
        Skipped at launch — student progress model is implemented in a later milestone.
        """
        topic = await self._repo.get_topic_by_id(topic_id)
        if topic is None or topic.deleted_at is not None:
            raise NotFoundError(f"Syllabus topic '{topic_id}' not found")
        await self._repo.soft_delete_topic(topic)
        logger.info("syllabus_topic_deleted", topic_id=topic_id)

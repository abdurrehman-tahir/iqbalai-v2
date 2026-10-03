"""Student-facing concept enrichment — T-190 (flow-6 §3.10 / §5.9, #71).

Cache hit → serve the per-concept row immediately (shared by every student).
Cache miss → insert a PENDING row (the unique (concept_id, tenant_type) key
makes this the generation lock: concurrent students race on the insert, only
the winner enqueues ``concept.enrich_applications``) and return ``pending``.
Stale READY rows keep being served while a refresh is enqueued.

Only concepts that actually occur in a lecture the student can access are
served — this bounds LLM spend to real curriculum concepts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.features.concept_enrichment.cache import LOST_PENDING_AFTER, enqueue_enrichment, is_stale
from app.features.concept_enrichment.models import (
    ConceptApplicationStatus,
    EnrichmentTenantType,
    SchoolConceptApplication,
)
from app.features.concept_enrichment.repository import (
    CareerRepository,
    ConceptApplicationRepository,
)
from app.features.concept_enrichment.schemas import (
    CareerRead,
    ConceptEnrichmentRead,
    LectureConceptRead,
    MiniSimSpecRead,
    RealWorldUseRead,
)
from app.features.lectures.models import SchoolLecture
from app.features.lectures.repository import LectureParagraphRepository, LectureRepository
from app.features.lectures.service import LectureService
from app.features.session_difficulty.subtopic import sub_topic_for_paragraph
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def concept_label(concept_id: str, meta: dict[str, object], lecture_topic: str) -> str:
    """Readable label: explicit sub-topic/topic metadata, else the id's last path
    segment, else the lecture topic."""
    for key in ("sub_topic", "topic"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:500]
    if concept_id:
        return concept_id.rsplit("/", 1)[-1][:500]
    return lecture_topic[:500]


class ConceptEnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._paragraphs = LectureParagraphRepository(session)
        self._lecture_svc = LectureService(session)
        self._applications = ConceptApplicationRepository(session)
        self._careers = CareerRepository(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def _require_lecture(self, student: User, lecture_id: str) -> SchoolLecture:
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None or lecture.current_version_id is None:
            raise NotFoundError("Lecture not found")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")
        return lecture

    async def _concepts(self, lecture: SchoolLecture) -> list[LectureConceptRead]:
        assert lecture.current_version_id is not None
        paragraphs = await self._paragraphs.list_by_version(lecture.current_version_id)
        seen: dict[str, LectureConceptRead] = {}
        for p in sorted(paragraphs, key=lambda x: x.ordinal):
            meta = dict(p.source_metadata_jsonb or {})
            cid = sub_topic_for_paragraph(meta, lecture_topic=lecture.topic)
            if cid and cid not in seen:
                seen[cid] = LectureConceptRead(
                    concept_id=cid,
                    label=concept_label(cid, meta, lecture.topic),
                    first_paragraph_id=p.id,
                    first_paragraph_ordinal=p.ordinal,
                )
        return list(seen.values())

    async def list_lecture_concepts(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[LectureConceptRead]:
        student = await self._require_student(claims)
        lecture = await self._require_lecture(student, lecture_id)
        return await self._concepts(lecture)

    async def require_lecture_concept(
        self, claims: dict[str, object], *, lecture_id: str, concept_id: str
    ) -> tuple[User, LectureConceptRead]:
        """Student + a concept that really occurs in an accessible lecture."""
        student = await self._require_student(claims)
        lecture = await self._require_lecture(student, lecture_id)
        concept = next(
            (c for c in await self._concepts(lecture) if c.concept_id == concept_id), None
        )
        if concept is None:
            raise NotFoundError("Concept not found in this lecture")
        return student, concept

    async def get_enrichment(
        self, claims: dict[str, object], *, lecture_id: str, concept_id: str
    ) -> ConceptEnrichmentRead:
        _student, concept = await self.require_lecture_concept(
            claims, lecture_id=lecture_id, concept_id=concept_id
        )
        tenant = EnrichmentTenantType.SCHOOL
        row = await self._applications.get_for_concept(concept_id, tenant)

        if row is None:
            row = await self._claim_generation(concept_id, concept.label, tenant)
        elif row.status == ConceptApplicationStatus.FAILED or (
            row.status == ConceptApplicationStatus.PENDING
            and row.updated_at < _utcnow() - LOST_PENDING_AFTER
        ):
            # Retry a failed / lost generation on demand (bumps updated_at so
            # concurrent requests don't all re-enqueue).
            row.status = ConceptApplicationStatus.PENDING
            row.updated_at = _utcnow()
            await self._session.commit()
            enqueue_enrichment(row.id)

        refreshing = is_stale(row)
        if refreshing and row.updated_at < _utcnow() - timedelta(hours=1):
            row.updated_at = _utcnow()  # throttle duplicate refresh enqueues
            await self._session.commit()
            enqueue_enrichment(row.id)
        return await self._to_read(row, refreshing=refreshing)

    async def _claim_generation(
        self, concept_id: str, label: str, tenant: EnrichmentTenantType
    ) -> SchoolConceptApplication:
        row = SchoolConceptApplication(
            concept_id=concept_id, concept_label=label, tenant_type=tenant
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            # Another student's request won the insert — reuse its row, no enqueue.
            winner = await self._applications.get_for_concept(concept_id, tenant)
            if winner is None:
                raise
            return winner
        await self._session.commit()
        enqueue_enrichment(row.id)
        return row

    async def _to_read(
        self, row: SchoolConceptApplication, *, refreshing: bool
    ) -> ConceptEnrichmentRead:
        careers = await self._careers.get_many(list(row.career_link_ids or []))
        uses: list[RealWorldUseRead] = []
        for item in row.real_world_uses or []:
            if isinstance(item, dict):
                uses.append(RealWorldUseRead.model_validate(item))
        sim = (
            MiniSimSpecRead.model_validate(row.mini_sim_prompt)
            if row.status == ConceptApplicationStatus.READY and row.mini_sim_prompt
            else None
        )
        return ConceptEnrichmentRead(
            concept_id=row.concept_id,
            concept_label=row.concept_label,
            status=row.status.value,
            real_world_uses=uses,
            careers=[CareerRead(id=c.id, name=c.name, sector=c.sector) for c in careers],
            mini_sim=sim,
            generated_at=row.generated_at,
            refreshing=refreshing,
        )

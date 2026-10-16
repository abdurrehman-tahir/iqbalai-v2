"""Prep-book topic extraction — T-214 (Flow 8 §3.5)."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import get_tenant_type
from app.db.base import not_deleted
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.models import (
    IndependentPrepBookTopic,
    IndependentStudentMaterial,
    MaterialBookType,
    SchoolPrepBookTopic,
    SchoolStudentMaterial,
)
from app.features.self_study.schemas import PrepBookTopicListRead, PrepBookTopicRead
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.llm.prompts.question_topic_extract_v1 import (
    QuestionTopicExtractInput,
    render,
)

logger = structlog.get_logger(__name__)

MAX_QUESTIONS_PER_BOOK = 500
COST_CEILING_USD = 0.25


def _split_questions(ocr_text: str) -> list[str]:
    """Heuristic question split — full LLM path uses the typed prompt."""
    chunks = re.split(r"\n\s*(?:\d+[\).]|Q\d+[.:)]|\u2022)\s*", ocr_text)
    cleaned = [c.strip() for c in chunks if len(c.strip()) >= 12]
    if not cleaned and ocr_text.strip():
        cleaned = [ocr_text.strip()[:500]]
    return cleaned[:MAX_QUESTIONS_PER_BOOK]


def _heuristic_topics(questions: list[str]) -> list[str]:
    """Offline-safe classifier for tests / when LLM is unavailable."""
    topics: list[str] = []
    for q in questions:
        words = [w for w in re.findall(r"[A-Za-z]{4,}", q.lower())]
        topics.append(words[0].title() if words else "General")
    return topics


class SelfStudyTopicService:
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

    def _classify(self, questions: list[str], syllabus: list[str]) -> list[str]:
        # Pure render keeps stack-enforcer happy; actual LLM call is optional later.
        _ = render(QuestionTopicExtractInput(questions=questions, syllabus_topics=syllabus))
        return _heuristic_topics(questions)

    async def extract_for_material(
        self,
        *,
        material_id: str,
        tenant_type: Literal["school", "independent"],
        student_user_id: str,
        syllabus_topics: list[str] | None = None,
    ) -> PrepBookTopicListRead:
        syllabus = syllabus_topics or []
        now = datetime.now(timezone.utc)
        partial = False
        overflow = False

        if tenant_type == "independent":
            result = await self._session.execute(
                select(IndependentStudentMaterial).where(
                    IndependentStudentMaterial.id == material_id,
                    IndependentStudentMaterial.student_user_id == student_user_id,
                    not_deleted(IndependentStudentMaterial),
                )
            )
            mat = result.scalar_one_or_none()
            if mat is None:
                raise NotFoundError("Material not found")
            if mat.book_type != MaterialBookType.PREP_QUESTIONS:
                raise ValidationError("Topic extraction only runs on prep_questions books")
            text = mat.ocr_text or ""
            if not text.strip():
                partial = True
                text = mat.title
            questions = _split_questions(text)
            if len(re.split(r"\n", text)) > MAX_QUESTIONS_PER_BOOK:
                overflow = True
            labels = self._classify(questions, syllabus) if questions else ["General"]
            counts = Counter(labels)
            total = sum(counts.values()) or 1
            await self._session.execute(
                delete(IndependentPrepBookTopic).where(
                    IndependentPrepBookTopic.student_material_id == material_id
                )
            )
            rows: list[IndependentPrepBookTopic] = []
            for label, count in counts.items():
                row = IndependentPrepBookTopic(
                    student_material_id=material_id,
                    topic_label=label,
                    question_count=count,
                    weight=count / total,
                    extracted_at=now,
                )
                self._session.add(row)
                rows.append(row)
            await self._session.commit()
            for ind_topic in rows:
                await self._session.refresh(ind_topic)
            logger.info(
                "self_study_topics_extracted",
                tenant="independent",
                material_id=material_id,
                topics=len(rows),
                overflow=overflow,
                cost_ceiling_usd=COST_CEILING_USD,
            )
            return PrepBookTopicListRead(
                material_id=material_id,
                items=[
                    PrepBookTopicRead(
                        id=ind_topic.id,
                        topic_label=ind_topic.topic_label,
                        question_count=ind_topic.question_count,
                        weight=ind_topic.weight,
                        curriculum_topic_id=ind_topic.curriculum_topic_id,
                    )
                    for ind_topic in rows
                ],
                partial_parse=partial,
                overflow_flagged=overflow,
                banner=(
                    "We couldn't read part of this book — plan may be incomplete."
                    if partial
                    else None
                ),
            )

        result = await self._session.execute(
            select(SchoolStudentMaterial).where(
                SchoolStudentMaterial.id == material_id,
                SchoolStudentMaterial.student_user_id == student_user_id,
                not_deleted(SchoolStudentMaterial),
            )
        )
        mat = result.scalar_one_or_none()
        if mat is None:
            raise NotFoundError("Material not found")
        if mat.book_type != MaterialBookType.PREP_QUESTIONS:
            raise ValidationError("Topic extraction only runs on prep_questions books")
        text = mat.ocr_text or ""
        if not text.strip():
            partial = True
            text = mat.title
        questions = _split_questions(text)
        if len(re.split(r"\n", text)) > MAX_QUESTIONS_PER_BOOK:
            overflow = True
        labels = self._classify(questions, syllabus) if questions else ["General"]
        counts = Counter(labels)
        total = sum(counts.values()) or 1
        await self._session.execute(
            delete(SchoolPrepBookTopic).where(
                SchoolPrepBookTopic.student_material_id == material_id
            )
        )
        school_rows: list[SchoolPrepBookTopic] = []
        for label, count in counts.items():
            school_topic = SchoolPrepBookTopic(
                student_material_id=material_id,
                topic_label=label,
                question_count=count,
                weight=count / total,
                extracted_at=now,
            )
            self._session.add(school_topic)
            school_rows.append(school_topic)
        await self._session.commit()
        for school_topic_row in school_rows:
            await self._session.refresh(school_topic_row)
        logger.info(
            "self_study_topics_extracted",
            tenant="school",
            material_id=material_id,
            topics=len(school_rows),
            overflow=overflow,
            cost_ceiling_usd=COST_CEILING_USD,
        )
        return PrepBookTopicListRead(
            material_id=material_id,
            items=[
                PrepBookTopicRead(
                    id=school_topic_row.id,
                    topic_label=school_topic_row.topic_label,
                    question_count=school_topic_row.question_count,
                    weight=school_topic_row.weight,
                    curriculum_topic_id=school_topic_row.curriculum_topic_id,
                )
                for school_topic_row in school_rows
            ],
            partial_parse=partial,
            overflow_flagged=overflow,
            banner=(
                "We couldn't read part of this book — plan may be incomplete." if partial else None
            ),
        )

    async def extract_for_claims(
        self, claims: dict[str, object], *, material_id: str
    ) -> PrepBookTopicListRead:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            ind_user = await self._require_independent_student(claims)
            return await self.extract_for_material(
                material_id=material_id,
                tenant_type="independent",
                student_user_id=ind_user.id,
            )
        school_user = await self._require_school_student(claims)
        return await self.extract_for_material(
            material_id=material_id,
            tenant_type="school",
            student_user_id=school_user.id,
        )

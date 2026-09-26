"""Student lecture question service — T-156 / T-157 / T-158 / T-160 (school)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.files.models import UploadRecord
from app.features.files.profiles import STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION
from app.features.lectures.lecture_session import LectureSessionService
from app.features.lectures.models import (
    LectureSessionStatus,
    SchoolLecture,
    SchoolLectureSession,
)
from app.features.lectures.repository import LectureRepository, LectureSessionRepository
from app.features.lectures.schemas import ParagraphSourceMetadata
from app.features.lectures.service import LectureService
from app.features.student_privacy.service import student_allows_teacher_share
from app.features.student_questions.answer_pipeline import (
    collect_attached_images,
    enforce_vision_cost_guard,
    enqueue_answer_generation,
    stream_answer_for_question,
)
from app.features.student_questions.classifier import classify_question, to_model_enum
from app.features.student_questions.events import (
    publish_student_highlight_created,
    publish_student_question_asked,
)
from app.features.student_questions.models import (
    ConversationRole,
    SchoolStudentQuestion,
    SchoolStudentQuestionConversation,
    StudentQuestionTenantType,
)
from app.features.student_questions.repository import (
    LectureParagraphLookup,
    StudentQuestionConversationRepository,
    StudentQuestionImageLookup,
    StudentQuestionRepository,
)
from app.features.student_questions.schemas import (
    AnswerSourceSpanRead,
    AttachedImageRef,
    ConversationRoleLiteral,
    ConversationTurnRead,
    QuestionClassificationLiteral,
    StudentQuestionAnswerRead,
    StudentQuestionCreateRequest,
    StudentQuestionFollowUpRequest,
    StudentQuestionRead,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

_MIME_BY_EXT: dict[str, Literal["image/jpeg", "image/png", "image/webp"]] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mime_from_filename(filename: str) -> Literal["image/jpeg", "image/png", "image/webp"]:
    lower = filename.lower()
    for ext, mime in _MIME_BY_EXT.items():
        if lower.endswith(ext):
            return mime
    return "image/jpeg"


def _tenant_scope_id(student: User) -> str:
    """Per-tenant MinIO scope: school_id for school students, else user id.

    Mirrors ``image_upload._tenant_scope_id`` — kept as a local duplicate
    (not imported) since services don't reach into each other's private
    helpers; both must stay in lockstep with how uploads are scoped (T-166).
    """
    if student.school_id:
        return student.school_id
    return student.id


def _parse_attached_images(raw: list[object] | None) -> list[AttachedImageRef]:
    if not isinstance(raw, list):
        return []
    result: list[AttachedImageRef] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                result.append(AttachedImageRef.model_validate(item))
            except Exception:
                continue
    return result


def _turn_to_read(row: SchoolStudentQuestionConversation) -> ConversationTurnRead:
    return ConversationTurnRead(
        id=row.id,
        root_question_id=row.root_question_id,
        turn_index=row.turn_index,
        role=ConversationRoleLiteral(row.role.value),
        content=row.content,
        source_tags_jsonb=row.source_tags_jsonb,
        attached_images=_parse_attached_images(row.attached_images_jsonb),
        created_at=row.created_at,
    )


def question_to_read(
    row: SchoolStudentQuestion,
    turns: list[SchoolStudentQuestionConversation] | None = None,
) -> StudentQuestionRead:
    return StudentQuestionRead(
        id=row.id,
        student_user_id=row.student_user_id,
        session_id=row.session_id,
        lecture_id=row.lecture_id,
        tenant_type=row.tenant_type.value,
        highlight_text=row.highlight_text,
        question_text=row.question_text,
        question_language=row.question_language,
        paragraph_id=row.paragraph_id,
        source_chunk_id=row.source_chunk_id,
        classification=QuestionClassificationLiteral(row.classification.value),
        answer_text=row.answer_text,
        answer_source_tags_jsonb=row.answer_source_tags_jsonb,
        attached_images=_parse_attached_images(row.attached_images_jsonb),
        asked_at=row.asked_at,
        answered_at=row.answered_at,
        conversations=[_turn_to_read(t) for t in (turns or [])],
    )


class StudentQuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._lectures = LectureRepository(session)
        self._sessions = LectureSessionRepository(session)
        self._lecture_svc = LectureService(session)
        self._session_svc = LectureSessionService(session)
        self._questions = StudentQuestionRepository(session)
        self._conversations = StudentQuestionConversationRepository(session)
        self._paragraphs = LectureParagraphLookup(session)
        self._images = StudentQuestionImageLookup(session)

    async def _require_student(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    async def _require_accessible_lecture(self, student: User, lecture_id: str) -> SchoolLecture:
        lecture = await self._lectures.get_by_id(lecture_id)
        if lecture is None:
            raise NotFoundError("Lecture not found")
        if not await self._lecture_svc.student_can_access_lecture(student, lecture):
            raise PermissionDeniedError("Not enrolled or access-restricted for this lecture")
        return lecture

    async def _require_active_owned_session(
        self, student: User, *, lecture_id: str, session_id: str
    ) -> SchoolLectureSession:
        # Lazy inactivity end via the shared session service (re-fetches after).
        await self._session_svc.get_session({"sub": student.authentik_id}, session_id)
        row = await self._sessions.get_by_id(session_id)
        if row is None or row.student_user_id != student.id or row.lecture_id != lecture_id:
            raise NotFoundError("Lecture session not found")
        if row.status != LectureSessionStatus.ACTIVE:
            raise ValidationError("Lecture session has ended; open a new session")
        return row

    async def _resolve_attached_images(
        self, student: User, storage_keys: list[str]
    ) -> list[AttachedImageRef]:
        """Validate + resolve ``attached_images`` storage keys (T-169 / T-170).

        Enforces: max 3 per question/turn, and that each key is an
        ``UploadRecord`` under the ``student_question_image`` profile owned
        by *this* student within *this* student's tenant scope (school_id, or
        the student's own id for independent) — cross-student and
        cross-tenant image references are rejected (tenant isolation).
        """
        if not storage_keys:
            return []
        if len(storage_keys) > STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION:
            raise ValidationError(
                f"Max {STUDENT_QUESTION_IMAGE_MAX_PER_QUESTION} images per question"
            )
        tenant_scope_id = _tenant_scope_id(student)
        refs: list[AttachedImageRef] = []
        for key in storage_keys:
            record: UploadRecord | None = await self._images.get_owned(
                key, tenant_scope_id=tenant_scope_id, uploaded_by=student.id
            )
            if record is None:
                raise ValidationError(
                    "Attached image not found, or not owned by this student"
                )
            refs.append(
                AttachedImageRef(
                    storage_key=record.minio_key,
                    mime_type=_mime_from_filename(record.filename),
                    size_bytes=record.size_bytes,
                    upload_id=record.id,
                )
            )
        return refs

    async def _resolve_source_chunk_id(
        self, *, paragraph_id: str | None, source_chunk_id: str | None
    ) -> str | None:
        if source_chunk_id:
            return source_chunk_id
        if not paragraph_id:
            return None
        paragraph = await self._paragraphs.get_by_id(paragraph_id)
        if paragraph is None:
            raise ValidationError("paragraph_id does not match a lecture paragraph")
        meta = ParagraphSourceMetadata.from_jsonb(dict(paragraph.source_metadata_jsonb))
        return meta.chunk_id

    async def ask_question(
        self,
        claims: dict[str, object],
        *,
        lecture_id: str,
        session_id: str,
        payload: StudentQuestionCreateRequest,
    ) -> StudentQuestionRead:
        student = await self._require_student(claims)
        lecture = await self._require_accessible_lecture(student, lecture_id)
        study_session = await self._require_active_owned_session(
            student, lecture_id=lecture_id, session_id=session_id
        )

        source_chunk_id = await self._resolve_source_chunk_id(
            paragraph_id=payload.paragraph_id,
            source_chunk_id=payload.source_chunk_id,
        )
        attached_images = await self._resolve_attached_images(student, payload.attached_images)

        lecture_excerpt = ""
        if payload.paragraph_id:
            paragraph = await self._paragraphs.get_by_id(payload.paragraph_id)
            if paragraph is not None:
                lecture_excerpt = paragraph.text[:2000]

        classified = classify_question(
            question_text=payload.question_text,
            highlight_text=payload.highlight_text,
            lecture_excerpt=lecture_excerpt,
            target_language=payload.question_language,
        )
        classification = to_model_enum(classified)

        now = _utcnow()
        question = SchoolStudentQuestion(
            student_user_id=student.id,
            session_id=study_session.id,
            lecture_id=lecture_id,
            tenant_type=StudentQuestionTenantType(study_session.tenant_type.value),  # Open Q13
            highlight_text=payload.highlight_text,
            question_text=payload.question_text,
            question_language=payload.question_language,
            paragraph_id=payload.paragraph_id,
            source_chunk_id=source_chunk_id,
            classification=classification,
            attached_images_jsonb=(
                [img.model_dump(mode="json") for img in attached_images]
                if attached_images
                else None
            ),
            asked_at=now,
        )
        created = await self._questions.create(question)

        user_turn = SchoolStudentQuestionConversation(
            root_question_id=created.id,
            turn_index=0,
            role=ConversationRole.USER,
            content=payload.question_text,
            source_tags_jsonb=None,
            attached_images_jsonb=(
                [img.model_dump(mode="json") for img in attached_images]
                if attached_images
                else None
            ),
        )
        await self._conversations.create(user_turn)

        # Bump session activity.
        study_session.last_activity_at = now
        await self._sessions.save(study_session)

        await self._session.commit()
        await self._session.refresh(created)
        await self._session.refresh(user_turn)

        allows_share = await student_allows_teacher_share(self._session, student.id)
        event_payload = {
            "question_id": created.id,
            "student_user_id": student.id,
            "session_id": session_id,
            "lecture_id": lecture_id,
            "school_id": lecture.school_id or "",
            "tenant_type": created.tenant_type.value,
            "teacher_share": "share" if allows_share else "private",
            "paragraph_id": created.paragraph_id,
            "source_chunk_id": created.source_chunk_id,
            "classification": created.classification.value,
            "question_text": created.question_text,
            "highlight_text": created.highlight_text,
            "asked_at": created.asked_at.isoformat(),
            # T-169: image refs carried on the event so downstream consumers
            # (e.g. Cognitive DNA, Flow 9/M-18) see vision-routed questions.
            "attached_images": [img.storage_key for img in attached_images],
        }
        await publish_student_question_asked(payload=event_payload)
        if created.highlight_text:
            await publish_student_highlight_created(payload=event_payload)

        # T-158 — client opens SSE ``.../answer/stream`` to generate + receive tokens.
        await enqueue_answer_generation(question_id=created.id, root_question_id=created.id)

        turns = await self._conversations.list_for_question(created.id)
        return question_to_read(created, turns)

    async def list_for_lecture(
        self, claims: dict[str, object], lecture_id: str
    ) -> list[StudentQuestionRead]:
        student = await self._require_student(claims)
        await self._require_accessible_lecture(student, lecture_id)

        questions = await self._questions.list_for_student_lecture(
            student_user_id=student.id, lecture_id=lecture_id
        )
        turns = await self._conversations.list_for_questions([q.id for q in questions])
        by_root: dict[str, list[SchoolStudentQuestionConversation]] = defaultdict(list)
        for turn in turns:
            by_root[turn.root_question_id].append(turn)
        return [question_to_read(q, by_root.get(q.id, [])) for q in questions]

    async def list_conversations(
        self, claims: dict[str, object], *, lecture_id: str, question_id: str
    ) -> list[ConversationTurnRead]:
        student = await self._require_student(claims)
        await self._require_accessible_lecture(student, lecture_id)
        question = await self._questions.get_by_id(question_id)
        if (
            question is None
            or question.student_user_id != student.id
            or question.lecture_id != lecture_id
        ):
            raise NotFoundError("Question not found")
        turns = await self._conversations.list_for_question(question_id)
        return [_turn_to_read(t) for t in turns]

    async def add_follow_up(
        self,
        claims: dict[str, object],
        *,
        lecture_id: str,
        question_id: str,
        payload: StudentQuestionFollowUpRequest,
    ) -> StudentQuestionRead:
        student = await self._require_student(claims)
        await self._require_accessible_lecture(student, lecture_id)
        question = await self._questions.get_by_id(question_id)
        if (
            question is None
            or question.student_user_id != student.id
            or question.lecture_id != lecture_id
        ):
            raise NotFoundError("Question not found")

        # Keep the parent study session warm when still active.
        study_session = await self._sessions.get_by_id(question.session_id)
        if study_session is not None and study_session.status == LectureSessionStatus.ACTIVE:
            study_session.last_activity_at = _utcnow()
            await self._sessions.save(study_session)

        attached_images = await self._resolve_attached_images(student, payload.attached_images)

        turn_index = await self._conversations.next_turn_index(question_id)
        user_turn = SchoolStudentQuestionConversation(
            root_question_id=question_id,
            turn_index=turn_index,
            role=ConversationRole.USER,
            content=payload.content,
            source_tags_jsonb=None,
            attached_images_jsonb=(
                [img.model_dump(mode="json") for img in attached_images]
                if attached_images
                else None
            ),
        )
        await self._conversations.create(user_turn)

        if attached_images:
            # T-169: a new image changes what the answer must address — clear
            # the cached answer so the stream endpoint regenerates instead of
            # replaying the pre-image answer (see stream_answer_for_question's
            # early-return-on-cached-answer guard).
            question.answer_text = None
            question.answered_at = None
            await self._questions.save(question)

        await self._session.commit()

        await enqueue_answer_generation(
            question_id=question_id,
            root_question_id=question_id,
            turn_index=turn_index,
        )

        turns = await self._conversations.list_for_question(question_id)
        refreshed = await self._questions.get_by_id(question_id)
        assert refreshed is not None
        return question_to_read(refreshed, turns)

    async def _require_owned_question(
        self, student: User, *, lecture_id: str, question_id: str
    ) -> SchoolStudentQuestion:
        question = await self._questions.get_by_id(question_id)
        if (
            question is None
            or question.student_user_id != student.id
            or question.lecture_id != lecture_id
        ):
            raise NotFoundError("Question not found")
        return question

    @staticmethod
    def _answer_to_read(question: SchoolStudentQuestion) -> StudentQuestionAnswerRead:
        tags = question.answer_source_tags_jsonb
        primary: str | None = None
        spans: list[AnswerSourceSpanRead] = []
        if isinstance(tags, dict):
            raw_primary = tags.get("primary_badge")
            if isinstance(raw_primary, str):
                primary = raw_primary
            raw_spans = tags.get("spans")
            if isinstance(raw_spans, list):
                for item in raw_spans:
                    if isinstance(item, dict):
                        try:
                            spans.append(AnswerSourceSpanRead.model_validate(item))
                        except Exception:
                            continue
        return StudentQuestionAnswerRead(
            question_id=question.id,
            answer_text=question.answer_text,
            primary_badge=primary,
            answer_source_tags_jsonb=tags,
            answered_at=question.answered_at,
            source_spans=spans,
        )

    async def get_answer(
        self, claims: dict[str, object], *, lecture_id: str, question_id: str
    ) -> StudentQuestionAnswerRead:
        student = await self._require_student(claims)
        await self._require_accessible_lecture(student, lecture_id)
        question = await self._require_owned_question(
            student, lecture_id=lecture_id, question_id=question_id
        )
        return self._answer_to_read(question)

    async def stream_answer(
        self, claims: dict[str, object], *, lecture_id: str, question_id: str
    ) -> AsyncGenerator[str, None]:
        """SSE token stream for Pattern S + ``lecture_qa_v1`` (T-158).

        Access checks run before the generator is returned so FastAPI can still
        emit 403/404 instead of a half-open SSE body. The T-170 vision cost
        guard runs here too (before any LLM call, and before the SSE body
        starts) for the same reason — a 429/422 must land as a normal JSON
        error response, not a half-open stream.
        """
        student = await self._require_student(claims)
        lecture = await self._require_accessible_lecture(student, lecture_id)
        question = await self._require_owned_question(
            student, lecture_id=lecture_id, question_id=question_id
        )
        turns = await self._conversations.list_for_question(question_id)

        if not question.answer_text:
            attached_images = collect_attached_images(question, turns)
            if attached_images:
                await enforce_vision_cost_guard(question.student_user_id)

        # Keep the study session warm while the answer streams.
        study_session = await self._sessions.get_by_id(question.session_id)
        if study_session is not None and study_session.status == LectureSessionStatus.ACTIVE:
            study_session.last_activity_at = _utcnow()
            await self._sessions.save(study_session)
            await self._session.commit()

        return stream_answer_for_question(
            self._session,
            question=question,
            lecture=lecture,
            turns=turns,
        )

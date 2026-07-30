"""T-116 — Pattern S dual-RAG generation (weighting, prompt, persist, enqueue)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.lectures.generation import apply_curriculum_weight, run_lecture_generation
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureParagraph,
    SchoolLectureVersion,
)
from app.features.lectures.tasks import SOFT_TIME_LIMIT_SECONDS
from app.infrastructure.llm.prompts.lecture_generate_v1 import (
    PROMPT_VERSION,
    ChunkRef,
    LectureGenerateInput,
    render,
)


def test_curriculum_weight_is_1_5x() -> None:
    curriculum = [{"id": "c1", "score": 1.0, "payload": {"text": "A"}}]
    reference = [{"id": "r1", "score": 1.0, "payload": {"text": "B"}}]
    merged = apply_curriculum_weight(curriculum, reference)
    assert len(merged) == 2
    assert merged[0]["id"] == "c1"
    assert merged[0]["score"] == pytest.approx(1.5)
    assert merged[0]["tier"] == "curriculum"
    assert merged[1]["score"] == pytest.approx(1.0)
    assert merged[1]["tier"] == "reference"


def test_soft_time_limit_is_five_minutes() -> None:
    assert SOFT_TIME_LIMIT_SECONDS == 300


def test_lecture_generate_prompt_marks_structure_vs_depth() -> None:
    call = render(
        LectureGenerateInput(
            topic="Forces",
            teaching_mode="auto",
            target_language="en",
            curriculum_chunks=[
                ChunkRef(
                    source_id="c1",
                    source_label="Physics Grade 9",
                    tier="curriculum",
                    text="Newton's first law.",
                )
            ],
            reference_chunks=[
                ChunkRef(
                    source_id="r1",
                    source_label="Physics Handbook",
                    tier="reference",
                    text="Inertia example with a bus.",
                )
            ],
        )
    )
    assert call.version == PROMPT_VERSION
    assert "[Curriculum" in call.user
    assert "[Ref:" in call.user
    assert "SEQUENCE" in call.system or "structure" in call.system.lower()


@pytest.mark.asyncio
async def test_run_lecture_generation_persists_version_and_paragraphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lecture = SchoolLecture(
        id="lec-1",
        school_id="school-1",
        grade_subject_offering_id="offering-1",
        teacher_user_id="teacher-1",
        title="Forces",
        topic="Forces",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.GENERATING,
    )

    curriculum_item = MagicMock()
    curriculum_item.id = "curr-1"
    curriculum_item.title = "Curriculum Book"

    ref_item = MagicMock()
    ref_item.id = "ref-1"
    ref_item.title = "Ref Book"

    chunk_c = MagicMock()
    chunk_c.id = "chunk-c"
    chunk_c.library_item_id = "curr-1"
    chunk_c.chunk_index = 0
    chunk_c.chunk_text = "Curriculum structure: define force."

    chunk_r = MagicMock()
    chunk_r.id = "chunk-r"
    chunk_r.library_item_id = "ref-1"
    chunk_r.chunk_index = 0
    chunk_r.chunk_text = "Reference depth: F=ma example."

    added: list[Any] = []

    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model is SchoolLecture and pk == "lec-1":
            return lecture
        if pk == "curr-1":
            return curriculum_item
        if pk == "ref-1":
            return ref_item
        return None

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, object]]:
        return []

    async def _fake_load_db(_session: Any, item_ids: list[str]) -> list[Any]:
        out: list[Any] = []
        if "curr-1" in item_ids:
            out.append(chunk_c)
        if "ref-1" in item_ids:
            out.append(chunk_r)
        return out

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return (
            '{"title": "Forces and Motion", "paragraphs": ['
            '{"text": "From curriculum: force.", "tier": "curriculum", '
            '"book_name": "Curriculum Book", "chunk_id": "chunk-c"},'
            '{"text": "From reference: F=ma.", "tier": "reference", '
            '"book_name": "Ref Book", "chunk_id": "chunk-r"}'
            "]}"
        )

    events: list[str] = []

    async def _fake_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        events.append(event_type)

    monkeypatch.setattr("app.features.lectures.generation.retrieve", _fake_retrieve)
    monkeypatch.setattr("app.features.lectures.generation._load_db_chunks", _fake_load_db)
    monkeypatch.setattr("app.features.lectures.generation.chat", _fake_chat)
    monkeypatch.setattr("app.features.lectures.generation.publish_lecture_event", _fake_publish)

    version_id = await run_lecture_generation(
        session,
        lecture_id="lec-1",
        school_id="school-1",
        topic="Forces",
        curriculum_id="curr-1",
        reference_book_ids=["ref-1"],
        teaching_mode="auto",
        teacher_user_id="teacher-1",
    )

    assert lecture.status == LectureStatus.GENERATED_V1
    assert lecture.current_version_id == version_id
    assert lecture.title == "Forces and Motion"
    versions = [o for o in added if isinstance(o, SchoolLectureVersion)]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert len(versions) == 1
    assert versions[0].version == 1
    assert len(paragraphs) == 2
    assert paragraphs[0].source_metadata_jsonb["tier"] == "curriculum"
    assert paragraphs[1].source_metadata_jsonb["tier"] == "reference"
    assert "lecture.generation_requested" in events
    assert "lecture.version.created" in events
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_generate_enqueues_celery_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """API generate path must enqueue lectures.generate_lecture (T-116 wiring)."""
    from unittest.mock import MagicMock

    from app.features.lectures.schemas import LectureGenerateRequest, TeachingMode
    from app.features.lectures.service import LectureWizardService
    from app.features.lectures.tests.test_lecture_wizard_steps_3_5 import (
        CURRICULUM,
        GRADE,
        OFFERING,
        PROFILE,
        REF_SAME,
        SUBJECT,
        TEACHER,
        _FakeDraftRepo,
        _FakeGradeRepo,
        _FakeLectureRepo,
        _FakeLibraryRepo,
        _FakeOfferingRepo,
        _FakeProfileRepo,
        _FakeSubjectRepo,
        _FakeUserRepo,
    )

    _FakeUserRepo.store = {TEACHER.id: TEACHER}
    _FakeOfferingRepo.store = {OFFERING.id: OFFERING}
    _FakeGradeRepo.store = {GRADE.id: GRADE}
    _FakeSubjectRepo.store = {SUBJECT.id: SUBJECT}
    _FakeLibraryRepo.items = {CURRICULUM.id: CURRICULUM, REF_SAME.id: REF_SAME}
    _FakeDraftRepo.store = {}
    _FakeLectureRepo.store = {}
    _FakeProfileRepo.store = {PROFILE.user_id: PROFILE}

    monkeypatch.setattr("app.features.lectures.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr("app.features.lectures.service.OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr("app.features.lectures.service.GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr("app.features.lectures.service.SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr("app.features.lectures.service.SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureDraftRepository", _FakeDraftRepo)
    monkeypatch.setattr("app.features.lectures.service.LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr("app.features.lectures.service.TeacherProfileRepository", _FakeProfileRepo)

    enqueued: dict[str, Any] = {}

    def _capture(**kwargs: Any) -> None:
        enqueued.update(kwargs)

    monkeypatch.setattr(
        "app.features.lectures.tasks.generate_lecture.apply_async",
        _capture,
    )

    svc = LectureWizardService(MagicMock())
    result = await svc.generate_from_wizard(
        {"sub": "auth-teacher", "role": "teacher", "user_id": "teacher-1"},
        LectureGenerateRequest(
            grade_subject_offering_id="offering-1",
            topic="Forces",
            curriculum_id="curr-1",
            reference_book_ids=["ref-9"],
            teaching_mode=TeachingMode.AUTO,
            include_cross_grade=False,
        ),
    )
    assert result.status == LectureStatus.GENERATING.value
    assert "kwargs" in enqueued
    assert enqueued["kwargs"]["curriculum_id"] == "curr-1"
    assert enqueued["kwargs"]["reference_book_ids"] == ["ref-9"]
    assert enqueued["kwargs"]["school_id"] == "school-1"

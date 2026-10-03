"""T-185 — highlight persistence + yellow-mark restore (flow-6 §3.6 / §5.5)."""

# mypy: disable-error-code="method-assign"

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import PermissionDeniedError, setup_exception_handlers
from app.db.base import Base, SoftDeleteMixin
from app.features.lectures.models import (
    LectureStatus,
    LectureTenantType,
    SchoolLecture,
    SchoolLectureParagraph,
)
from app.features.student_highlights.anchoring import locate_anchor, resolve_mark
from app.features.student_highlights.models import HighlightTenantType, SchoolStudentHighlight
from app.features.student_highlights.schemas import StudentHighlightRead
from app.features.student_highlights.service import StudentHighlightService, resolve_marks
from app.features.users.models import UserRole

_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "school"
    / "0073_student_highlights.py"
)

PARA_TEXT = "Force equals mass times acceleration. Newton's second law."


def _para(pid: str = "p1", ordinal: int = 0, text: str = PARA_TEXT, version: str = "ver-1") -> Any:
    return SchoolLectureParagraph(
        id=pid,
        lecture_version_id=version,
        ordinal=ordinal,
        text=text,
        source_metadata_jsonb={"tier": "curriculum", "chunk_id": "chunk-9"},
    )


def _lecture(**overrides: Any) -> SchoolLecture:
    defaults: dict[str, Any] = {
        "id": "lec-1",
        "school_id": "school-1",
        "title": "Newton",
        "topic": "Forces",
        "status": LectureStatus.PUBLISHED,
        "current_version_id": "ver-1",
        "grade_subject_offering_id": "gso-1",
        "tenant_type": LectureTenantType.SCHOOL,
    }
    defaults.update(overrides)
    return SchoolLecture(**defaults)


def _highlight(**overrides: Any) -> SchoolStudentHighlight:
    defaults: dict[str, Any] = {
        "id": "h1",
        "student_user_id": "stu-1",
        "lecture_id": "lec-1",
        "lecture_version_id": "ver-1",
        "paragraph_id": "p1",
        "paragraph_ordinal": 0,
        "text_range_offset": 13,
        "text_range_length": 4,
        "highlighted_text": "mass",
        "question_id": "q1",
        "concept_tag": "forces/newton-2",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return SchoolStudentHighlight(**defaults)


def _user(**overrides: Any) -> MagicMock:
    user = MagicMock()
    user.id = overrides.get("id", "stu-1")
    user.role = overrides.get("role", UserRole.STUDENT)
    user.deleted_at = None
    user.school_id = overrides.get("school_id", "school-1")
    return user


# --- model / migration --------------------------------------------------------


def test_table_registered_school_only_with_soft_delete() -> None:
    assert "school.student_highlights" in Base.metadata.tables
    assert "independent.student_highlights" not in Base.metadata.tables
    assert issubclass(SchoolStudentHighlight, SoftDeleteMixin)


def test_columns_cover_ticket_intent() -> None:
    cols = {c.name for c in Base.metadata.tables["school.student_highlights"].columns}
    assert {
        "id",
        "lecture_id",
        "student_user_id",
        "paragraph_ordinal",
        "text_range_offset",
        "text_range_length",
        "highlighted_text",
        "question_id",
        "concept_tag",
        "created_at",
        "tenant_type",
        "deleted_at",
    } <= cols


def test_user_fk_cascades_per_arch_4_6() -> None:
    table = Base.metadata.tables["school.student_highlights"]
    fks = {fk.parent.name: fk.ondelete for fk in table.foreign_keys}
    assert fks["student_user_id"] == "CASCADE"
    assert fks["lecture_id"] == "CASCADE"
    assert fks["question_id"] == "SET NULL"


def test_tenant_type_defaults_school() -> None:
    assert _highlight().tenant_type == HighlightTenantType.SCHOOL


def test_migration_revises_0072_and_is_reversible() -> None:
    text = _MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0073"' in text
    assert 'down_revision: str = "school_0072"' in text
    assert "create_type=False" in text
    assert 'op.drop_table("student_highlights"' in text


# --- anchoring ----------------------------------------------------------------


def test_locate_anchor_trusts_matching_hint() -> None:
    anchor = locate_anchor(PARA_TEXT, "mass", 13)
    assert anchor is not None and (anchor.offset, anchor.length) == (13, 4)


def test_locate_anchor_falls_back_to_search_on_bad_hint() -> None:
    anchor = locate_anchor(PARA_TEXT, "mass", 0)
    assert anchor is not None and anchor.offset == 13


def test_locate_anchor_rejects_text_not_in_paragraph() -> None:
    assert locate_anchor(PARA_TEXT, "photosynthesis", None) is None
    assert locate_anchor(PARA_TEXT, "", 0) is None


def test_resolve_mark_restores_at_original_position() -> None:
    mark = resolve_mark(
        paragraph_ordinal=0,
        offset=13,
        length=4,
        highlighted_text="mass",
        current_paragraphs=[(0, "p1-v2", PARA_TEXT)],
    )
    # Unchanged paragraph in a new version keeps its mark (new paragraph id).
    assert mark is not None and mark.paragraph_id == "p1-v2" and mark.offset == 13


def test_resolve_mark_drops_silently_when_span_edited_away() -> None:
    edited = "Force is a push or a pull."
    assert (
        resolve_mark(
            paragraph_ordinal=0,
            offset=13,
            length=4,
            highlighted_text="mass",
            current_paragraphs=[(0, "p1-v2", edited)],
        )
        is None
    )


def test_resolve_mark_drops_when_paragraph_removed() -> None:
    assert (
        resolve_mark(
            paragraph_ordinal=3,
            offset=0,
            length=4,
            highlighted_text="mass",
            current_paragraphs=[(0, "p1", PARA_TEXT)],
        )
        is None
    )


def test_resolve_marks_keeps_row_but_nulls_mark_on_reedit() -> None:
    rows = [_highlight()]
    out = resolve_marks(rows, [_para(pid="p9", text="Totally rewritten paragraph.")])
    assert len(out) == 1  # the highlight survives (its flashcard too — T-186)
    assert out[0].mark is None


# --- service write path -------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_for_question_creates_tenant_tagged_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    svc = StudentHighlightService(session)
    monkeypatch.setattr(
        "app.features.student_highlights.service.resolve_sub_topic_id",
        AsyncMock(return_value="forces/newton-2"),
    )

    row = await svc.persist_for_question(
        student_user_id="stu-1",
        lecture=_lecture(),
        question_id="q1",
        tenant_type="school",
        paragraph=_para(),
        highlighted_text="mass",
        offset_hint=13,
        source_chunk_id="chunk-9",
    )

    assert row is not None
    assert (row.paragraph_ordinal, row.text_range_offset, row.text_range_length) == (0, 13, 4)
    assert row.highlighted_text == "mass"
    assert row.question_id == "q1"  # ai_response_ref
    assert row.concept_tag == "forces/newton-2"
    assert row.tenant_type == HighlightTenantType.SCHOOL
    assert row.lecture_version_id == "ver-1"
    session.add.assert_called_once_with(row)


@pytest.mark.asyncio
async def test_persist_for_question_skips_unanchorable_or_free_form() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    svc = StudentHighlightService(session)
    kwargs: dict[str, Any] = {
        "student_user_id": "stu-1",
        "lecture": _lecture(),
        "question_id": "q1",
        "tenant_type": "school",
        "offset_hint": None,
        "source_chunk_id": None,
    }
    assert await svc.persist_for_question(paragraph=None, highlighted_text="mass", **kwargs) is None
    assert (
        await svc.persist_for_question(paragraph=_para(), highlighted_text=None, **kwargs) is None
    )
    assert (
        await svc.persist_for_question(
            paragraph=_para(), highlighted_text="not in paragraph", **kwargs
        )
        is None
    )
    session.add.assert_not_called()


# --- service read path --------------------------------------------------------


def _read_svc(user: Any, *, can_access: bool, rows: list[SchoolStudentHighlight]) -> Any:
    svc = StudentHighlightService(AsyncMock())
    svc._users = MagicMock()
    svc._users.get_by_authentik_id = AsyncMock(return_value=user)
    svc._lectures = MagicMock()
    svc._lectures.get_by_id = AsyncMock(return_value=_lecture())
    svc._lecture_svc = MagicMock()
    svc._lecture_svc.student_can_access_lecture = AsyncMock(return_value=can_access)
    svc._paragraphs = MagicMock()
    svc._paragraphs.list_by_version = AsyncMock(return_value=[_para()])
    svc._highlights = MagicMock()
    svc._highlights.list_for_student_lecture = AsyncMock(return_value=rows)
    return svc


@pytest.mark.asyncio
async def test_list_for_lecture_restores_marks_owner_scoped() -> None:
    svc = _read_svc(_user(), can_access=True, rows=[_highlight()])
    out = await svc.list_for_lecture({"sub": "auth-1"}, "lec-1")
    assert out[0].mark is not None
    assert (out[0].mark.paragraph_id, out[0].mark.offset, out[0].mark.length) == ("p1", 13, 4)
    # Owner scope: the repository is queried with the caller's own id only.
    svc._highlights.list_for_student_lecture.assert_awaited_once_with(
        student_user_id="stu-1", lecture_id="lec-1"
    )


@pytest.mark.asyncio
async def test_list_for_lecture_other_student_sees_only_own_rows() -> None:
    other = _user(id="stu-2")
    svc = _read_svc(other, can_access=True, rows=[])
    out = await svc.list_for_lecture({"sub": "auth-2"}, "lec-1")
    assert out == []
    svc._highlights.list_for_student_lecture.assert_awaited_once_with(
        student_user_id="stu-2", lecture_id="lec-1"
    )


@pytest.mark.asyncio
async def test_list_for_lecture_denies_other_school_or_gso() -> None:
    # A student of another school / outside the lecture's GSO fails the
    # viewer's access gate before any highlight is read.
    svc = _read_svc(_user(school_id="school-2"), can_access=False, rows=[_highlight()])
    with pytest.raises(PermissionDeniedError):
        await svc.list_for_lecture({"sub": "auth-x"}, "lec-1")
    svc._highlights.list_for_student_lecture.assert_not_called()


@pytest.mark.asyncio
async def test_list_for_lecture_rejects_non_student() -> None:
    svc = _read_svc(_user(role=UserRole.TEACHER), can_access=True, rows=[_highlight()])
    with pytest.raises(PermissionDeniedError):
        await svc.list_for_lecture({"sub": "auth-t"}, "lec-1")


# --- API contract -------------------------------------------------------------


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client(role: str) -> AsyncClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db

    async def _claims() -> dict[str, object]:
        return {"sub": "auth-1", "role": role, "user_id": "stu-1", "tenant_type": "school"}

    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_lists_highlights_with_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    read = resolve_marks([_highlight()], [_para()])

    async def _list(self: Any, claims: Any, lecture_id: str) -> list[StudentHighlightRead]:
        assert lecture_id == "lec-1"
        return read

    monkeypatch.setattr(StudentHighlightService, "list_for_lecture", _list)
    async with _client("student") as client:
        res = await client.get("/api/v1/students/me/lectures/lec-1/highlights")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body[0]["highlighted_text"] == "mass"
    assert body[0]["mark"] == {"paragraph_id": "p1", "offset": 13, "length": 4}
    # Response shape matches the declared response_model exactly.
    StudentHighlightRead.model_validate(body[0])


@pytest.mark.asyncio
async def test_api_service_permission_error_maps_to_403(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _deny(self: Any, claims: Any, lecture_id: str) -> list[StudentHighlightRead]:
        raise PermissionDeniedError("Not enrolled")

    monkeypatch.setattr(StudentHighlightService, "list_for_lecture", _deny)
    async with _client("student") as client:
        res = await client.get("/api/v1/students/me/lectures/lec-1/highlights")
    assert res.status_code == 403

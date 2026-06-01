"""Unit tests for Platform Library service (T-024)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.features.library.models import PlatformReferenceBook
from app.features.library.schemas import LibraryBookUploadRequest, LibraryUploadResponse
from app.features.library.service import LibraryService


def _make_book(**kwargs: object) -> PlatformReferenceBook:
    book = PlatformReferenceBook(
        id="book-1",
        upload_id="upload-1",
        title="Physics Grade 9",
        content_type="curriculum",
        sha256="abc123",
        status="processing",
        language="en",
    )
    for k, v in kwargs.items():
        setattr(book, k, v)
    return book


@pytest.mark.asyncio
async def test_upload_deduplication_returns_existing() -> None:
    """When SHA-256 matches an existing non-deleted book, the existing entry is returned."""
    mock_session = AsyncMock()
    svc = LibraryService(mock_session)

    existing_book = _make_book(status="available")
    meta = LibraryBookUploadRequest(title="Physics Grade 9")

    with (
        patch.object(
            svc._repo,
            "get_by_sha256",
            return_value=existing_book,
        ),
        patch("app.features.library.service.sha256_of_bytes", return_value="abc123"),
    ):
        result = await svc.upload(
            data=b"%PDF-fake",
            filename="physics.pdf",
            meta=meta,
            actor_id="admin-1",
        )

    assert isinstance(result, LibraryUploadResponse)
    assert result.status == "duplicate"
    assert result.book_id == existing_book.id


@pytest.mark.asyncio
async def test_upload_new_book_creates_record_and_queues_task() -> None:
    """A fresh upload creates a PlatformReferenceBook and enqueues the ingestion task."""
    from app.features.files.schemas import UploadInitiated, UploadStatus

    mock_session = AsyncMock()
    svc = LibraryService(mock_session)

    new_book = _make_book(id="book-new")
    meta = LibraryBookUploadRequest(title="New Book", language="ur")
    upload_result = UploadInitiated(
        upload_id="upload-new",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-new",
    )

    with (
        patch.object(svc._repo, "get_by_sha256", return_value=None),
        patch.object(svc._repo, "save", return_value=new_book),
        patch("app.features.library.service.sha256_of_bytes", return_value="newsha"),
        patch("app.features.library.service.run_upload_pipeline", return_value=upload_result),
        patch("app.features.library.service.audit", return_value=None),
        patch("app.features.library.tasks.ingest_platform_book.apply_async") as mock_task,
    ):
        result = await svc.upload(
            data=b"%PDF-new",
            filename="newbook.pdf",
            meta=meta,
            actor_id="admin-2",
        )

    assert result.status == "processing"
    assert result.book_id == new_book.id
    mock_task.assert_called_once()


@pytest.mark.asyncio
async def test_soft_delete_raises_when_not_found() -> None:
    """Deleting a non-existent book raises NotFoundError."""
    from app.core.exceptions import NotFoundError

    mock_session = AsyncMock()
    svc = LibraryService(mock_session)

    with patch.object(svc._repo, "get_by_id", return_value=None):
        with pytest.raises(NotFoundError):
            await svc.soft_delete("nonexistent-id", actor_id="admin-1")

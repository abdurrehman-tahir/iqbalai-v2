"""Unit tests for school library ingestion task — T-056."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    SchoolLibraryItem,
)
from app.features.library.school_tasks import ingest_school_library_item


def _item(**kwargs: object) -> SchoolLibraryItem:
    base = SchoolLibraryItem(
        id="item-1",
        school_id="school-1",
        title="Physics Notes",
        content_type=LibraryContentType.REFERENCE,
        language="en",
        subject_id=None,
        grade_level_ordinal=None,
        storage_key="school-library/school-1/notes.pdf",
        sha256="a" * 64,
        ingestion_status=LibraryIngestionStatus.PENDING,
        created_by="teacher-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_ingest_skips_when_already_available() -> None:
    item = _item(ingestion_status=LibraryIngestionStatus.AVAILABLE)

    with patch("app.features.library.school_tasks.run_db", return_value=item):
        result = ingest_school_library_item.run("item-1", "school-1")

    assert result["status"] == "available"
    assert result["skipped"] is True


def test_ingest_pipeline_marks_available() -> None:
    item = _item()
    fake_qdrant = MagicMock()
    fake_qdrant.get_collections.return_value.collections = []

    with (
        patch("app.features.library.school_tasks.run_db") as mock_run_db,
        patch("app.features.library.school_tasks.download_bytes", return_value=b"%PDF"),
        patch(
            "app.features.library.school_tasks.extract_text_from_pdf",
            return_value=[{"page": 1, "text": "Newton laws of motion." * 20}],
        ),
        patch("app.features.library.school_tasks.chunk_text", return_value=["chunk-a", "chunk-b"]),
        patch("app.features.library.school_tasks.embed_sync", return_value=[[0.1], [0.2]]),
        patch("app.features.library.school_tasks.QdrantClient", return_value=fake_qdrant),
    ):
        mock_run_db.side_effect = [
            item,  # _load_item
            True,  # _mark_ingesting
            None,  # _clear_existing_chunks
            None,  # _persist_chunks
            None,  # _mark_status available
        ]
        result = ingest_school_library_item.run("item-1", "school-1")

    assert result["status"] == "available"
    assert result["chunk_count"] == 2
    fake_qdrant.upsert.assert_called_once()

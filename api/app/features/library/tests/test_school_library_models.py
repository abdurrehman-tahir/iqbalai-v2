"""Unit tests for school library ORM models — T-054."""

from __future__ import annotations

from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
    SchoolLibraryItemSelection,
)


def test_library_item_enum_values() -> None:
    assert LibraryContentType.CURRICULUM.value == "curriculum"
    assert LibraryContentType.REFERENCE.value == "reference"
    assert LibraryVisibility.PRIVATE.value == "private"
    assert LibraryVisibility.SCHOOL_PUBLIC.value == "school_public"
    assert LibraryIngestionStatus.PENDING.value == "pending"
    assert LibraryIngestionStatus.AVAILABLE.value == "available"


def test_library_item_model_fields() -> None:
    item = SchoolLibraryItem(
        id="item-1",
        school_id="school-1",
        title="Punjab Physics Grade 9",
        content_type=LibraryContentType.CURRICULUM,
        language="en",
        subject_id=None,
        grade_level_ordinal=9,
        storage_key="school-library/school-1/curriculum.pdf",
        sha256="c" * 64,
        ingestion_status=LibraryIngestionStatus.PENDING,
        topic_tree_jsonb=None,
        created_by="user-1",
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
    )
    assert item.grade_level_ordinal == 9
    assert item.content_type is LibraryContentType.CURRICULUM


def test_library_item_selection_model() -> None:
    selection = SchoolLibraryItemSelection(
        id="sel-1",
        library_item_id="item-1",
        user_id="user-1",
    )
    assert selection.library_item_id == "item-1"
    assert selection.user_id == "user-1"

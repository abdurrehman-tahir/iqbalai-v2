"""Auto-derived edit_summary annotation tests (T-130, feeds T-137's timeline)."""

from __future__ import annotations

from app.features.lectures.edit_summary import derive_edit_summary


def test_first_version_has_no_annotations() -> None:
    """previous_body=None — v1, nothing to diff against."""
    assert derive_edit_summary(previous_body=None, new_body="Some content.") is None


def test_unchanged_body_has_no_annotations() -> None:
    assert derive_edit_summary(previous_body="Same.", new_body="Same.") is None


def test_added_content_annotation() -> None:
    result = derive_edit_summary(previous_body="Short.", new_body="Short. A bit more.")
    assert result == ["Added content"]


def test_trimmed_content_annotation() -> None:
    result = derive_edit_summary(previous_body="A longer sentence here.", new_body="Shorter.")
    assert result == ["Trimmed content"]


def test_substantial_rewrite_annotation() -> None:
    result = derive_edit_summary(previous_body="Short.", new_body="x" * 500)
    assert result == ["Substantial rewrite"]


def test_extra_annotations_from_voice_or_image_are_preserved() -> None:
    """T-131/T-132 append their own annotation via extra_annotations."""
    result = derive_edit_summary(
        previous_body="Short.",
        new_body="Short. A bit more.",
        extra_annotations=["Applied voice edit"],
    )
    assert result is not None
    assert "Applied voice edit" in result
    assert "Added content" in result


def test_extra_annotations_alone_survive_unchanged_body() -> None:
    """Image insert can change content_jsonb without changing extracted plain
    text (e.g. an image node contributes no text) — the annotation still shows.
    """
    result = derive_edit_summary(
        previous_body="Same.",
        new_body="Same.",
        extra_annotations=["Image inserted"],
    )
    assert result == ["Image inserted"]

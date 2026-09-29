"""Sub-topic resolution: source_chunk_id → lecture_paragraphs → topic_tree (T-175)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lectures.models import SchoolLecture, SchoolLectureParagraph


def _sub_topic_from_metadata(meta: dict[str, Any], *, source_chunk_id: str) -> str:
    """Extract a stable sub-topic id from paragraph provenance metadata."""
    for key in ("sub_topic_id", "topic_id", "topic_node_id"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    path = meta.get("topic_path")
    if isinstance(path, list) and path:
        joined = "/".join(str(p) for p in path if p)
        if joined:
            return joined[:128]
    if isinstance(path, str) and path.strip():
        return path.strip()[:128]
    topic = meta.get("topic") or meta.get("sub_topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()[:128]
    # Fallback: chunk id is the finest stable curriculum pointer we have.
    return source_chunk_id[:128]


async def resolve_sub_topic_id(
    session: AsyncSession,
    *,
    source_chunk_id: str | None,
    lecture_id: str | None = None,
    paragraph_id: str | None = None,
) -> str | None:
    """Map a question's source_chunk_id to a curriculum sub-topic identifier.

    Resolution order:
    1. paragraph by id (if provided) → metadata
    2. paragraph whose ``source_metadata_jsonb.chunk_id`` matches source_chunk_id
    3. lecture.topic when lecture_id is known
    4. source_chunk_id itself
    """
    if paragraph_id:
        para = await session.get(SchoolLectureParagraph, paragraph_id)
        if para is not None:
            meta = dict(para.source_metadata_jsonb or {})
            chunk = source_chunk_id or str(meta.get("chunk_id") or "")
            if chunk:
                return _sub_topic_from_metadata(meta, source_chunk_id=chunk)

    if source_chunk_id:
        stmt = select(SchoolLectureParagraph).where(
            SchoolLectureParagraph.source_metadata_jsonb["chunk_id"].astext
            == source_chunk_id
        )
        result = await session.execute(stmt.limit(1))
        para = result.scalar_one_or_none()
        if para is not None:
            meta = dict(para.source_metadata_jsonb or {})
            return _sub_topic_from_metadata(meta, source_chunk_id=source_chunk_id)

    if lecture_id:
        lecture = await session.get(SchoolLecture, lecture_id)
        if lecture is not None and lecture.topic:
            return str(lecture.topic)[:128]

    if source_chunk_id:
        return source_chunk_id[:128]
    return None

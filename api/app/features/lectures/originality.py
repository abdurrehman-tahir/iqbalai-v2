"""System-wide originality check (T-135, Flow 5 §3.7 #33, ARCH §7.15).

Part of the scoring pipeline (T-134) — embeds the saved version's body, cosine-
compares it against an index of prior lecture versions, and computes
``originality_score = 1 - max_similarity``. Two tenant-scoped entry points:

- ``check_and_index_school_originality`` — compares against the GLOBAL index
  of ALL school-tenant lectures (cross-school by design, per ARCH §7.15's
  "single cross-tenant search path" exception) and raises a Platform-Admin
  flag above the locked 0.85 similarity threshold.
- ``check_and_index_independent_originality`` — compares only against the
  same teacher's own prior lecture versions (tenant-isolated per §3.16; no
  flag — ``lecture_plagiarism_flags`` is a school-schema-only table).

Both exclude the current lecture's own prior versions from counting as a
match against itself (editing a draft isn't "unoriginal") before indexing
this version's own vector for future checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from app.infrastructure.rag.embedder import (
    embed,
    independent_personal_collection,
    lecture_originality_index_collection,
)
from app.infrastructure.rag.retriever import search_by_vector, upsert_point

SIMILARITY_FLAG_THRESHOLD = 0.85
_MAX_EMBED_CHARS = 6000
_TOP_K = 10


@dataclass(frozen=True)
class OriginalityResult:
    originality_score: Decimal
    max_similarity: float
    is_flagged: bool
    matched_version_id: str | None


def _compute_originality_score(max_similarity: float) -> Decimal:
    clipped = max(0.0, min(1.0, 1.0 - max_similarity))
    return Decimal(str(round(clipped, 3)))


async def _embed_one(body: str) -> list[float]:
    text = body[:_MAX_EMBED_CHARS] or "(empty)"
    vectors = await embed([text])
    return vectors[0]


async def check_and_index_school_originality(
    *, school_id: str, teacher_id: str, lecture_id: str, version_id: str, body: str
) -> OriginalityResult:
    vector = await _embed_one(body)
    collection = lecture_originality_index_collection()

    # No tenant_filter here — the whole point is a GLOBAL, cross-school
    # comparison (ARCH §7.15). Excluding this lecture's own prior versions
    # (same lecture_id) is the only filter: they aren't "unoriginal," they're
    # the same content being edited.
    matches = await search_by_vector(
        collection, vector, exclude={"lecture_id": lecture_id}, top_k=_TOP_K
    )
    # Qdrant returns cosine-similarity results sorted descending, so the top
    # hit is the max similarity match.
    max_similarity = cast(float, matches[0]["score"]) if matches else 0.0
    is_flagged = max_similarity > SIMILARITY_FLAG_THRESHOLD

    await upsert_point(
        collection,
        version_id,
        vector,
        payload={
            "school_id": school_id,
            "teacher_id": teacher_id,
            "lecture_id": lecture_id,
            "version_id": version_id,
        },
    )

    return OriginalityResult(
        originality_score=_compute_originality_score(max_similarity),
        max_similarity=max_similarity,
        is_flagged=is_flagged,
        matched_version_id=str(matches[0]["id"]) if is_flagged and matches else None,
    )


async def check_and_index_independent_originality(
    *, teacher_id: str, lecture_id: str, version_id: str, body: str
) -> OriginalityResult:
    vector = await _embed_one(body)
    # Reuses the teacher's own personal-content Qdrant namespace (already
    # per-user, per ARCH §3.16 tenant isolation) rather than a new collection —
    # ``content_type="lecture_version"`` keeps lecture vectors logically
    # separate from the teacher's uploaded reference PDFs in the same
    # collection, per embedder.py's ``lecture_originality_index_collection``
    # docstring pointer.
    collection = independent_personal_collection(teacher_id)
    matches = await search_by_vector(
        collection,
        vector,
        tenant_filter={"content_type": "lecture_version"},
        exclude={"lecture_id": lecture_id},
        top_k=_TOP_K,
    )
    max_similarity = cast(float, matches[0]["score"]) if matches else 0.0

    await upsert_point(
        collection,
        version_id,
        vector,
        payload={
            "user_id": teacher_id,
            "lecture_id": lecture_id,
            "version_id": version_id,
            "content_type": "lecture_version",
        },
    )

    return OriginalityResult(
        originality_score=_compute_originality_score(max_similarity),
        max_similarity=max_similarity,
        # No plagiarism-flag concept for independent teachers — tenant-isolated
        # comparison against their own prior work only, never cross-teacher.
        is_flagged=False,
        matched_version_id=None,
    )

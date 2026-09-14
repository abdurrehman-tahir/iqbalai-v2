"""Topic relevance percentage (T-136, Flow 5 §3.8 #34, ARCH §7.3).

Part of the scoring pipeline (T-134) — embeds the saved version's body and
the curriculum topic it was generated against (``lecture.topic``, populated
from the teacher's flattened topic-tree selection at generation time — see
``WizardTopicOption``/``LectureGenerateRequest``; no separate topic-tree node
FK is persisted on the lecture, so the topic string itself is the durable
"topic definition" reference), then computes
``relevance_pct = cosine_similarity(topic, body) * 100``.

Same tenant-agnostic core for both schemas — unlike originality (T-135),
there's no cross-tenant index involved, just two embeddings and a dot
product, so one function serves both ``score_school_lecture_version`` and
``score_independent_lecture_version``.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.infrastructure.rag.embedder import embed

LOW_RELEVANCE_WARNING_THRESHOLD = 70.0
_MAX_EMBED_CHARS = 6000


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def compute_topic_relevance(*, topic: str, body: str) -> Decimal:
    """Returns a percentage in [0, 100], rounded to 2 decimals (matches the
    ``Numeric(5, 2)`` ``topic_relevance_pct`` column)."""
    topic_text = topic[:_MAX_EMBED_CHARS] or "(untitled topic)"
    body_text = body[:_MAX_EMBED_CHARS] or "(empty)"

    vectors = await embed([topic_text, body_text])
    topic_vector, body_vector = vectors[0], vectors[1]

    similarity = _cosine_similarity(topic_vector, body_vector)
    # Cosine similarity is mathematically in [-1, 1]; clip defensively before
    # scaling to a percentage — embedding models rarely return negatives for
    # related text, but a clean [0, 100] bound matters more than raw fidelity
    # to a slightly-negative outlier.
    clipped = max(0.0, min(1.0, similarity))
    return Decimal(str(round(clipped * 100, 2)))

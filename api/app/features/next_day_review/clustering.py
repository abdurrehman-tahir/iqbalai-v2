"""Cosine clustering within review question buckets — T-197 (Flow 7 §3.1).

Clusters questions whose dense embeddings have cosine similarity ≥ ``THRESHOLD``
(locked 0.80). Uses BGE-M3 dense vectors via ``infrastructure/rag/embedder``
(ARCH §7.3) — no other embedder.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.infrastructure.rag.embedder import embed

logger = structlog.get_logger(__name__)

COSINE_THRESHOLD = 0.80


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; zero vectors → 0.0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class QuestionCluster:
    """One cosine cluster inside a bucket."""

    cluster_ref: str
    bucket_key: str
    items: list[dict[str, Any]] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)

    @property
    def unique_student_count(self) -> int:
        return len({str(item.get("user_id", "")) for item in self.items if item.get("user_id")})

    @property
    def question_texts(self) -> list[str]:
        texts: list[str] = []
        for item in self.items:
            raw = item.get("question_text")
            if isinstance(raw, str) and raw.strip():
                texts.append(raw.strip())
        return texts


def _max_similarity_to_cluster(vector: list[float], cluster: QuestionCluster) -> float:
    if not cluster.embeddings:
        return 0.0
    return max(cosine_similarity(vector, emb) for emb in cluster.embeddings)


def cluster_embedded_items(
    *,
    bucket_key: str,
    items: list[dict[str, Any]],
    vectors: list[list[float]],
    threshold: float = COSINE_THRESHOLD,
) -> list[QuestionCluster]:
    """Greedy single-pass clustering: assign to first cluster with max cosine ≥ threshold."""
    if len(items) != len(vectors):
        raise ValueError("items and vectors length mismatch")
    clusters: list[QuestionCluster] = []
    for item, vector in zip(items, vectors, strict=True):
        assigned: QuestionCluster | None = None
        for cluster in clusters:
            if _max_similarity_to_cluster(vector, cluster) >= threshold:
                assigned = cluster
                break
        if assigned is None:
            assigned = QuestionCluster(
                cluster_ref=f"{bucket_key}#c{len(clusters)}",
                bucket_key=bucket_key,
            )
            clusters.append(assigned)
        assigned.items.append(item)
        assigned.embeddings.append(vector)
    return clusters


async def cluster_bucket(
    bucket_key: str,
    items: list[dict[str, Any]],
    *,
    threshold: float = COSINE_THRESHOLD,
) -> list[QuestionCluster]:
    """Embed question texts and cluster at ``threshold`` cosine."""
    if not items:
        return []
    texts = [
        str(item.get("question_text") or item.get("question_id") or "question") for item in items
    ]
    vectors = await embed(texts)
    return cluster_embedded_items(
        bucket_key=bucket_key, items=items, vectors=vectors, threshold=threshold
    )


async def cluster_all_buckets(
    buckets: dict[str, list[dict[str, Any]]],
    *,
    threshold: float = COSINE_THRESHOLD,
) -> list[QuestionCluster]:
    """Cluster every bucket; returns a flat list of clusters."""
    all_clusters: list[QuestionCluster] = []
    for bucket_key, items in buckets.items():
        clusters = await cluster_bucket(bucket_key, items, threshold=threshold)
        all_clusters.extend(clusters)
        logger.info(
            "review_bucket_clustered",
            bucket_key=bucket_key,
            question_count=len(items),
            cluster_count=len(clusters),
        )
    return all_clusters

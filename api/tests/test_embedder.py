"""Tests for embedding provider routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.infrastructure.rag.embedder import (
    embed_sync,
    embedding_model_name,
    embedding_vector_dim,
    platform_chunks_collection,
)


def test_local_provider_uses_separate_collection() -> None:
    with patch("app.infrastructure.rag.embedder.get_settings") as mock_settings:
        mock_settings.return_value.EMBEDDING_PROVIDER = "local"
        mock_settings.return_value.EMBEDDING_MODEL = ""
        mock_settings.return_value.EMBEDDING_VECTOR_DIM = 0
        assert platform_chunks_collection() == "platform_chunks_local"
        assert embedding_vector_dim() == 384
        assert (
            embedding_model_name() == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )


def test_infinity_provider_defaults() -> None:
    with patch("app.infrastructure.rag.embedder.get_settings") as mock_settings:
        mock_settings.return_value.EMBEDDING_PROVIDER = "infinity"
        mock_settings.return_value.EMBEDDING_MODEL = ""
        mock_settings.return_value.EMBEDDING_VECTOR_DIM = 0
        assert platform_chunks_collection() == "platform_chunks"
        assert embedding_vector_dim() == 1024
        assert embedding_model_name() == "BAAI/bge-m3"


def test_embed_sync_local_path() -> None:
    fake_model = MagicMock()
    fake_model.embed.return_value = iter([[0.1, 0.2]])

    with (
        patch("app.infrastructure.rag.embedder.get_settings") as mock_settings,
        patch("app.infrastructure.rag.embedder._get_local_model", return_value=fake_model),
    ):
        mock_settings.return_value.EMBEDDING_PROVIDER = "local"
        mock_settings.return_value.EMBEDDING_MODEL = ""
        mock_settings.return_value.EMBEDDING_VECTOR_DIM = 0

        result = embed_sync(["hello"])

    assert result == [[0.1, 0.2]]
    fake_model.embed.assert_called_once_with(["hello"])

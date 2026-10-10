"""Tests for process-level singleton embedding model in worker and embedder."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.embedder import LocalEmbedder, _process_model_cache, get_embedding_model
from app.worker.tasks import WorkerSettings, worker_startup


def test_embedding_model_process_singleton():
    """Verify that get_embedding_model caches and reuses the exact same model instance."""
    mock_st_instance = MagicMock()

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_st_instance
    ) as mock_st_cls:
        # Clear cache for isolated test
        _process_model_cache.clear()

        model1 = get_embedding_model("test-model")
        model2 = get_embedding_model("test-model")

        assert model1 is model2
        # SentenceTransformer should have been instantiated exactly once
        assert mock_st_cls.call_count == 1

        embedder1 = LocalEmbedder(model_name="test-model")
        embedder2 = LocalEmbedder(model_name="test-model")

        assert embedder1._get_model() is embedder2._get_model()
        assert embedder1._get_model() is model1
        assert mock_st_cls.call_count == 1


@pytest.mark.asyncio
async def test_worker_startup_preloads_singleton():
    """Verify that worker_startup preloads the embedding model singleton."""
    mock_st_instance = MagicMock()

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_st_instance
    ) as mock_st_cls:
        _process_model_cache.clear()

        ctx = {}
        await worker_startup(ctx)

        assert mock_st_cls.call_count == 1
        assert WorkerSettings.on_startup is worker_startup

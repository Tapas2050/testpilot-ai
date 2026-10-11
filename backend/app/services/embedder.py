"""Local embedding generator using sentence-transformers."""

from typing import Any, List, Optional

from app.core.config import get_settings

_process_model_cache: dict[str, Any] = {}


def get_embedding_model(model_name: Optional[str] = None) -> Any:
    """Process-level singleton loader for SentenceTransformer to avoid loading weights per job."""
    name = model_name or get_settings().EMBEDDING_MODEL
    if name not in _process_model_cache:
        from sentence_transformers import SentenceTransformer

        try:
            _process_model_cache[name] = SentenceTransformer(
                name, device="cpu", local_files_only=True
            )
        except Exception:
            _process_model_cache[name] = SentenceTransformer(name, device="cpu")
    return _process_model_cache[name]


class LocalEmbedder:
    """Embedder using local sentence-transformers model (all-MiniLM-L6-v2, 384 dims)."""

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name

    def _get_model(self):
        """Lazy loader returning the process-level singleton SentenceTransformer."""
        return get_embedding_model(self._model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a list of text strings."""
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [vec.tolist() for vec in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Compute embedding for a single query string."""
        return self.embed_texts([query])[0]


embedder = LocalEmbedder()

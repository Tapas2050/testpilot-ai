"""Local embedding generator using sentence-transformers."""

from typing import List, Optional

from app.core.config import get_settings


class LocalEmbedder:
    """Embedder using local sentence-transformers model (all-MiniLM-L6-v2, 384 dims)."""

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        """Lazy loader for the SentenceTransformer model to obey memory constraints."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            model_name = self._model_name or get_settings().EMBEDDING_MODEL
            self._model = SentenceTransformer(model_name, device="cpu")
        return self._model

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

"""RAG service for document chunk indexing, pgvector retrieval and Redis caching."""

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.services.chunker import chunk_text
from app.services.embedder import LocalEmbedder, embedder

logger = logging.getLogger(__name__)


class RAGService:
    """Service handling text chunking, embedding, vector search and Redis cache."""

    def __init__(self, embedding_provider: Optional[LocalEmbedder] = None):
        self.embedder = embedding_provider or embedder

    def _cache_key(self, project_id: uuid.UUID, query: str) -> str:
        query_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
        return f"rag:{project_id}:{query_hash}"

    async def invalidate_cache(self, project_id: uuid.UUID) -> None:
        """Invalidate all cached retrieval queries for a specific project."""
        try:
            redis = get_redis_client()
            cursor = 0
            pattern = f"rag:{project_id}:*"
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Failed to invalidate Redis RAG cache for project {project_id}: {e}")

    async def index_document(
        self, db: AsyncSession, document: Document
    ) -> List[DocumentChunk]:
        """Split document text into chunks, generate embeddings, and persist in pgvector."""
        if not document.extracted_text or not document.extracted_text.strip():
            return []

        chunks_text = chunk_text(document.extracted_text)
        if not chunks_text:
            return []

        embeddings = self.embedder.embed_texts(chunks_text)
        created_chunks = []

        for idx, (text_content, emb_vector) in enumerate(zip(chunks_text, embeddings)):
            chunk = DocumentChunk(
                document_id=document.id,
                project_id=document.project_id,
                chunk_index=idx,
                content=text_content,
                embedding=emb_vector,
            )
            db.add(chunk)
            created_chunks.append(chunk)

        await db.commit()
        # Invalidate project cache upon new indexed document
        await self.invalidate_cache(document.project_id)
        return created_chunks

    async def retrieve(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks for a project using pgvector cosine distance.

        Results are cached in Redis with a 1-hour TTL.
        """
        if not query or not query.strip():
            return []

        cache_key = self._cache_key(project_id, query)
        redis = None
        try:
            redis = get_redis_client()
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache lookup failed: {e}")

        # Compute query vector
        query_vec = self.embedder.embed_query(query)

        # Query using pgvector cosine distance: embedding <=> query_vec
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.project_id,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
                DocumentChunk.embedding.cosine_distance(query_vec).label("distance"),
            )
            .where(DocumentChunk.project_id == project_id)
            .order_by("distance")
            .limit(top_k)
        )

        result = await db.execute(stmt)
        rows = result.all()

        results = [
            {
                "id": str(row.id),
                "document_id": str(row.document_id),
                "project_id": str(row.project_id),
                "chunk_index": row.chunk_index,
                "content": row.content,
                "distance": float(row.distance),
            }
            for row in rows
        ]

        if redis is not None and results:
            try:
                await redis.set(cache_key, json.dumps(results), ex=3600)
            except Exception as e:
                logger.warning(f"Failed to store RAG result in Redis: {e}")

        return results


rag_service = RAGService()

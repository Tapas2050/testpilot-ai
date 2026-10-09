# Plan: Phase 6 - RAG Pipeline

## 1. Goal
Implement RAG (Retrieval Augmented Generation) pipeline: chunking extracted document text, embedding with local `sentence-transformers/all-MiniLM-L6-v2` (384 dims), storing vectors in Postgres via pgvector, project-scoped semantic search, and Redis retrieval caching with automatic invalidation.

## 2. Requirements & Constraints
- Model: `DocumentChunk` with `id`, `document_id`, `project_id`, `chunk_index`, `content`, `embedding` (Vector(384)).
- Alembic migration: creates `document_chunks` table and index on `project_id`.
- Chunking: `chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]`. Splits along paragraph / section boundaries where possible.
- Embedder: `backend/app/services/embedder.py` lazy singleton `LocalEmbedder` returning list of 384-dim floats using `all-MiniLM-L6-v2`.
- Indexing & Invalidation:
  - When `DocumentService.upload_document` completes with `SUCCESS`, chunk and embed the text, save chunks to `document_chunks`, and invalidate project cache in Redis (`rag:{project_id}:*`).
  - When document deleted, DB cascade deletes chunks, and Redis cache is invalidated.
- Retrieval:
  - `rag_service.retrieve(project_id: uuid.UUID, query: str, top_k: int = 5) -> List[ChunkResult]`
  - Scoped to `project_id`. Uses pgvector cosine distance (`DocumentChunk.embedding.cosine_distance(query_vector)`).
  - Caches retrieval result in Redis with TTL.
- Tests (TEST_PLAN.md):
  - T6.1 Chunks created and embedded with dimension 384.
  - T6.2 Query about ticket deletion retrieves the admin-only delete requirement.
  - T6.3 Retrieval never returns another project's chunks (project-scoped).
  - T6.4 Redis cache returns cached result and invalidates on upload/delete.

## 3. Files to Create / Modify
- `backend/app/models/chunk.py` (New DocumentChunk model)
- `backend/app/models/__init__.py` (Export DocumentChunk)
- `backend/app/models/project.py`, `backend/app/models/document.py` (Relationships)
- Alembic migration `create document_chunks table`
- `backend/app/services/embedder.py` (Embedder interface & LocalEmbedder)
- `backend/app/services/chunker.py` (Chunking function)
- `backend/app/services/rag_service.py` (RAG service with pgvector search & Redis caching)
- `backend/app/services/document_service.py` (Trigger indexing on upload, invalidation on delete)
- `backend/tests/test_rag.py` (T6.1 through T6.4)

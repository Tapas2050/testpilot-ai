"""Tests for RAG pipeline: chunking, embedding, pgvector retrieval, and Redis cache (Phase 6)."""

import uuid
from typing import Tuple

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.redis import get_redis_client
from app.main import app
from app.models.chunk import DocumentChunk
from app.services.rag_service import rag_service


@pytest.fixture
async def user_and_project(client: AsyncClient) -> Tuple[dict, dict]:
    """Helper fixture creating a registered user and an initial project."""
    email = f"raguser_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "ValidPassword123!"

    reg_resp = await client.post("/auth/register", json={"email": email, "password": pwd})
    assert reg_resp.status_code == 201

    login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj_resp = await client.post(
        "/projects",
        json={
            "name": "RAG Test Project",
            "description": "Project for RAG semantic search tests",
            "target_url": "http://localhost:8001",
        },
        headers=headers,
    )
    assert proj_resp.status_code == 201
    return {"headers": headers, "email": email}, proj_resp.json()


@pytest.mark.asyncio
async def test_t6_1_chunks_created_and_embedded_dimension(
    db_session, user_and_project: Tuple[dict, dict]
) -> None:
    """T6.1: Chunks created and embedded with the right dimension (384)."""
    user, project = user_and_project
    headers = user["headers"]
    project_id = project["id"]

    sample_doc = (
        "# SupportDesk Specification\n\n"
        "## Authentication\n"
        "Users can log in with email and password.\n\n"
        "## Ticket Management\n"
        "Support agents can create tickets, update status, and search tickets.\n\n"
        "## Security and Permissions\n"
        "Ticket deletion is strictly restricted to users with the admin role. "
        "Agents and normal users must never be allowed to delete tickets."
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.md", sample_doc.encode("utf-8"), "text/markdown")},
            headers=headers,
        )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = uuid.UUID(doc_data["id"])

        # Check document_chunks table
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        result = await db_session.execute(stmt)
        chunks = result.scalars().all()

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.project_id == uuid.UUID(project_id)
            assert len(chunk.embedding) == 384
            assert isinstance(chunk.content, str)
            assert len(chunk.content) > 0


@pytest.mark.asyncio
async def test_t6_2_retrieval_finds_admin_delete_requirement(
    db_session, user_and_project: Tuple[dict, dict]
) -> None:
    """T6.2: Query about ticket deletion retrieves the admin-only delete requirement."""
    user, project = user_and_project
    headers = user["headers"]
    project_id = project["id"]

    doc_content = (
        "Role Permissions:\n"
        "Standard user: can view open tickets and submit new tickets.\n"
        "Support agent: can assign tickets and modify status to in-progress or closed.\n"
        "Admin role: only administrators have permission to "
        "permanently delete tickets from the database."
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("roles.txt", doc_content.encode("utf-8"), "text/plain")},
            headers=headers,
        )
        assert upload_resp.status_code == 201

        # Query semantic search via rag_service
        query = "Who is allowed to delete tickets?"
        results = await rag_service.retrieve(db_session, uuid.UUID(project_id), query, top_k=3)

        assert len(results) >= 1
        top_match = results[0]["content"]
        assert "delete tickets" in top_match.lower()
        assert "admin" in top_match.lower()


@pytest.mark.asyncio
async def test_t6_3_project_scoped_isolation(
    client: AsyncClient,
    db_session,
    user_and_project: Tuple[dict, dict],
) -> None:
    """T6.3: Retrieval never returns another project's chunks."""
    user1, project1 = user_and_project
    headers1 = user1["headers"]
    project_id1 = project1["id"]

    # Create project 2 for user 1
    proj2_resp = await client.post(
        "/projects",
        json={
            "name": "Project Two",
            "target_url": "http://localhost:8002",
        },
        headers=headers1,
    )
    assert proj2_resp.status_code == 201
    project_id2 = proj2_resp.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        # Upload secret content into project 1 only
        secret_text = "SECRET_PROJ_1: Nuclear launch codes and admin delete authorization."
        await async_client.post(
            f"/projects/{project_id1}/documents",
            files={"file": ("secret.txt", secret_text.encode("utf-8"), "text/plain")},
            headers=headers1,
        )

        # Upload generic content into project 2
        generic_text = "Project 2 documentation: Billing and invoice export."
        await async_client.post(
            f"/projects/{project_id2}/documents",
            files={"file": ("generic.txt", generic_text.encode("utf-8"), "text/plain")},
            headers=headers1,
        )

        # Search for project 1's secret inside project 2
        results_proj2 = await rag_service.retrieve(
            db_session, uuid.UUID(project_id2), "Nuclear launch codes", top_k=5
        )

        # Must not contain anything from project 1
        for res in results_proj2:
            assert res["project_id"] == project_id2
            assert "SECRET_PROJ_1" not in res["content"]


@pytest.mark.asyncio
async def test_t6_4_redis_cache_and_invalidation(
    db_session, user_and_project: Tuple[dict, dict]
) -> None:
    """T6.4: Cache returns the same result and invalidates after document delete."""
    user, project = user_and_project
    headers = user["headers"]
    project_id = project["id"]
    p_uuid = uuid.UUID(project_id)

    doc_text = "Cache verification: Document content for caching test."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("cached.txt", doc_text.encode("utf-8"), "text/plain")},
            headers=headers,
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        query = "Document content for caching"

        # 1. First retrieval -> hits DB and populates cache
        res1 = await rag_service.retrieve(db_session, p_uuid, query)
        assert len(res1) >= 1

        # Check key in Redis
        redis = get_redis_client()
        cache_key = rag_service._cache_key(p_uuid, query)
        cached_val = await redis.get(cache_key)
        assert cached_val is not None

        # 2. Second retrieval -> identical results from cache
        res2 = await rag_service.retrieve(db_session, p_uuid, query)
        assert res1 == res2

        # 3. Delete document -> invalidates cache
        del_resp = await client.delete(f"/documents/{doc_id}", headers=headers)
        assert del_resp.status_code == 204

        # Key should now be evicted from Redis
        cached_after_del = await redis.get(cache_key)
        assert cached_after_del is None

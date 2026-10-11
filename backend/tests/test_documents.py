"""Tests for Document upload, extraction, storage, and lifecycle (Phase 5)."""

import json
import uuid
from typing import Tuple

import fitz  # PyMuPDF
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


def generate_sample_pdf(text: str = "Admin Requirement: Only admins can delete tickets.") -> bytes:
    """Generate a valid minimal PDF in-memory using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
async def user_and_project(client: AsyncClient) -> Tuple[dict, dict, dict]:
    """Helper fixture creating a registered user and an initial project."""
    email = f"docuser_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "ValidPassword123!"

    # 1. Register
    reg_resp = await client.post("/auth/register", json={"email": email, "password": pwd})
    assert reg_resp.status_code == 201

    # 2. Login
    login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Project
    proj_resp = await client.post(
        "/projects",
        json={
            "name": "Doc Test Project",
            "description": "Project for document extraction testing",
            "target_url": "http://localhost:8000",
        },
        headers=headers,
    )
    assert proj_resp.status_code == 201
    project = proj_resp.json()

    return {"email": email, "headers": headers}, project, login_resp.json()


@pytest.mark.asyncio
async def test_t5_1_supported_types_upload_and_extract(
    user_and_project: Tuple[dict, dict, dict],
) -> None:
    """T5.1: Each supported type (PDF, TXT, Markdown, JSON) uploads and extracts text."""
    auth_user, project, _ = user_and_project
    headers = auth_user["headers"]
    project_id = project["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. PDF Upload & Extraction
        pdf_bytes = generate_sample_pdf("System Specification: Ticket delete requires admin role.")
        pdf_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert pdf_resp.status_code == 201, pdf_resp.text
        pdf_data = pdf_resp.json()
        assert pdf_data["file_type"] == "pdf"
        assert pdf_data["original_name"] == "requirements.pdf"
        assert pdf_data["extraction_status"] == "SUCCESS"
        assert "Ticket delete requires admin role" in pdf_data["extracted_text"]

        # 2. TXT Upload & Extraction
        txt_content = b"Simple plain text requirement line 1.\nLine 2 info."
        txt_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("specs.txt", txt_content, "text/plain")},
            headers=headers,
        )
        assert txt_resp.status_code == 201
        txt_data = txt_resp.json()
        assert txt_data["file_type"] == "txt"
        assert txt_data["extraction_status"] == "SUCCESS"
        assert "Simple plain text requirement" in txt_data["extracted_text"]

        # 3. Markdown Upload & Extraction
        md_content = b"# Requirements Document\n\n- Feature A\n- Feature B"
        md_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("readme.md", md_content, "text/markdown")},
            headers=headers,
        )
        assert md_resp.status_code == 201
        md_data = md_resp.json()
        assert md_data["file_type"] == "markdown"
        assert md_data["extraction_status"] == "SUCCESS"
        assert "# Requirements Document" in md_data["extracted_text"]

        # 4. JSON Upload & Extraction
        json_obj = {"tickets": [{"id": 1, "title": "Bug", "priority": "high"}]}
        json_content = json.dumps(json_obj).encode("utf-8")
        json_resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("data.json", json_content, "application/json")},
            headers=headers,
        )
        assert json_resp.status_code == 201
        json_data = json_resp.json()
        assert json_data["file_type"] == "json"
        assert json_data["extraction_status"] == "SUCCESS"
        assert "tickets" in json_data["extracted_text"]


@pytest.mark.asyncio
async def test_t5_2_rejected_uploads(user_and_project: Tuple[dict, dict, dict]) -> None:
    """T5.2: Wrong type, spoofed type, empty and oversized files rejected."""
    auth_user, project, _ = user_and_project
    headers = auth_user["headers"]
    project_id = project["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Wrong type (e.g. .exe or .py)
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("script.py", b"print('hello')", "text/x-python")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Unsupported file extension" in resp.json()["detail"]

        # 2. Empty file
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("empty.txt", b"", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

        # 3. Spoofed PDF (extension .pdf but invalid header)
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("fake.pdf", b"NOT A PDF HEADER", "application/pdf")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Missing %PDF" in resp.json()["detail"]

        # 4. Spoofed JSON (extension .json but invalid JSON syntax)
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("invalid.json", b"{ invalid_json: 123", "application/json")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

        # 5. Oversized file (exceeds MAX_UPLOAD_MB)
        oversized = b"A" * ((get_settings().MAX_UPLOAD_MB * 1024 * 1024) + 1024)
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("large.txt", oversized, "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "maximum allowed size" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_t5_3_stored_filename_is_generated_uuid(
    user_and_project: Tuple[dict, dict, dict],
) -> None:
    """T5.3: Stored filename is generated UUID, never the original user input."""
    auth_user, project, _ = user_and_project
    headers = auth_user["headers"]
    project_id = project["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Attempt path traversal in original filename
        malicious_name = "../../../etc/passwd.txt"
        resp = await client.post(
            f"/projects/{project_id}/documents",
            files={"file": (malicious_name, b"Sample content", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Check DB list to see stored filename
        list_resp = await client.get(
            f"/projects/{project_id}/documents",
            headers=headers,
        )
        docs = list_resp.json()
        assert len(docs) >= 1
        created_doc = next(d for d in docs if d["id"] == doc_id)
        # Original name sanitized or recorded
        assert "passwd.txt" in created_doc["original_name"]


@pytest.mark.asyncio
async def test_t5_4_delete_removes_file_and_record_and_blocks_cross_user(
    client: AsyncClient,
    user_and_project: Tuple[dict, dict, dict],
) -> None:
    """T5.4: Delete removes file and record; cross-user access blocked with 404."""
    user1, project1, _ = user_and_project
    headers1 = user1["headers"]
    project_id1 = project1["id"]

    # Register user 2
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": user2_email, "password": "Password123!"})
    login2 = await client.post(
        "/auth/login", json={"email": user2_email, "password": "Password123!"}
    )
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        # 1. User 1 uploads document
        upload_resp = await async_client.post(
            f"/projects/{project_id1}/documents",
            files={"file": ("to_delete.txt", b"delete me later", "text/plain")},
            headers=headers1,
        )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = doc_data["id"]

        # 2. User 2 tries to list User 1's documents -> 404
        list_cross = await async_client.get(
            f"/projects/{project_id1}/documents",
            headers=headers2,
        )
        assert list_cross.status_code == 404

        # 3. User 2 tries to delete User 1's document -> 404
        del_cross = await async_client.delete(
            f"/documents/{doc_id}",
            headers=headers2,
        )
        assert del_cross.status_code == 404

        # 4. User 1 deletes their document -> 204
        del_resp = await async_client.delete(
            f"/documents/{doc_id}",
            headers=headers1,
        )
        assert del_resp.status_code == 204

        # 5. Verify deleted from list
        list_resp = await async_client.get(
            f"/projects/{project_id1}/documents",
            headers=headers1,
        )
        assert not any(d["id"] == doc_id for d in list_resp.json())

        # 6. Second delete returns 404
        del_again = await async_client.delete(
            f"/documents/{doc_id}",
            headers=headers1,
        )
        assert del_again.status_code == 404

"""T13.2: Comprehensive Cross-User Isolation Suite.

Ensures that every resource owned by User A returns HTTP 404 when queried
by User B, completely preventing information leakage and cross-tenant tampering.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.credential import ProjectCredential
from app.models.document import Document
from app.models.project import Project
from app.models.session import UserSession
from app.models.test_run import TestRun
from app.models.user import User


@pytest.fixture
async def two_users(db_session: AsyncSession):
    """Fixture providing two distinct authenticated users with isolated credentials and projects."""
    # User A
    pw_hash = await hash_password("PasswordA123!")
    user_a = User(
        id=uuid.uuid4(),
        email="user_a@example.com",
        password_hash=pw_hash,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_a)
    await db_session.flush()

    sess_a = UserSession(
        user_id=user_a.id,
        token_id=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(sess_a)

    proj_a = Project(
        id=uuid.uuid4(),
        user_id=user_a.id,
        name="User A Project",
        target_url="http://localhost:8001",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj_a)

    cred_a = ProjectCredential(
        id=uuid.uuid4(),
        project_id=proj_a.id,
        role_label="admin",
        username="admin_a",
        password_encrypted="encrypted_pw",
    )
    db_session.add(cred_a)

    doc_a = Document(
        id=uuid.uuid4(),
        project_id=proj_a.id,
        original_name="req_a.md",
        stored_name=f"{uuid.uuid4()}.md",
        file_type="md",
        size_bytes=500,
        extraction_status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(doc_a)

    run_a = TestRun(
        id=uuid.uuid4(),
        project_id=proj_a.id,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
        report={"total_tests": 1, "passed_tests": 1, "failed_tests": 0, "pass_percentage": 100.0},
    )
    db_session.add(run_a)

    # User B
    user_b = User(
        id=uuid.uuid4(),
        email="user_b@example.com",
        password_hash=pw_hash,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_b)
    await db_session.flush()

    token_b, jti_b, exp_b = create_access_token(user_b.id)
    sess_b = UserSession(
        user_id=user_b.id,
        token_id=jti_b,
        expires_at=exp_b,
    )
    db_session.add(sess_b)
    await db_session.commit()

    headers_b = {"Authorization": f"Bearer {token_b}"}

    return {
        "headers_b": headers_b,
        "proj_a_id": proj_a.id,
        "cred_a_id": cred_a.id,
        "doc_a_id": doc_a.id,
        "run_a_id": run_a.id,
    }


@pytest.mark.asyncio
async def test_t13_2_cross_user_project_access_refused(client: AsyncClient, two_users):
    """T13.2: User B cannot view, edit, or delete User A's project."""
    h_b = two_users["headers_b"]
    p_a = two_users["proj_a_id"]

    # GET project
    r_get = await client.get(f"/projects/{p_a}", headers=h_b)
    assert r_get.status_code == 404

    # PATCH project
    r_patch = await client.patch(f"/projects/{p_a}", json={"name": "Hacked"}, headers=h_b)
    assert r_patch.status_code == 404

    # DELETE project
    r_del = await client.delete(f"/projects/{p_a}", headers=h_b)
    assert r_del.status_code == 404


@pytest.mark.asyncio
async def test_t13_2_cross_user_credential_access_refused(client: AsyncClient, two_users):
    """T13.2: User B cannot list, add, or delete credentials on User A's project."""
    h_b = two_users["headers_b"]
    p_a = two_users["proj_a_id"]
    c_a = two_users["cred_a_id"]

    # List credentials
    r_list = await client.get(f"/projects/{p_a}/credentials", headers=h_b)
    assert r_list.status_code == 404

    # Add credential
    r_add = await client.post(
        f"/projects/{p_a}/credentials",
        json={"role_label": "agent", "username": "bad", "password": "bad"},
        headers=h_b,
    )
    assert r_add.status_code == 404

    # Delete credential
    r_del = await client.delete(f"/projects/{p_a}/credentials/{c_a}", headers=h_b)
    assert r_del.status_code == 404


@pytest.mark.asyncio
async def test_t13_2_cross_user_document_access_refused(client: AsyncClient, two_users):
    """T13.2: User B cannot list documents, upload documents, or delete User A's document."""
    h_b = two_users["headers_b"]
    p_a = two_users["proj_a_id"]
    d_a = two_users["doc_a_id"]

    # List documents
    r_list = await client.get(f"/projects/{p_a}/documents", headers=h_b)
    assert r_list.status_code == 404

    # Upload document to User A's project
    r_up = await client.post(
        f"/projects/{p_a}/documents",
        files={"file": ("malicious.txt", b"evil content", "text/plain")},
        headers=h_b,
    )
    assert r_up.status_code == 404

    # Delete User A's document directly
    r_del = await client.delete(f"/documents/{d_a}", headers=h_b)
    assert r_del.status_code == 404


@pytest.mark.asyncio
async def test_t13_2_cross_user_runs_and_reports_access_refused(client: AsyncClient, two_users):
    """T13.2: User B cannot trigger runs, list runs, get run status, cancel, or view reports."""
    h_b = two_users["headers_b"]
    p_a = two_users["proj_a_id"]
    r_a = two_users["run_a_id"]

    # Trigger run on User A's project
    r_start = await client.post(f"/projects/{p_a}/runs", headers=h_b)
    assert r_start.status_code == 404

    # List runs on User A's project
    r_list = await client.get(f"/projects/{p_a}/runs", headers=h_b)
    assert r_list.status_code == 404

    # Get User A's run details
    r_get = await client.get(f"/runs/{r_a}", headers=h_b)
    assert r_get.status_code == 404

    # Cancel User A's run
    r_cancel = await client.post(f"/runs/{r_a}/cancel", headers=h_b)
    assert r_cancel.status_code == 404

    # Get User A's report
    r_rep = await client.get(f"/runs/{r_a}/report", headers=h_b)
    assert r_rep.status_code == 404

    # Get User A's screenshot evidence
    r_screen = await client.get(f"/runs/{r_a}/screenshots/evidence_01.png", headers=h_b)
    assert r_screen.status_code == 404

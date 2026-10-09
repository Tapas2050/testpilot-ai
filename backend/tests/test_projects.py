"""Tests for Project Management Backend (T3.1, T3.2, T3.3, T3.4)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credential
from app.models.credential import ProjectCredential


async def create_user_and_token(client: AsyncClient, email: str) -> dict[str, str]:
    """Helper creating user and returning Authorization headers."""
    pwd = "SecurePassword123"
    await client.post("/auth/register", json={"email": email, "password": pwd})
    login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_project_crud_for_owner(client: AsyncClient, db_session: AsyncSession):
    """T3.1: CRUD works for project owner."""
    headers = await create_user_and_token(client, "owner@example.com")

    # 1. Create Project
    create_payload = {
        "name": "SupportDesk QA",
        "description": "Internal test project",
        "target_url": "http://localhost:8001",
    }
    create_resp = await client.post("/projects", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    project_data = create_resp.json()
    project_id = project_data["id"]
    assert project_data["name"] == "SupportDesk QA"
    assert project_data["target_url"] == "http://localhost:8001"

    # 2. List Projects
    list_resp = await client.get("/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 1
    assert projects[0]["id"] == project_id

    # 3. Read Single Project
    get_resp = await client.get(f"/projects/{project_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id

    # 4. Update Project
    update_payload = {"name": "SupportDesk Release 1.0", "description": "Updated description"}
    update_resp = await client.patch(
        f"/projects/{project_id}", json=update_payload, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "SupportDesk Release 1.0"
    assert update_resp.json()["description"] == "Updated description"

    # 5. Delete Project
    del_resp = await client.delete(f"/projects/{project_id}", headers=headers)
    assert del_resp.status_code == 204

    # 6. Verify Project Gone
    get_after_del = await client.get(f"/projects/{project_id}", headers=headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_isolation_returns_404(client: AsyncClient):
    """T3.2: Another user gets 404 on read, update, delete, credentials."""
    headers_a = await create_user_and_token(client, "user_a@example.com")
    headers_b = await create_user_and_token(client, "user_b@example.com")

    # User A creates project
    create_resp = await client.post(
        "/projects",
        json={"name": "User A Project", "target_url": "http://localhost:8001"},
        headers=headers_a,
    )
    project_id = create_resp.json()["id"]

    # User A adds a credential
    cred_resp = await client.post(
        f"/projects/{project_id}/credentials",
        json={"role_label": "admin", "username": "admin@local", "password": "AdminPassword123"},
        headers=headers_a,
    )
    cred_id = cred_resp.json()["id"]

    # User B list projects does NOT show User A's project
    list_b = await client.get("/projects", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0

    # User B read -> 404
    assert (await client.get(f"/projects/{project_id}", headers=headers_b)).status_code == 404

    # User B update -> 404
    assert (
        await client.patch(
            f"/projects/{project_id}",
            json={"name": "Hijacked"},
            headers=headers_b,
        )
    ).status_code == 404

    # User B credentials list -> 404
    assert (
        await client.get(f"/projects/{project_id}/credentials", headers=headers_b)
    ).status_code == 404

    # User B add credential -> 404
    assert (
        await client.post(
            f"/projects/{project_id}/credentials",
            json={"role_label": "hacker", "username": "bad", "password": "123"},
            headers=headers_b,
        )
    ).status_code == 404

    # User B delete credential -> 404
    assert (
        await client.delete(f"/projects/{project_id}/credentials/{cred_id}", headers=headers_b)
    ).status_code == 404

    # User B delete project -> 404
    assert (await client.delete(f"/projects/{project_id}", headers=headers_b)).status_code == 404


@pytest.mark.asyncio
async def test_project_creation_rejects_ssrf_urls(client: AsyncClient):
    """T3.3: Creating a project with blocked private or metadata URL returns 422."""
    headers = await create_user_and_token(client, "ssrf_tester@example.com")

    # AWS metadata address
    resp1 = await client.post(
        "/projects",
        json={"name": "Metadata Project", "target_url": "http://169.254.169.254/secret"},
        headers=headers,
    )
    assert resp1.status_code == 422

    # Private IP
    resp2 = await client.post(
        "/projects",
        json={"name": "Internal IP", "target_url": "http://10.0.0.5:8080"},
        headers=headers,
    )
    assert resp2.status_code == 422

    # Invalid scheme
    resp3 = await client.post(
        "/projects",
        json={"name": "File Scheme", "target_url": "file:///etc/passwd"},
        headers=headers,
    )
    assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_credentials_encrypted_in_db_and_never_returned(
    client: AsyncClient, db_session: AsyncSession
):
    """T3.4: Credentials are encrypted at rest and never returned in API responses."""
    headers = await create_user_and_token(client, "cred_tester@example.com")

    # Create project
    proj_resp = await client.post(
        "/projects",
        json={"name": "Cred Project", "target_url": "http://localhost:8001"},
        headers=headers,
    )
    project_id = proj_resp.json()["id"]

    raw_password = "SuperSecretSupportDeskAdminPassword#2026!"
    # Add credential
    cred_create_resp = await client.post(
        f"/projects/{project_id}/credentials",
        json={
            "role_label": "admin",
            "username": "admin@supportdesk.local",
            "password": raw_password,
        },
        headers=headers,
    )
    assert cred_create_resp.status_code == 201
    cred_data = cred_create_resp.json()
    cred_id = cred_data["id"]

    # Verify response body contains NO password fields
    assert "password" not in cred_data
    assert "password_encrypted" not in cred_data
    assert raw_password not in cred_create_resp.text

    # Verify list credentials response contains NO password fields
    cred_list_resp = await client.get(f"/projects/{project_id}/credentials", headers=headers)
    assert cred_list_resp.status_code == 200
    list_data = cred_list_resp.json()
    assert len(list_data) == 1
    assert "password" not in list_data[0]
    assert "password_encrypted" not in list_data[0]
    assert raw_password not in cred_list_resp.text

    # Inspect database row directly
    db_result = await db_session.execute(
        select(ProjectCredential).where(ProjectCredential.id == cred_id)
    )
    db_row = db_result.scalar_one_or_none()
    assert db_row is not None
    assert db_row.password_encrypted != raw_password
    assert raw_password not in db_row.password_encrypted
    # Verify it can be decrypted back to raw password using encryption helper
    assert decrypt_credential(db_row.password_encrypted) == raw_password

    # Delete credential
    del_cred_resp = await client.delete(
        f"/projects/{project_id}/credentials/{cred_id}", headers=headers
    )
    assert del_cred_resp.status_code == 204

    # Verify credential deleted from DB
    deleted_check = await db_session.execute(
        select(ProjectCredential).where(ProjectCredential.id == cred_id)
    )
    assert deleted_check.scalar_one_or_none() is None

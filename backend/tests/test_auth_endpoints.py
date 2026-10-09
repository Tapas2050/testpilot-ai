"""Tests for authentication endpoints (/auth/register, /auth/login, /auth/me, /auth/logout)."""

import logging
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import UserSession
from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    """T2.1: Register a new user returns 201 with UserResponse excluding password."""
    payload = {"email": "newuser@example.com", "password": "SecurePassword123"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "newuser@example.com"
    assert "created_at" in data
    assert "password" not in data
    assert "password_hash" not in data

    # Verify user exists in database
    result = await db_session.execute(select(User).where(User.email == "newuser@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.password_hash != "SecurePassword123"
    assert "$argon2" in user.password_hash


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client: AsyncClient):
    """T2.1: Duplicate registration with the same email returns 400 Bad Request."""
    payload = {"email": "duplicate@example.com", "password": "SecurePassword123"}
    resp1 = await client.post("/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Email is already registered"


@pytest.mark.asyncio
async def test_register_race_condition_integrity_error_handled(client: AsyncClient):
    mock_integrity = IntegrityError("duplicate", None, Exception())
    with patch("app.services.auth_service.AsyncSession.commit", side_effect=mock_integrity):
        payload = {"email": "race@example.com", "password": "SecurePassword123"}
        response = await client.post("/auth/register", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "Email is already registered"


@pytest.mark.asyncio
async def test_password_stored_hashed_never_plaintext(
    client: AsyncClient, db_session: AsyncSession
):
    """T2.2: Password in database is an argon2 hash and never plaintext."""
    pwd = "MySecretPassword!2026"
    response = await client.post(
        "/auth/register", json={"email": "hashedtest@example.com", "password": pwd}
    )
    assert response.status_code == 201

    result = await db_session.execute(select(User).where(User.email == "hashedtest@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert pwd not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_login_success_and_session_created(client: AsyncClient, db_session: AsyncSession):
    """T2.3: Successful login returns 200 with JWT access_token and creates UserSession."""
    await client.post(
        "/auth/register", json={"email": "loginuser@example.com", "password": "Password12345"}
    )

    login_resp = await client.post(
        "/auth/login", json={"email": "loginuser@example.com", "password": "Password12345"}
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify session row exists
    sessions = (await db_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


@pytest.mark.asyncio
async def test_login_invalid_password_returns_generic_message(client: AsyncClient):
    """T2.3: Wrong password returns 401 with generic 'Invalid email or password'."""
    await client.post(
        "/auth/register", json={"email": "wrongpwd@example.com", "password": "Password12345"}
    )

    login_resp = await client.post(
        "/auth/login", json={"email": "wrongpwd@example.com", "password": "WrongPassword999"}
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_generic_message(client: AsyncClient):
    """T2.3: Nonexistent email returns 401 with exact same generic message."""
    login_resp = await client.post(
        "/auth/login", json={"email": "doesnotexist@example.com", "password": "AnyPassword123"}
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_email_case_insensitivity_and_normalization(client: AsyncClient):
    """T2.6: Register with mixed case and login with lowercase works."""
    # Register with mixed case and leading/trailing whitespace
    reg_resp = await client.post(
        "/auth/register", json={"email": "  User@Example.COM  ", "password": "Password12345"}
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["email"] == "user@example.com"

    # Login with all lowercase
    login_resp = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "Password12345"}
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # Login with all UPPERCASE
    login_resp_upper = await client.post(
        "/auth/login", json={"email": "USER@EXAMPLE.COM", "password": "Password12345"}
    )
    assert login_resp_upper.status_code == 200

    # Duplicate registration with different case returns 400
    dup_resp = await client.post(
        "/auth/register", json={"email": "USER@EXAMPLE.com", "password": "Password12345"}
    )
    assert dup_resp.status_code == 400
    assert dup_resp.json()["detail"] == "Email is already registered"


@pytest.mark.asyncio
async def test_password_length_validation_enforced(client: AsyncClient):
    """T2.7: Password length bounds (8 min, 128 max) enforced in Pydantic schema."""
    # Too short: 7 characters
    resp_short = await client.post(
        "/auth/register", json={"email": "short@example.com", "password": "1234567"}
    )
    assert resp_short.status_code == 422

    # Exactly 8 characters: succeeds
    resp_min = await client.post(
        "/auth/register", json={"email": "min8@example.com", "password": "12345678"}
    )
    assert resp_min.status_code == 201

    # Exactly 128 characters: succeeds
    pwd_128 = "A" * 128
    resp_max = await client.post(
        "/auth/register", json={"email": "max128@example.com", "password": pwd_128}
    )
    assert resp_max.status_code == 201

    # Too long: 129 characters
    pwd_129 = "A" * 129
    resp_oversized = await client.post(
        "/auth/register", json={"email": "oversized@example.com", "password": pwd_129}
    )
    assert resp_oversized.status_code == 422


@pytest.mark.asyncio
async def test_get_me_and_logout_revocation(client: AsyncClient):
    """T2.4, T2.5: GET /auth/me returns profile; POST /auth/logout revokes session."""
    await client.post(
        "/auth/register", json={"email": "profile@example.com", "password": "Password12345"}
    )
    login_resp = await client.post(
        "/auth/login", json={"email": "profile@example.com", "password": "Password12345"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me succeeds
    me_resp = await client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "profile@example.com"
    assert "password" not in data
    assert "password_hash" not in data

    # /auth/logout succeeds
    logout_resp = await client.post("/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out successfully"

    # Subsequent call with the same token is rejected
    after_me_resp = await client.get("/auth/me", headers=headers)
    assert after_me_resp.status_code == 401


@pytest.mark.asyncio
async def test_response_bodies_never_contain_password_or_hash(client: AsyncClient):
    """T2.10: No response body across auth endpoints leaks password or password_hash."""
    pwd = "SecretPassword123"
    # Register
    r1 = await client.post(
        "/auth/register", json={"email": "leaktest@example.com", "password": pwd}
    )
    text1 = r1.text.lower()
    assert "password" not in text1
    assert "password_hash" not in text1
    assert "$argon2" not in text1

    # Login
    r2 = await client.post("/auth/login", json={"email": "leaktest@example.com", "password": pwd})
    text2 = r2.text.lower()
    assert pwd.lower() not in text2
    assert "password_hash" not in text2
    assert "$argon2" not in text2

    token = r2.json()["access_token"]
    # Me
    r3 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    text3 = r3.text.lower()
    assert "password" not in text3
    assert "password_hash" not in text3
    assert "$argon2" not in text3

    # Logout
    r4 = await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    text4 = r4.text.lower()
    assert "password" not in text4
    assert "password_hash" not in text4


@pytest.mark.asyncio
async def test_logs_contain_no_passwords_or_tokens(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """T2.10: Application logging never records plaintext passwords or raw JWT tokens."""
    caplog.set_level(logging.DEBUG)
    raw_pwd = "SuperSecretUnloggedPassword123"

    # Register
    await client.post("/auth/register", json={"email": "logclean@example.com", "password": raw_pwd})

    # Login
    login_resp = await client.post(
        "/auth/login", json={"email": "logclean@example.com", "password": raw_pwd}
    )
    token = login_resp.json()["access_token"]

    # Logout
    await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    all_logs = " ".join([record.getMessage() for record in caplog.records])
    assert raw_pwd not in all_logs
    assert token not in all_logs

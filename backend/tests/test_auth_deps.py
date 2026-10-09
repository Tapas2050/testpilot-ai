"""Tests for authentication dependency validation and token security (T2.4, T2.8)."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.session import UserSession
from app.models.user import User


@pytest.mark.asyncio
async def test_deps_missing_token_returns_401(client: AsyncClient):
    """T2.4: Accessing protected endpoint without Authorization header returns 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_malformed_token_returns_401(client: AsyncClient):
    """T2.4: Accessing protected endpoint with malformed token returns 401."""
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_tampered_signature_returns_401(client: AsyncClient, db_session: AsyncSession):
    """T2.8: Accessing protected endpoint with tampered JWT signature returns 401."""
    user = User(email="tamper@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    token, jti, expire = create_access_token(user.id)
    session = UserSession(user_id=user.id, token_id=jti, expires_at=expire)
    db_session.add(session)
    await db_session.commit()

    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tamperedsignature"

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_unknown_jti_returns_401(client: AsyncClient, db_session: AsyncSession):
    """T2.8: Valid JWT signature with jti missing from database sessions returns 401."""
    user = User(email="unknown_jti@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    # Token generated but session never inserted into DB
    token, _, _ = create_access_token(user.id)

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_user_no_longer_exists_returns_401(
    client: AsyncClient, db_session: AsyncSession
):
    """T2.8: Valid session whose corresponding user was deleted returns 401."""
    user = User(email="deleted@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    token, jti, expire = create_access_token(user.id)
    session = UserSession(user_id=user.id, token_id=jti, expires_at=expire)
    db_session.add(session)
    await db_session.commit()

    # Delete the user manually disabling FK cascade temporarily or manually deleting
    # In SQLite or Postgres with CASCADE, deleting user deletes session,
    # so simulate user deletion while session exists (e.g. non-existent user_id in token)
    settings = get_settings()
    ghost_user_id = uuid.uuid4()
    # Create session with ghost_user_id is prevented by FK, so create valid user, create session,
    # then make token with a different user_id but matching session's jti:
    mismatched_token = jwt.encode(
        {
            "sub": str(ghost_user_id),
            "jti": jti,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(expire.timestamp()),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {mismatched_token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_expired_session_row_returns_401(client: AsyncClient, db_session: AsyncSession):
    """T2.8: Token whose session row in DB has expires_at in the past returns 401."""
    user = User(email="past_session@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    # Create a token that is theoretically valid in JWT exp, but DB row says expired
    token, jti, _ = create_access_token(user.id, expires_delta=timedelta(hours=2))
    past_session = UserSession(
        user_id=user.id,
        token_id=jti,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # expired row
    )
    db_session.add(past_session)
    await db_session.commit()

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deps_revoked_session_returns_401(client: AsyncClient, db_session: AsyncSession):
    """T2.4: Token whose session has revoked_at populated returns 401."""
    user = User(email="revoked@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    token, jti, expire = create_access_token(user.id)
    revoked_session = UserSession(
        user_id=user.id,
        token_id=jti,
        expires_at=expire,
        revoked_at=datetime.now(timezone.utc),  # revoked
    )
    db_session.add(revoked_session)
    await db_session.commit()

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

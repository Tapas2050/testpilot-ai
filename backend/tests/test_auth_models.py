"""Tests for User and UserSession models."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import UserSession
from app.models.user import User


@pytest.mark.asyncio
async def test_create_user_and_session(db_session: AsyncSession):
    """Test User and UserSession models can be created and queried."""
    user = User(
        email="test@example.com",
        password_hash="fakehash",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert user.created_at.tzinfo is not None

    session = UserSession(
        user_id=user.id,
        token_id="jti-12345",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.id is not None
    assert session.user_id == user.id
    assert session.token_id == "jti-12345"
    assert session.revoked_at is None
    assert session.expires_at.tzinfo is not None


@pytest.mark.asyncio
async def test_user_session_cascade_deletion(db_session: AsyncSession):
    """Deleting a user should cascade delete its sessions."""
    user = User(
        email="cascade@example.com",
        password_hash="fakehash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = UserSession(
        user_id=user.id,
        token_id="jti-cascade",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )
    db_session.add(session)
    await db_session.commit()

    # Delete user
    await db_session.delete(user)
    await db_session.commit()

    result = await db_session.execute(
        select(UserSession).where(UserSession.token_id == "jti-cascade")
    )
    assert result.scalar_one_or_none() is None

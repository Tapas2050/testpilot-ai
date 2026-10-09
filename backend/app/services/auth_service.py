"""Authentication service handling registration, password verification, and session creation."""

import logging
from datetime import datetime, timezone
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.models.session import UserSession
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    """Service layer for user registration and authentication workflows."""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Register a new user account with argon2 hashed password.

        Catches IntegrityError to safely handle concurrent registration races.
        """
        normalized_email = email.strip().lower()

        # Check existing user
        stmt = select(User).where(User.email == normalized_email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            logger.info("Registration attempt with already registered email")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered",
            )

        hashed = await hash_password(password)
        new_user = User(
            email=normalized_email,
            password_hash=hashed,
            created_at=datetime.now(timezone.utc),
        )

        try:
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            logger.info("Successfully registered user ID %s", new_user.id)
            return new_user
        except IntegrityError:
            await db.rollback()
            logger.warning("IntegrityError on registration race for email")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered",
            )

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Tuple[User, str, UserSession]:
        """Authenticate user by email and password, creating a persisted UserSession.

        Uses generic 401 error message for non-existent users and incorrect passwords.
        Performs dummy hash verification for non-existent users to thwart timing attacks.
        """
        normalized_email = email.strip().lower()

        stmt = select(User).where(User.email == normalized_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Timing attack mitigation: compute argon2 against dummy hash
            await verify_dummy_password(password)
            logger.info("Failed login attempt for nonexistent email")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        is_valid = await verify_password(password, user.password_hash)
        if not is_valid:
            logger.info("Failed login attempt: invalid password for user ID %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Create JWT access token and database UserSession
        token, jti, expire = create_access_token(user.id)
        user_session = UserSession(
            user_id=user.id,
            token_id=jti,
            expires_at=expire,
        )
        db.add(user_session)
        await db.commit()
        await db.refresh(user_session)

        logger.info("Successful login and session creation for user ID %s", user.id)
        return user, token, user_session

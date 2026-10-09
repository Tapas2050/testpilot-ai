"""FastAPI dependency providers for authentication and authorization."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Tuple

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.session import UserSession
from app.models.user import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_and_session(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tuple[User, UserSession]:
    """Validate Bearer token, signature, claims, user persistence, and session revocation.

    Raises 401 if:
    - Token is malformed, tampered, or expired
    - Required claims (sub, jti, exp) are missing
    - Token ID (jti) is not found in database sessions
    - Session has been revoked (revoked_at is set)
    - Session has expired in database (expires_at <= now)
    - User account no longer exists in database
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        logger.info("JWT decode validation failed: %s", exc.__class__.__name__)
        raise credentials_exception

    sub = payload.get("sub")
    jti = payload.get("jti")
    if not sub or not jti:
        raise credentials_exception

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    # Query session record
    stmt_session = select(UserSession).where(UserSession.token_id == jti)
    res_session = await db.execute(stmt_session)
    user_session = res_session.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not user_session:
        logger.info("Session lookup failed: token_id not found")
        raise credentials_exception

    if user_session.revoked_at is not None:
        logger.info("Session lookup failed: session revoked")
        raise credentials_exception

    if user_session.expires_at <= now:
        logger.info("Session lookup failed: session row expired")
        raise credentials_exception

    # Query user record
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()

    if not user:
        logger.info("User lookup failed: user no longer exists")
        raise credentials_exception

    return user, user_session


async def get_current_user(
    user_and_session: Tuple[User, UserSession] = Depends(get_current_user_and_session),
) -> User:
    """Dependency returning the validated current User."""
    return user_and_session[0]

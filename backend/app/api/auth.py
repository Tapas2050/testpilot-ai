"""Authentication endpoints for registration, login, profile, and logout."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_and_session
from app.core.database import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account with validated email and password."""
    return await AuthService.register_user(db, email=data.email, password=data.password)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate credentials and generate a JWT access token with a persisted session."""
    _, token, _ = await AuthService.authenticate_user(db, email=data.email, password=data.password)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Retrieve authenticated user's profile."""
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and revoke current session token",
)
async def logout(
    user_and_session: Tuple[User, UserSession] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Revoke the current active session in the database."""
    _, user_session = user_and_session
    user_session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Session %s successfully revoked", user_session.token_id)
    return {"message": "Logged out successfully"}

"""Security, password hashing (argon2), and JWT authentication utilities."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

# Use argon2-cffi PasswordHasher
_ph = PasswordHasher()

# Compute one dummy hash at startup for timing-attack mitigation (SECURITY.md 2.1, D-019)
DUMMY_PASSWORD_HASH: str = _ph.hash("testpilot-dummy-constant-time-password-salt")


async def hash_password(password: str) -> str:
    """Hash password using argon2-cffi in a background worker thread."""
    return await asyncio.to_thread(_ph.hash, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against argon2 hash in a background worker thread."""

    def _verify() -> bool:
        try:
            return _ph.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(_verify)


async def verify_dummy_password(plain_password: str) -> bool:
    """Run verification against startup dummy hash when user is not found.

    Ensures response latency is comparable to valid user lookup to thwart timing attacks.
    """
    return await verify_password(plain_password, DUMMY_PASSWORD_HASH)


def create_access_token(
    user_id: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, str, datetime]:
    """Create a signed HS256 JWT access token with exp, sub, and jti claims.

    Returns:
        Tuple of (encoded_jwt_token, jti, expiration_datetime_with_utc)
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token, jti, expire


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Requires HS256 algorithm and presence of exp, sub, and jti claims.
    Raises jwt.PyJWTError subclasses on failure.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
        options={
            "require": ["exp", "sub", "jti"],
            "verify_exp": True,
        },
    )
    return payload


def get_fernet():
    """Get Fernet instance initialized with CREDENTIAL_ENCRYPTION_KEY."""
    from cryptography.fernet import Fernet

    settings = get_settings()
    if not settings.CREDENTIAL_ENCRYPTION_KEY:
        raise ValueError("CREDENTIAL_ENCRYPTION_KEY is not configured in settings")
    return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_credential(plain_text: str) -> str:
    """Encrypt a credential string using Fernet symmetric encryption."""
    if plain_text is None:
        raise ValueError("Cannot encrypt None credential")
    f = get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_credential(cipher_text: str) -> str:
    """Decrypt a Fernet encrypted credential token to plaintext."""
    if not cipher_text:
        raise ValueError("Cannot decrypt empty credential token")
    f = get_fernet()
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")

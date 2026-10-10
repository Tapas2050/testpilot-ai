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


def sanitize_secret_values(text: Optional[str], secrets: Optional[list[str]] = None) -> str:
    """Scrub sensitive passwords, tokens, API keys, and connection strings from text."""
    if not text:
        return ""
    clean = str(text)

    import re

    # 1. Scrub credentials from connection strings: postgresql://user:password@host
    clean = re.sub(r"://([^:\s]+):([^@\s]+)@", r"://\1:[REDACTED]@", clean)

    # 2. Scrub Bearer tokens: Bearer eyJ...
    clean = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", clean, flags=re.IGNORECASE)

    # 3. Scrub common API key patterns (Google AI Studio, OpenAI, etc.)
    clean = re.sub(r"AIza[0-9A-Za-z_\-]{35}", "[REDACTED]", clean)
    clean = re.sub(r"sk-[0-9A-Za-z_\-]{20,}", "[REDACTED]", clean)

    # 4. Scrub configured secrets from settings
    try:
        settings = get_settings()
        configured_secrets = [
            getattr(settings, "JWT_SECRET", None),
            getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", None),
            getattr(settings, "GOOGLE_API_KEY", None),
            getattr(settings, "OPENAI_API_KEY", None),
            getattr(settings, "ANTHROPIC_API_KEY", None),
        ]
        for sec in configured_secrets:
            if sec and isinstance(sec, str) and len(sec) >= 4 and sec in clean:
                clean = clean.replace(sec, "[REDACTED]")
    except Exception:
        pass

    # 5. Scrub explicitly supplied secrets (e.g. project credentials)
    if secrets:
        for sec in secrets:
            if sec and isinstance(sec, str) and len(sec) >= 3 and sec in clean:
                clean = clean.replace(sec, "[REDACTED]")

    # 6. Scrub password=... or password='...' in strings
    clean = re.sub(
        r"(password\s*[:=]\s*['\"]?)([^'\",\s]+)(['\"]?)",
        r"\1[REDACTED]\3",
        clean,
        flags=re.IGNORECASE,
    )

    return clean


def format_run_failure_message(
    stage: str,
    exc: Union[str, Exception],
    test_key: Optional[str] = None,
    secrets: Optional[list[str]] = None,
) -> str:
    """Format an honest, sanitized run failure message."""
    if isinstance(exc, Exception):
        exc_type = type(exc).__name__
        raw_msg = str(exc).strip() or exc_type
    else:
        exc_type = "Failure"
        raw_msg = str(exc).strip()

    clean_msg = sanitize_secret_values(raw_msg, secrets)
    short_msg = clean_msg.splitlines()[0] if clean_msg else exc_type
    if len(short_msg) > 300:
        short_msg = short_msg[:297] + "..."

    test_part = f":{test_key}" if test_key else ""
    return f"[{stage}{test_part}] {exc_type}: {short_msg}"


"""Unit tests for password hashing and JWT helpers in app.core.security."""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)


@pytest.mark.asyncio
async def test_password_hashing_uniqueness_and_verification():
    """T2.2: Password hashing generates unique salt hashes and verifies correctly."""
    pwd = "CorrectHorseBatteryStaple123"
    hash1 = await hash_password(pwd)
    hash2 = await hash_password(pwd)

    # Argon2 produces distinct salts for identical inputs
    assert hash1 != hash2
    assert "$argon2" in hash1
    assert "$argon2" in hash2

    assert await verify_password(pwd, hash1) is True
    assert await verify_password(pwd, hash2) is True
    assert await verify_password("WrongPassword123", hash1) is False
    assert await verify_password("", hash1) is False


@pytest.mark.asyncio
async def test_verify_dummy_password():
    """Verify dummy password comparison completes without errors."""
    result = await verify_dummy_password("any_user_input_password")
    assert result is False


def test_jwt_token_creation_and_decoding():
    """T2.4: JWT token creation contains sub, jti, exp and decodes accurately."""
    user_id = uuid.uuid4()
    token, jti, expire = create_access_token(user_id)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["jti"] == jti
    assert "exp" in payload
    assert payload["exp"] == int(expire.timestamp())


def test_jwt_tampered_signature_rejected():
    """T2.8: JWT with tampered signature is rejected."""
    user_id = uuid.uuid4()
    token, _, _ = create_access_token(user_id)

    # Tamper with signature
    parts = token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.invalidsignature"

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(tampered_token)


def test_jwt_expired_token_rejected():
    """T2.4: Expired JWT is rejected."""
    user_id = uuid.uuid4()
    token, _, _ = create_access_token(user_id, expires_delta=timedelta(seconds=-10))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_missing_required_claims_rejected():
    """T2.8: Tokens missing jti or sub or exp are rejected."""
    settings = get_settings()

    # Missing jti
    no_jti_token = jwt.encode(
        {"sub": "123", "exp": 9999999999},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(no_jti_token)

    # Missing sub
    no_sub_token = jwt.encode(
        {"jti": "abc", "exp": 9999999999},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(no_sub_token)


def test_jwt_wrong_algorithm_rejected():
    """T2.8: Tokens signed with unexpected algorithm (e.g. HS384) are rejected."""
    settings = get_settings()
    wrong_alg_token = jwt.encode(
        {"sub": "123", "jti": "abc", "exp": 9999999999},
        settings.JWT_SECRET,
        algorithm="HS384",
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(wrong_alg_token)

"""Tests for Fernet credential encryption and decryption (T3.4)."""

import pytest
from cryptography.fernet import InvalidToken

from app.core.security import decrypt_credential, encrypt_credential


def test_credential_encryption_and_decryption_roundtrip():
    """T3.4: Credential encryption produces opaque token and decrypts accurately."""
    raw_password = "SuperSecretAdminPassword#2026!"
    encrypted = encrypt_credential(raw_password)

    # Must be encrypted and not contain plaintext
    assert encrypted != raw_password
    assert raw_password not in encrypted
    assert len(encrypted) > 40

    # Decrypts back to exact original
    decrypted = decrypt_credential(encrypted)
    assert decrypted == raw_password


def test_credential_encryption_randomness():
    """T3.4: Encrypting the same password multiple times produces distinct ciphertexts."""
    pwd = "StaticPassword123"
    enc1 = encrypt_credential(pwd)
    enc2 = encrypt_credential(pwd)

    assert enc1 != enc2
    assert decrypt_credential(enc1) == pwd
    assert decrypt_credential(enc2) == pwd


def test_invalid_credential_decryption_fails():
    """T3.4: Tampered or invalid ciphertext raises InvalidToken."""
    with pytest.raises(InvalidToken):
        decrypt_credential("invalid-tampered-ciphertext-token")

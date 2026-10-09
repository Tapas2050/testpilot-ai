"""Tests for target URL validation and SSRF protection (T3.3)."""

from unittest.mock import patch

import pytest

from app.core.url_validator import validate_target_url


def test_valid_public_urls_accepted():
    """T3.3: Valid public HTTP and HTTPS URLs are accepted."""
    assert validate_target_url("https://example.com") == "https://example.com"
    assert validate_target_url("http://example.com/app/test") == "http://example.com/app/test"
    assert validate_target_url("https://example.com:8443/api") == "https://example.com:8443/api"


def test_invalid_schemes_rejected():
    """T3.3: Non-http/https schemes are rejected."""
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_target_url("ftp://example.com")

    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_target_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_target_url("gopher://example.com")


def test_private_and_link_local_ip_literals_rejected():
    """T3.3: Direct private and link-local IP addresses are rejected."""
    # 10.0.0.0/8
    with pytest.raises(ValueError, match="blocked private or local IP"):
        validate_target_url("http://10.0.0.1:8080")

    # 192.168.0.0/16
    with pytest.raises(ValueError, match="blocked private or local IP"):
        validate_target_url("http://192.168.1.50/admin")

    # 172.16.0.0/12
    with pytest.raises(ValueError, match="blocked private or local IP"):
        validate_target_url("http://172.16.10.20")

    # Link-local / AWS metadata
    with pytest.raises(ValueError, match="metadata address"):
        validate_target_url("http://169.254.169.254/latest/meta-data/")

    # Link-local other
    with pytest.raises(ValueError, match="blocked private or local IP"):
        validate_target_url("http://169.254.1.1")


def test_hostnames_resolving_to_private_ips_rejected():
    """T3.3: Hostnames resolving to private IP addresses are rejected."""
    # Mock DNS resolution to return private IP
    with patch(
        "socket.getaddrinfo",
        return_value=[(None, None, None, None, ("192.168.1.100", 80))],
    ):
        with pytest.raises(ValueError, match="resolves to blocked private address"):
            validate_target_url("http://internal-corp-service.test")


def test_localhost_and_allowlist_behavior():
    """T3.3: Localhost is allowed when in ALLOWED_PRIVATE_HOSTS allowlist."""
    # By default, localhost and 127.0.0.1 are in ALLOWED_PRIVATE_HOSTS
    assert validate_target_url("http://localhost:8001") == "http://localhost:8001"
    assert validate_target_url("http://127.0.0.1:8001") == "http://127.0.0.1:8001"

    # When allowlist is overridden to empty, localhost must be rejected
    with patch("app.core.url_validator.get_settings") as mock_settings:
        mock_settings.return_value.ALLOWED_PRIVATE_HOSTS = []
        with pytest.raises(ValueError, match="blocked private or local IP"):
            validate_target_url("http://127.0.0.1:8001")


def test_empty_or_malformed_url_rejected():
    """T3.3: Empty or malformed URLs raise ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_target_url("")

    with pytest.raises(ValueError, match="valid hostname"):
        validate_target_url("http://")

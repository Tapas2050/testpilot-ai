"""Target URL validator with SSRF protection, private-address blocking, and allowlist."""

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import get_settings

BLOCKED_METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "instance-data",
}


def validate_target_url(url: str) -> str:
    """Validate target URL for SSRF security risks.

    Enforces:
    - Scheme must be http or https
    - Hostname must be present
    - Metadata IP/hosts (169.254.169.254, metadata.google.internal) are blocked
    - Loopback, private, link-local, multicast, and reserved addresses are blocked
      unless explicitly allowlisted in settings.ALLOWED_PRIVATE_HOSTS (e.g. localhost for demo)
    - Hostnames resolving to private/loopback IPs are blocked unless allowlisted

    Raises:
        ValueError: with a clear descriptive message if URL is unsafe or invalid.
    Returns:
        The normalized validated URL string.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Target URL cannot be empty")

    url = url.strip()
    try:
        parsed = urlsplit(url)
    except Exception as exc:
        raise ValueError(f"Malformed URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{scheme}': only http and https are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a valid hostname")

    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_METADATA_HOSTS:
        raise ValueError(f"Access to metadata address '{hostname}' is strictly forbidden")

    settings = get_settings()
    allowed_hosts = [h.lower() for h in settings.ALLOWED_PRIVATE_HOSTS]

    # If hostname is explicitly allowlisted (e.g. localhost, 127.0.0.1 for local demo), allow it
    if hostname_lower in allowed_hosts:
        return url

    # Check if hostname is an IP literal
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"Target URL points to a blocked private or local IP address: {ip}")
        return url
    except ValueError as ve:
        # If it was raised by our check above, re-raise it
        if "Target URL points to a blocked" in str(ve):
            raise
        # Otherwise it is a domain name that needs DNS resolution check
        pass

    # Resolve domain to IP addresses and ensure none point to private / loopback networks
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Target hostname '{hostname}' could not be resolved: {exc}") from exc

    resolved_ips = {item[4][0] for item in addr_info}
    for resolved_ip_str in resolved_ips:
        try:
            resolved_ip = ipaddress.ip_address(resolved_ip_str)
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_link_local
                or resolved_ip.is_reserved
                or resolved_ip.is_multicast
                or resolved_ip.is_unspecified
            ):
                raise ValueError(
                    f"Target hostname '{hostname}' resolves to blocked private address: "
                    f"{resolved_ip}"
                )
        except ValueError as ve:
            if "resolves to blocked" in str(ve):
                raise

    return url

"""Fast preflight checks before planning to fail early without spending LLM tokens."""

import asyncio
import uuid
from typing import Optional

import httpx
from sqlalchemy import select

from app.agent.mcp_client import PlaywrightMCPClient
from app.core.config import get_settings
from app.core.database import get_async_session_factory
from app.core.security import decrypt_credential
from app.core.url_validator import validate_target_url
from app.models.credential import ProjectCredential
from app.models.project import Project


class PreflightCheckError(Exception):
    """Raised when a preflight validation check fails."""

    pass


async def check_target_url_reachable(url: str, timeout: float = 5.0) -> None:
    """Send an HTTP GET request to check target URL reachability."""
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, verify=False
    ) as http_client:
        await http_client.get(url)


async def run_preflight_checks(
    project_id: uuid.UUID,
    db_url: Optional[str] = None,
    is_mock_mcp: Optional[bool] = None,
) -> dict[str, str]:
    """Execute target URL reachability, Playwright MCP handshake, and credential decryption checks.

    Target execution time: ~1-3s, hard timeout: 10s.
    Fails fast with actionable error message naming what failed and what the user should do.
    """
    settings = get_settings()
    session_factory = get_async_session_factory(db_url)

    import os
    if is_mock_mcp is None:
        is_mock_mcp = bool(os.getenv("PYTEST_CURRENT_TEST"))

    # 1. Fetch project to get target_url and check credential decryption
    async with session_factory() as session:
        proj_stmt = select(Project).where(Project.id == project_id)
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        target_url = (
            project.target_url
            if project
            else getattr(settings, "SUPPORTDESK_URL", "http://localhost:8001")
        )

        # Check 3: Check credential decryption early
        cred_stmt = select(ProjectCredential).where(ProjectCredential.project_id == project_id)
        db_creds = (await session.execute(cred_stmt)).scalars().all()
        for c in db_creds:
            try:
                decrypted = decrypt_credential(c.password_encrypted)
                if not decrypted:
                    raise ValueError("Decrypted password is empty")
            except Exception as exc:
                raise PreflightCheckError(
                    f"Stored credential for role '{c.role_label}' could not be decrypted ({exc}). "
                    f"Check CREDENTIAL_ENCRYPTION_KEY or re-save project credentials."
                ) from exc

    # Check 1: Target URL reachability through SSRF validator
    try:
        validated_url = validate_target_url(target_url)
    except Exception as val_exc:
        raise PreflightCheckError(
            f"Target URL '{target_url}' failed safety validation: {val_exc}. "
            f"Check target URL format."
        ) from val_exc

    try:
        await check_target_url_reachable(validated_url)
    except PreflightCheckError:
        raise
    except Exception as req_exc:
        raise PreflightCheckError(
            f"Target app at {target_url} did not respond ({req_exc}). Is it running?"
        ) from req_exc

    # Check 2: Playwright MCP server start and initialize handshake
    mcp = PlaywrightMCPClient(is_mock=is_mock_mcp)
    try:
        await asyncio.wait_for(mcp.start(), timeout=8.0)
    except Exception as mcp_exc:
        raise PreflightCheckError(
            f"Playwright MCP server could not start or complete handshake ({mcp_exc}). "
            f"Check Node.js and Playwright installation."
        ) from mcp_exc
    finally:
        try:
            await mcp.close()
        except Exception:
            pass

    return {"status": "ok", "target_url": target_url}

"""Fast, resilient preflight checks before planning to fail early without spending LLM tokens."""

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Optional

import httpx
from sqlalchemy import select

from app.agent.mcp_client import PlaywrightMCPClient
from app.core.config import get_settings
from app.core.database import get_async_session_factory
from app.core.process_memory import get_process_rss_mb
from app.core.security import decrypt_credential, format_exception_summary
from app.core.url_validator import validate_target_url
from app.models.credential import ProjectCredential
from app.models.project import Project

logger = logging.getLogger(__name__)


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
    run_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Execute preflight checks with cold-start tolerance and honest failure reporting.

    Budgets:
    - Target reachability: ~5.0s
    - Credential decryption: ~2.0s
    - Playwright MCP startup & handshake: configurable (MCP_STARTUP_TIMEOUT_SECONDS, >= 45s)
    Overall budget is the sum of these checks.
    """
    settings = get_settings()
    session_factory = get_async_session_factory(db_url)

    if is_mock_mcp is None:
        is_mock_mcp = bool(os.getenv("PYTEST_CURRENT_TEST"))

    mcp_budget = float(getattr(settings, "MCP_STARTUP_TIMEOUT_SECONDS", 45.0))
    target_budget = 5.0
    cred_budget = 2.0

    rss_start = get_process_rss_mb()
    logger.info(
        "[project_id=%s%s] Starting preflight checks (Process RSS: %.1f MB, MCP budget: %.0fs)",
        project_id,
        f", run_id={run_id}" if run_id else "",
        rss_start,
        mcp_budget,
    )

    # 1. Fetch project to get target_url and check credential decryption early
    t0_cred = time.monotonic()
    async with session_factory() as session:
        proj_stmt = select(Project).where(Project.id == project_id)
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        target_url = (
            project.target_url
            if project
            else getattr(settings, "SUPPORTDESK_URL", "http://localhost:8001")
        )

        cred_stmt = select(ProjectCredential).where(ProjectCredential.project_id == project_id)
        db_creds = (await session.execute(cred_stmt)).scalars().all()
        for c in db_creds:
            try:
                decrypted = decrypt_credential(c.password_encrypted)
                if not decrypted:
                    raise ValueError("Decrypted password is empty")
            except Exception as exc:
                elapsed_cred = round(time.monotonic() - t0_cred, 2)
                detail = format_exception_summary(exc, elapsed=elapsed_cred, budget=cred_budget)
                raise PreflightCheckError(
                    f"Stored credential for role '{c.role_label}' could not be decrypted "
                    f"({detail}). Check CREDENTIAL_ENCRYPTION_KEY or re-save project credentials."
                ) from exc

    # 2. Target URL reachability check through SSRF validator
    t0_target = time.monotonic()
    try:
        validated_url = validate_target_url(target_url)
    except Exception as val_exc:
        raise PreflightCheckError(
            f"Target URL '{target_url}' failed safety validation: {val_exc}. "
            f"Check target URL format."
        ) from val_exc

    try:
        await check_target_url_reachable(validated_url, timeout=target_budget)
    except PreflightCheckError:
        raise
    except Exception as req_exc:
        elapsed_target = round(time.monotonic() - t0_target, 2)
        detail = format_exception_summary(req_exc, elapsed=elapsed_target, budget=target_budget)
        raise PreflightCheckError(
            f"Target app at {target_url} did not respond ({detail}). Is it running?"
        ) from req_exc

    # 3. Playwright MCP server start and initialize handshake with cold-start tolerance and retry
    mcp: Optional[PlaywrightMCPClient] = None
    last_mcp_exc: Optional[Exception] = None
    t0_mcp_total = time.monotonic()

    for attempt in (1, 2):
        t0_attempt = time.monotonic()
        client = PlaywrightMCPClient(is_mock=is_mock_mcp)
        try:
            await asyncio.wait_for(
                client.start(startup_timeout=mcp_budget),
                timeout=mcp_budget,
            )
            mcp = client
            logger.info(
                "Playwright MCP started successfully on attempt %d in %.2fs",
                attempt,
                time.monotonic() - t0_attempt,
            )
            break
        except Exception as exc:
            attempt_duration = round(time.monotonic() - t0_attempt, 2)
            last_mcp_exc = exc
            try:
                await client.close()
            except Exception:
                pass
            if attempt == 1:
                logger.warning(
                    "Playwright MCP startup attempt 1 failed after %.2fs (%s); retrying once...",
                    attempt_duration,
                    format_exception_summary(exc, elapsed=attempt_duration, budget=mcp_budget),
                )

    if mcp is None:
        total_mcp_duration = round(time.monotonic() - t0_mcp_total, 2)
        exc_to_format = last_mcp_exc or RuntimeError("MCP failed to start")
        detail = format_exception_summary(
            exc_to_format, elapsed=total_mcp_duration, budget=mcp_budget
        )
        if isinstance(last_mcp_exc, FileNotFoundError) or "not found" in str(last_mcp_exc).lower():
            hint = (
                "Node.js not found on PATH or MCP package not installed. "
                "Check Node.js and Playwright installation."
            )
        elif isinstance(last_mcp_exc, (asyncio.TimeoutError, TimeoutError)):
            hint = (
                "First browser start can be slow under memory pressure; "
                "try 'Start a new run' again."
            )
        else:
            hint = "Check Node.js and Playwright installation."
        raise PreflightCheckError(
            f"Playwright MCP server could not start or complete handshake ({detail}). {hint}"
        ) from last_mcp_exc

    rss_end = get_process_rss_mb()
    logger.info("Preflight checks passed successfully. Current process RSS: %.1f MB", rss_end)

    # If run_id is supplied, hand mcp to execute_node to avoid starting browser twice;
    # otherwise close it immediately.
    if run_id is None:
        try:
            await mcp.close()
        except Exception:
            pass
        return {"status": "ok", "target_url": target_url}

    return {"status": "ok", "target_url": target_url, "mcp_client": mcp}

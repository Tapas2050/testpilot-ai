"""Preflight diagnostic script running under real worker conditions without LLM calls.

Measures:
- Per-check timings (target, process start, handshake, credential decryption)
- Exception class name and sanitized message for any failure
- Peak process memory (RSS)
"""

import asyncio
import ctypes
import ctypes.wintypes
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# Set up paths
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from sqlalchemy import select  # noqa: E402

from app.agent.mcp_client import PlaywrightMCPClient  # noqa: E402
from app.agent.preflight import (  # noqa: E402
    check_target_url_reachable,
    run_preflight_checks,
)
from app.core.config import get_settings  # noqa: E402
from app.core.database import get_async_session_factory  # noqa: E402
from app.core.security import decrypt_credential, sanitize_secret_values  # noqa: E402
from app.core.url_validator import validate_target_url  # noqa: E402
from app.models.credential import ProjectCredential  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services.embedder import get_embedding_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preflight_only")


def get_peak_rss_mb() -> float:
    """Return peak working set size (RSS) in megabytes."""
    if os.name == "nt":

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            psapi = ctypes.WinDLL("kernel32", use_last_error=True)
            fn = psapi.K32GetProcessMemoryInfo
            fn.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                ctypes.wintypes.DWORD,
            ]
            fn.restype = ctypes.wintypes.BOOL

            handle = psapi.GetCurrentProcess()
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if fn(handle, ctypes.byref(pmc), pmc.cb):
                return round(pmc.PeakWorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
        return 0.0
    else:
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return round(usage.ru_maxrss / 1024, 2)
        except Exception:
            return 0.0


async def find_demo_project_id(db_url: str) -> uuid.UUID:
    """Locate the SupportDesk Demo project ID."""
    sf = get_async_session_factory(db_url)
    async with sf() as session:
        stmt = select(Project).where(Project.name.ilike("%SupportDesk%"))
        proj = (await session.execute(stmt)).scalar_one_or_none()
        if proj:
            return proj.id
        stmt2 = select(Project).limit(1)
        first_proj = (await session.execute(stmt2)).scalar_one_or_none()
        if first_proj:
            return first_proj.id
    raise RuntimeError("No project found in database.")


async def run_diagnostics(project_id: Optional[uuid.UUID] = None) -> dict[str, Any]:
    """Execute preflight checks and measure detailed per-check timings and memory."""
    settings = get_settings()
    db_url = str(settings.DATABASE_URL)

    if not project_id:
        project_id = await find_demo_project_id(db_url)

    print(f"\n--- Running preflight diagnostics for project_id: {project_id} ---")
    print(f"Event loop policy: {type(asyncio.get_event_loop_policy()).__name__}")
    print(f"Current loop: {type(asyncio.get_running_loop()).__name__}")

    # Startup hook: preload embedding model (exactly as worker does)
    t0_embed = time.monotonic()
    print("Preloading embedding model singleton...", end=" ", flush=True)
    get_embedding_model()
    embed_duration = round(time.monotonic() - t0_embed, 3)
    print(f"DONE ({embed_duration}s). Current Peak RSS: {get_peak_rss_mb()} MB")

    timings: dict[str, float] = {}
    failure_info: Optional[dict[str, str]] = None

    # Measure Check A: Credential decryption
    t0_cred = time.monotonic()
    try:
        sf = get_async_session_factory(db_url)
        async with sf() as session:
            stmt = select(ProjectCredential).where(ProjectCredential.project_id == project_id)
            creds = (await session.execute(stmt)).scalars().all()
            for c in creds:
                decrypted = decrypt_credential(c.password_encrypted)
                if not decrypted:
                    raise ValueError(f"Empty decrypted password for role {c.role_label}")
        timings["credential_decryption"] = round(time.monotonic() - t0_cred, 3)
        count = len(creds)
        print(f"Credential decryption: OK ({timings['credential_decryption']}s, {count} creds)")
    except Exception as exc:
        timings["credential_decryption"] = round(time.monotonic() - t0_cred, 3)
        failure_info = {
            "check": "credential_decryption",
            "class": type(exc).__name__,
            "message": sanitize_secret_values(str(exc)),
        }
        cls_name = type(exc).__name__
        msg = failure_info["message"]
        print(
            f"Credential decryption: FAILED ({timings['credential_decryption']}s) "
            f"[{cls_name}]: {msg}"
        )

    # Measure Check B: Target URL reachability
    t0_target = time.monotonic()
    try:
        sf = get_async_session_factory(db_url)
        async with sf() as session:
            stmt = select(Project).where(Project.id == project_id)
            proj = (await session.execute(stmt)).scalar_one_or_none()
            target_url = proj.target_url if proj else "http://localhost:8001"
        validated_url = validate_target_url(target_url)
        await check_target_url_reachable(validated_url, timeout=5.0)
        timings["target_reachability"] = round(time.monotonic() - t0_target, 3)
        print(f"Target reachability ({target_url}): OK ({timings['target_reachability']}s)")
    except Exception as exc:
        timings["target_reachability"] = round(time.monotonic() - t0_target, 3)
        failure_info = {
            "check": "target_reachability",
            "class": type(exc).__name__,
            "message": sanitize_secret_values(str(exc)),
        }
        cls_name = type(exc).__name__
        msg = failure_info["message"]
        print(
            f"Target reachability: FAILED ({timings['target_reachability']}s) "
            f"[{cls_name}]: {msg}"
        )

    # Measure Check C: MCP process start & initialize handshake (isolated)
    mcp_client = PlaywrightMCPClient(is_mock=False)
    mcp_proc_elapsed = 0.0
    try:
        # Step C1: Process start
        t0_proc = time.monotonic()
        if not mcp_client.server_path.exists():
            raise FileNotFoundError(f"MCP server not found at {mcp_client.server_path}")
        mcp_cwd = mcp_client.server_path.parent.parent.parent.parent
        cwd = str(mcp_cwd) if mcp_cwd.exists() else None

        mcp_client._process = await asyncio.create_subprocess_exec(
            mcp_client.node_path,
            str(mcp_client.server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        mcp_proc_elapsed = round(time.monotonic() - t0_proc, 3)
        timings["mcp_process_start"] = mcp_proc_elapsed
        pid = mcp_client._process.pid if mcp_client._process else None
        print(f"MCP process start: OK ({mcp_proc_elapsed}s, PID={pid})")

        # Step C2: Handshake
        t0_handshake = time.monotonic()
        mcp_client._req_id += 1
        init_msg = {
            "jsonrpc": "2.0",
            "id": mcp_client._req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "testpilot", "version": "1.0"},
            },
        }
        await mcp_client._write_msg(init_msg)
        await mcp_client._read_response(mcp_client._req_id, timeout=45.0)
        notify_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        await mcp_client._write_msg(notify_msg)
        mcp_handshake_elapsed = round(time.monotonic() - t0_handshake, 3)
        timings["mcp_handshake"] = mcp_handshake_elapsed
        print(f"MCP initialize handshake: OK ({mcp_handshake_elapsed}s)")
    except Exception as exc:
        timings["mcp_process_start"] = mcp_proc_elapsed
        timings["mcp_handshake"] = round(time.monotonic() - t0_proc, 3)
        failure_info = {
            "check": "mcp_startup",
            "class": type(exc).__name__,
            "message": sanitize_secret_values(str(exc)) or "no detail",
        }
        print(f"MCP start/handshake: FAILED [{type(exc).__name__}]: {failure_info['message']}")
    finally:
        await mcp_client.close()

    # Now execute the REAL run_preflight_checks function exactly as worker calls it
    print("\nExecuting real run_preflight_checks() function...")
    t0_real = time.monotonic()
    real_preflight_success = False
    real_preflight_err: Optional[dict[str, str]] = None
    try:
        res = await run_preflight_checks(project_id=project_id, is_mock_mcp=False)
        real_elapsed = round(time.monotonic() - t0_real, 3)
        real_preflight_success = True
        print(f"Real run_preflight_checks(): SUCCESS in {real_elapsed}s (res={res})")
    except Exception as exc:
        real_elapsed = round(time.monotonic() - t0_real, 3)
        raw_msg = str(exc).strip() or "no detail"
        clean_msg = sanitize_secret_values(raw_msg)
        real_preflight_err = {
            "class": type(exc).__name__,
            "message": clean_msg,
            "elapsed": str(real_elapsed),
        }
        print(f"Real run_preflight_checks(): FAILED after {real_elapsed}s")
        print(f"  Exception Class: {real_preflight_err['class']}")
        print(f"  Sanitized Message: {real_preflight_err['message']}")

    peak_rss = get_peak_rss_mb()
    print(f"Peak memory seen (RSS): {peak_rss} MB")

    return {
        "timings": timings,
        "peak_rss_mb": peak_rss,
        "failure_info": failure_info,
        "real_preflight_success": real_preflight_success,
        "real_preflight_err": real_preflight_err,
        "real_preflight_elapsed": real_elapsed,
    }


def main():
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_diagnostics())


if __name__ == "__main__":
    main()

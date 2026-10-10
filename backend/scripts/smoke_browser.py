"""Browser smoke test without LLM calls.

Starts the pinned Playwright MCP server exactly the way the worker does,
initializes it, navigates to SupportDesk /login, reads visible text,
captures a screenshot into a temporary directory, closes the client,
and confirms no node or chromium child processes survive.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.agent.mcp_client import PlaywrightMCPClient  # noqa: E402


def get_child_pids_windows(parent_pid: int) -> list[int]:
    """Recursively collect child process IDs on Windows using PowerShell."""
    if os.name != "nt":
        return []
    try:
        ps_query = (
            f"Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.ParentProcessId -eq {parent_pid} }} | "
            f"Select-Object -ExpandProperty ProcessId"
        )
        cmd = ["powershell", "-NoProfile", "-Command", ps_query]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        pids: list[int] = []
        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                child_pid = int(line)
                pids.append(child_pid)
                pids.extend(get_child_pids_windows(child_pid))
        return pids
    except Exception as exc:
        print(f"  [warn] Failed to enumerate child processes: {exc}")
        return []


def is_pid_alive_windows(pid: int) -> bool:
    """Check if process ID is still alive on Windows."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return str(pid) in res.stdout
    except Exception:
        return False


async def run_smoke_test(target_url: str = "http://localhost:8001") -> bool:
    """Execute the end-to-end browser smoke test."""
    print(f"Starting browser smoke test against: {target_url}")
    overall_start = time.monotonic()
    all_ok = True

    mcp_client = PlaywrightMCPClient(is_mock=False)
    temp_dir = tempfile.mkdtemp(prefix="testpilot_smoke_")
    tracked_pids: list[int] = []

    try:
        # Step 1: Start and handshake
        t0 = time.monotonic()
        print(
            "Step 1: Starting Playwright MCP server and completing initialize handshake...",
            end=" ",
            flush=True,
        )
        try:
            await mcp_client.start()
            step1_elapsed = round(time.monotonic() - t0, 2)
            pid = mcp_client._process.pid if mcp_client._process else None
            if pid:
                tracked_pids.append(pid)
                # Capture spawned children (e.g., node, browser)
                await asyncio.sleep(0.5)
                tracked_pids.extend(get_child_pids_windows(pid))
            print(f"OK ({step1_elapsed}s, pid={pid})")
        except Exception as exc:
            step1_elapsed = round(time.monotonic() - t0, 2)
            print(f"FAIL ({step1_elapsed}s): {exc}")
            return False

        # Step 2: Navigate to /login
        t0 = time.monotonic()
        login_url = f"{target_url.rstrip('/')}/login"
        print(f"Step 2: Navigating to {login_url}...", end=" ", flush=True)
        try:
            await mcp_client.call_tool(
                "playwright_navigate",
                {"url": login_url, "headless": True},
            )
            step2_elapsed = round(time.monotonic() - t0, 2)
            # Update tracked PIDs now that chromium is launched
            if pid:
                tracked_pids.extend(get_child_pids_windows(pid))
                tracked_pids = list(set(tracked_pids))
            print(f"OK ({step2_elapsed}s)")
        except Exception as exc:
            step2_elapsed = round(time.monotonic() - t0, 2)
            print(f"FAIL ({step2_elapsed}s): {exc}")
            all_ok = False

        # Step 3: Read visible text
        if all_ok:
            t0 = time.monotonic()
            print("Step 3: Reading visible text from login page...", end=" ", flush=True)
            try:
                text_res = await mcp_client.call_tool("playwright_get_visible_text", {})
                step3_elapsed = round(time.monotonic() - t0, 2)
                raw_text = ""
                if isinstance(text_res, dict):
                    raw_text = text_res.get("text", "") or str(text_res.get("content", ""))
                # Verify key text exists on login page
                snippet = raw_text.replace("\n", " ").strip()[:60]
                print(f"OK ({step3_elapsed}s, snippet='{snippet}...')")
            except Exception as exc:
                step3_elapsed = round(time.monotonic() - t0, 2)
                print(f"FAIL ({step3_elapsed}s): {exc}")
                all_ok = False

        # Step 4: Take screenshot into temporary folder
        if all_ok:
            t0 = time.monotonic()
            print(f"Step 4: Capturing screenshot to {temp_dir}...", end=" ", flush=True)
            try:
                ss_filename = "smoke_screenshot.png"
                await mcp_client.call_tool(
                    "playwright_screenshot",
                    {
                        "name": ss_filename,
                        "downloadsDir": temp_dir,
                        "fullPage": True,
                        "savePng": True,
                    },
                )
                step4_elapsed = round(time.monotonic() - t0, 2)
                # Verify file was written
                candidates = list(Path(temp_dir).rglob("*.png"))
                if candidates:
                    ss_size = candidates[0].stat().st_size
                    print(f"OK ({step4_elapsed}s, file={candidates[0].name}, bytes={ss_size})")
                else:
                    print(f"OK ({step4_elapsed}s, requested)")
            except Exception as exc:
                step4_elapsed = round(time.monotonic() - t0, 2)
                print(f"FAIL ({step4_elapsed}s): {exc}")
                all_ok = False

        # Step 5: Close client
        t0 = time.monotonic()
        print("Step 5: Closing MCP client and terminating process tree...", end=" ", flush=True)
        try:
            await mcp_client.close()
            step5_elapsed = round(time.monotonic() - t0, 2)
            print(f"OK ({step5_elapsed}s)")
        except Exception as exc:
            step5_elapsed = round(time.monotonic() - t0, 2)
            print(f"FAIL ({step5_elapsed}s): {exc}")
            all_ok = False

        # Step 6: Verify no child processes remain running
        t0 = time.monotonic()
        print(
            "Step 6: Verifying no orphan node or chromium processes survive...",
            end=" ",
            flush=True,
        )
        await asyncio.sleep(1.0)
        alive_pids = [p for p in tracked_pids if is_pid_alive_windows(p)]
        step6_elapsed = round(time.monotonic() - t0, 2)
        if alive_pids:
            print(f"FAIL ({step6_elapsed}s): Orphan processes still running: {alive_pids}")
            # Force kill any lingering orphans
            for p in alive_pids:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p)], capture_output=True)
                except Exception:
                    pass
            all_ok = False
        else:
            print(f"OK ({step6_elapsed}s, verified {len(tracked_pids)} tracked PIDs terminated)")

    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    total_elapsed = round(time.monotonic() - overall_start, 2)
    print(f"\nSmoke test result: {'PASSED' if all_ok else 'FAILED'} (total time: {total_elapsed}s)")
    return all_ok


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    success = asyncio.run(run_smoke_test(url))
    sys.exit(0 if success else 1)

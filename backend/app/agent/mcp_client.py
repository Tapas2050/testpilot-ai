"""Playwright MCP client running over non-blocking stdio pipes with timeout enforcement."""

import asyncio
import atexit
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Strict security allowlist per SECURITY.md and D-008
ALLOWLISTED_TOOLS: frozenset[str] = frozenset({
    "playwright_navigate",
    "playwright_screenshot",
    "playwright_click",
    "playwright_fill",
    "playwright_select",
    "playwright_hover",
    "playwright_get_visible_text",
    "playwright_press_key",
    "playwright_close",
})

# Configurable tool timeouts (navigation 45s, other actions 30s, screenshot 30s)
DEFAULT_TOOL_TIMEOUTS: dict[str, float] = {
    "playwright_navigate": 45.0,
    "playwright_screenshot": 30.0,
}
DEFAULT_ACTION_TIMEOUT: float = 30.0

# Process tracking for guaranteed cleanup on worker exit
_all_running_pids: set[int] = set()


def kill_process_tree(pid: int) -> None:
    """Kill the entire process tree including all child processes (Windows & POSIX)."""
    if not pid:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except Exception as e:
            logger.warning("taskkill failed for PID %d: %s", pid, e)
    else:
        import signal

        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def _cleanup_all_mcp_processes() -> None:
    """atexit handler ensuring no node or chromium processes survive worker exit."""
    for pid in list(_all_running_pids):
        kill_process_tree(pid)


atexit.register(_cleanup_all_mcp_processes)


class ToolTimeoutError(RuntimeError):
    """Raised when a browser tool call exceeds its allocated timeout."""

    pass


def get_default_mcp_server_path() -> Path:
    """Find the installed Playwright MCP server entrypoint."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    server_path = (
        repo_root
        / "mcp"
        / "node_modules"
        / "@executeautomation"
        / "playwright-mcp-server"
        / "dist"
        / "index.js"
    )
    return server_path


def get_node_executable() -> str:
    """Locate the Node.js executable."""
    node_on_path = shutil.which("node")
    if node_on_path:
        return node_on_path
    standard_windows_node = r"C:\Program Files\nodejs\node.exe"
    if os.path.exists(standard_windows_node):
        return standard_windows_node
    return "node"


class PlaywrightMCPClient:
    """Manages child process running Playwright MCP server over non-blocking stdio."""

    def __init__(
        self,
        server_path: Optional[str | Path] = None,
        node_path: Optional[str] = None,
        is_mock: bool = False,
        tool_timeouts: Optional[dict[str, float]] = None,
        default_timeout: Optional[float] = None,
    ) -> None:
        self.server_path = Path(server_path) if server_path else get_default_mcp_server_path()
        self.node_path = node_path or get_node_executable()
        self.is_mock = is_mock
        self.tool_timeouts = dict(DEFAULT_TOOL_TIMEOUTS)
        if tool_timeouts:
            self.tool_timeouts.update(tool_timeouts)
        self.default_timeout = default_timeout or DEFAULT_ACTION_TIMEOUT

        self._process: Optional[asyncio.subprocess.Process] = None
        self._req_id = 0
        self._mock_responses: dict[str, Any] = {}
        self._called_tools: list[tuple[str, dict[str, Any]]] = []

    def set_mock_response(self, tool_name: str, response: Any) -> None:
        """Set a simulated response for mock testing."""
        self._mock_responses[tool_name] = response

    @property
    def called_tools(self) -> list[tuple[str, dict[str, Any]]]:
        """Return list of (tool_name, arguments) called."""
        return list(self._called_tools)

    def get_tool_timeout(self, tool_name: str) -> float:
        """Return allocated timeout in seconds for the given tool."""
        return self.tool_timeouts.get(tool_name, self.default_timeout)

    async def start(self) -> None:
        """Launch the MCP child process using non-blocking asyncio subprocess."""
        if self.is_mock:
            return

        if not self.server_path.exists():
            raise FileNotFoundError(
                f"Playwright MCP server not found at {self.server_path}. "
                "Ensure 'npm install' was run in mcp/ directory."
            )

        mcp_cwd = self.server_path.parent.parent.parent.parent
        cwd = str(mcp_cwd) if mcp_cwd.exists() else None

        self._process = await asyncio.create_subprocess_exec(
            self.node_path,
            str(self.server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        if self._process.pid:
            _all_running_pids.add(self._process.pid)

        # Handshake step 1: initialize
        self._req_id += 1
        init_msg = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "testpilot", "version": "1.0"},
            },
        }
        await self._write_msg(init_msg)
        await self._read_response(self._req_id, timeout=25.0)

        # Handshake step 2: notifications/initialized
        notify_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        await self._write_msg(notify_msg)

    async def _write_msg(self, msg: dict[str, Any]) -> None:
        """Write JSON-RPC message asynchronously to stdin."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP process stdin not available")
        line = (json.dumps(msg) + "\n").encode("utf-8")
        self._process.stdin.write(line)
        await self._process.stdin.drain()

    async def _read_response(self, expected_id: int, timeout: float = 30.0) -> dict[str, Any]:
        """Read stdout lines with timeout until matching JSON-RPC response arrives."""
        if not self._process or not self._process.stdout:
            raise RuntimeError("MCP process stdout not available")

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            time_left = deadline - asyncio.get_running_loop().time()
            if time_left <= 0:
                raise asyncio.TimeoutError(
                    f"MCP timed out waiting for response ID {expected_id} after {timeout}s"
                )

            try:
                line_bytes = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=time_left,
                )
            except (asyncio.TimeoutError, TimeoutError):
                raise asyncio.TimeoutError(
                    f"MCP timed out waiting for response ID {expected_id} after {timeout}s"
                )
            if not line_bytes:
                stderr_output = ""
                if self._process.stderr:
                    try:
                        err_bytes = await asyncio.wait_for(
                            self._process.stderr.read(2048), timeout=1.0
                        )
                        stderr_output = err_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        pass
                raise RuntimeError(
                    f"MCP process closed unexpectedly without response for ID {expected_id}. "
                    f"Stderr: {stderr_output}"
                )

            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip notifications (no 'id' field or different id)
            if data.get("id") == expected_id:
                if "error" in data:
                    err = data["error"]
                    raise RuntimeError(f"MCP JSON-RPC Error: {err.get('message', str(err))}")
                return data

    async def kill_process_tree(self) -> None:
        """Forcefully kill the MCP process and all its children (Node, Chromium)."""
        if self._process:
            pid = self._process.pid
            _all_running_pids.discard(pid)
            kill_process_tree(pid)
            try:
                if self._process.stdin and not self._process.stdin.is_closing():
                    self._process.stdin.close()
            except Exception:
                pass
            try:
                if self._process.returncode is None:
                    self._process.kill()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except Exception:
                pass
            self._process = None

    async def restart(self) -> None:
        """Kill the current process tree and restart the MCP server cleanly."""
        await self.kill_process_tree()
        if not self.is_mock:
            await self.start()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Call an MCP tool ensuring allowlist compliance and timeout enforcement."""
        arguments = arguments or {}
        self._called_tools.append((tool_name, arguments))

        # Enforce tool allowlist (T10.1)
        if tool_name not in ALLOWLISTED_TOOLS:
            raise ValueError(
                f"Security violation: Tool '{tool_name}' is not permitted by allowlist. "
                f"Allowed tools: {sorted(ALLOWLISTED_TOOLS)}"
            )

        if self.is_mock:
            if tool_name in self._mock_responses:
                resp = self._mock_responses[tool_name]
                if isinstance(resp, Exception):
                    raise resp
                return resp
            if tool_name == "playwright_get_visible_text":
                return {"text": f"Page content placeholder step {len(self._called_tools)}"}
            if tool_name == "playwright_screenshot":
                return {"status": "saved", "path": "mock_screenshot.png"}
            return {"status": "ok", "tool": tool_name}

        effective_timeout = timeout if timeout is not None else self.get_tool_timeout(tool_name)
        try:
            self._req_id += 1
            req_msg = {
                "jsonrpc": "2.0",
                "id": self._req_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
            await self._write_msg(req_msg)
            resp = await self._read_response(self._req_id, timeout=effective_timeout)
            return resp.get("result", {})
        except (asyncio.TimeoutError, TimeoutError) as exc:
            logger.error(
                "MCP tool call '%s' timed out after %.1fs. Killing process tree and restarting.",
                tool_name,
                effective_timeout,
            )
            await self.restart()
            raise ToolTimeoutError(
                f"Browser tool '{tool_name}' timed out after {effective_timeout}s"
            ) from exc

    async def close(self) -> None:
        """Close browser context and terminate MCP child process tree."""
        if self.is_mock:
            return

        if self._process:
            try:
                # Attempt graceful browser close first if still running
                if self._process.returncode is None:
                    self._req_id += 1
                    close_msg = {
                        "jsonrpc": "2.0",
                        "id": self._req_id,
                        "method": "tools/call",
                        "params": {"name": "playwright_close", "arguments": {}},
                    }
                    await self._write_msg(close_msg)
                    try:
                        await self._read_response(self._req_id, timeout=2.0)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                await self.kill_process_tree()

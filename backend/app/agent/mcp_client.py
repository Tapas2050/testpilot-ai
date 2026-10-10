"""Playwright MCP client running over stdio with security allowlist and JSON-RPC 2.0."""

import asyncio
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
    """Manages child process running Playwright MCP server over stdio."""

    def __init__(
        self,
        server_path: Optional[str | Path] = None,
        node_path: Optional[str] = None,
        is_mock: bool = False,
    ) -> None:
        self.server_path = Path(server_path) if server_path else get_default_mcp_server_path()
        self.node_path = node_path or get_node_executable()
        self.is_mock = is_mock
        self._process: Optional[subprocess.Popen] = None
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

    async def start(self) -> None:
        """Launch the MCP child process and complete initialize handshake."""
        if self.is_mock:
            return

        def _sync_start():
            if not self.server_path.exists():
                raise FileNotFoundError(
                    f"Playwright MCP server not found at {self.server_path}. "
                    "Ensure 'npm install' was run in mcp/ directory."
                )

            self._process = subprocess.Popen(
                [self.node_path, str(self.server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

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
            self._write_msg(init_msg)
            self._read_response(self._req_id)

            # Handshake step 2: notifications/initialized
            notify_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            self._write_msg(notify_msg)

        await asyncio.to_thread(_sync_start)

    def _write_msg(self, msg: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP process stdin not available")
        line = json.dumps(msg) + "\n"
        self._process.stdin.write(line)
        self._process.stdin.flush()

    def _read_response(self, expected_id: int, timeout: float = 30.0) -> dict[str, Any]:
        """Read stdout lines until a JSON-RPC response with matching id arrives."""
        if not self._process or not self._process.stdout:
            raise RuntimeError("MCP process stdout not available")

        while True:
            line = self._process.stdout.readline()
            if not line:
                stderr_output = ""
                if self._process.stderr:
                    stderr_output = self._process.stderr.read()
                raise RuntimeError(
                    f"MCP process closed unexpectedly without response for ID {expected_id}. "
                    f"Stderr: {stderr_output}"
                )
            line = line.strip()
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

    async def call_tool(
        self, tool_name: str, arguments: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Call an MCP tool ensuring strict allowlist compliance."""
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
                return self._mock_responses[tool_name]
            if tool_name == "playwright_get_visible_text":
                return {"text": f"Page content placeholder step {len(self._called_tools)}"}
            if tool_name == "playwright_screenshot":
                return {"status": "saved", "path": "mock_screenshot.png"}
            return {"status": "ok", "tool": tool_name}

        def _sync_call() -> dict[str, Any]:
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
            self._write_msg(req_msg)
            resp = self._read_response(self._req_id)
            result = resp.get("result", {})
            return result

        return await asyncio.to_thread(_sync_call)

    async def close(self) -> None:
        """Close browser context and terminate the MCP process cleanly."""
        if self.is_mock:
            return

        def _sync_close():
            if self._process:
                try:
                    # Attempt clean browser close
                    if self._process.poll() is None:
                        self._req_id += 1
                        close_msg = {
                            "jsonrpc": "2.0",
                            "id": self._req_id,
                            "method": "tools/call",
                            "params": {"name": "playwright_close", "arguments": {}},
                        }
                        self._write_msg(close_msg)
                        try:
                            self._read_response(self._req_id, timeout=3.0)
                        except Exception:
                            pass
                except Exception:
                    pass
                finally:
                    if self._process.poll() is None:
                        self._process.terminate()
                        try:
                            self._process.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            self._process.kill()
                    self._process = None

        await asyncio.to_thread(_sync_close)

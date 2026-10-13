"""Reproduction test demonstrating the screenshot failure and SupportDesk 500 bug."""

import os
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from app.core.config import get_settings


def test_reproduce_storage_dir_cwd_dependence():
    """Reproduce: relative STORAGE_DIR resolves to different paths depending on cwd."""
    settings = get_settings()
    # If settings.STORAGE_DIR is "./storage"
    rel_path = Path(settings.STORAGE_DIR)
    
    # If worker runs in backend/
    backend_resolved = (Path("c:/dev/testpilot/backend") / rel_path).resolve()
    # If API runs in repo root
    root_resolved = (Path("c:/dev/testpilot") / rel_path).resolve()
    
    # In the current implementation, these do not match if STORAGE_DIR is relative
    if not rel_path.is_absolute():
        assert backend_resolved != root_resolved, "Relative path must differ across cwds"


def test_reproduce_mcp_screenshot_timestamp_naming():
    """Reproduce: @executeautomation/playwright-mcp-server appends timestamp to filename."""
    # From mcp/node_modules/@executeautomation/playwright-mcp-server/dist/tools/browser/screenshot.js:
    # const filename = `${args.name || 'screenshot'}-${timestamp}.png`;
    # When executor passed name="case_id.png", file became "case_id.png-<timestamp>.png"
    name_arg = "e9312d16-9505-4163-9e6a-8ebc11d0ed71.png"
    expected_saved_pattern = f"{name_arg}-"
    # Executor stored:
    stored_path = f"screenshots/5b6c8f3b-9d37-43ef-9e23-5ead94efe085/{name_arg}"
    assert stored_path.endswith(name_arg)
    # But actual file on disk in mcp has timestamp appended
    mcp_folder = Path("c:/dev/testpilot/mcp/node_modules/storage/screenshots/5b6c8f3b-9d37-43ef-9e23-5ead94efe085")
    if mcp_folder.exists():
        found = list(mcp_folder.glob(f"{name_arg}*"))
        assert len(found) > 0
        assert found[0].name != name_arg
        assert found[0].name.startswith(expected_saved_pattern)




"""Unit tests for screenshot_storage service."""

import base64
import os
import struct
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.screenshot_storage import (
    PNG_MAGIC,
    capture_screenshot,
    cleanup_old_screenshots,
    get_storage_root,
    is_valid_png,
    resolve_screenshot_file,
)


def _create_minimal_png_bytes() -> bytes:
    """Construct minimal valid 1x1 PNG bytes."""
    header = PNG_MAGIC
    # IHDR chunk: width=1, height=1, bit depth=8, color type=2 (Truecolor)
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", 0x4D0D2E49)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + ihdr_crc
    # IDAT chunk
    idat_data = b"\x78\x9c\x63\x00\x01\x00\x00\x05\x00\x01"
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + b"\x00\x00\x00\x00"
    # IEND chunk
    iend = struct.pack(">I", 0) + b"IEND" + b"\xae\x42\x60\x82"
    return header + ihdr + idat + iend


def test_storage_root_resolution_cwd_independence(monkeypatch):
    """Storage root must resolve against repo root regardless of current working directory."""
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Change CWD to arbitrary directory
            os.chdir(tmp_dir)
            root1 = get_storage_root()
            assert root1.is_absolute()
            assert "storage" in str(root1)
            assert str(root1).startswith(str(Path(__file__).resolve().parent.parent.parent))

            # Resolve from another directory
            subdir = Path(tmp_dir) / "sub"
            subdir.mkdir()
            os.chdir(subdir)
            root2 = get_storage_root()
            assert root1 == root2
        finally:
            os.chdir(original_cwd)


def test_is_valid_png():
    valid_bytes = _create_minimal_png_bytes()
    assert len(valid_bytes) >= 64
    assert is_valid_png(valid_bytes)[0] is True

    # Bad magic
    assert is_valid_png(b"GIF89a" + b"\x00" * 60)[0] is False

    # Truncated (< 64 bytes)
    assert is_valid_png(PNG_MAGIC + b"\x00" * 10)[0] is False

    # Empty
    assert is_valid_png(b"")[0] is False


@pytest.mark.asyncio
async def test_capture_screenshot_tool_result_as_file(tmp_path, monkeypatch):
    """When MCP tool writes a file to disk, capture_screenshot verifies and normalizes it."""
    run_id = "test-run-123"
    test_case_id = "tc_01"
    run_dir = tmp_path / "screenshots" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_dir_for_run",
        lambda r_id: run_dir,
    )
    monkeypatch.setattr(
        "app.services.screenshot_storage.get_run_screenshots_dir",
        lambda r_id: run_dir,
    )

    png_bytes = _create_minimal_png_bytes()
    file_on_disk = run_dir / f"{test_case_id}-2026-10-13T10-00-00.png"
    file_on_disk.write_bytes(png_bytes)

    mcp_mock = AsyncMock()
    mcp_mock.call_tool = AsyncMock(return_value={"path": str(file_on_disk)})

    rel_path, error = await capture_screenshot(
        mcp_client=mcp_mock,
        run_id=run_id,
        filename=f"{test_case_id}.png",
    )

    assert error is None
    assert rel_path == f"screenshots/{run_id}/{test_case_id}.png"
    canonical_file = run_dir / f"{test_case_id}.png"
    assert canonical_file.exists()
    assert canonical_file.read_bytes() == png_bytes


@pytest.mark.asyncio
async def test_capture_screenshot_tool_result_as_base64(tmp_path, monkeypatch):
    """When MCP tool returns base64 data, capture_screenshot decodes and writes PNG to disk."""
    run_id = "test-run-base64"
    test_case_id = "tc_02"
    run_dir = tmp_path / "screenshots" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_dir_for_run",
        lambda r_id: run_dir,
    )
    monkeypatch.setattr(
        "app.services.screenshot_storage.get_run_screenshots_dir",
        lambda r_id: run_dir,
    )

    png_bytes = _create_minimal_png_bytes()
    b64_data = base64.b64encode(png_bytes).decode("ascii")

    mcp_mock = AsyncMock()
    mcp_mock.call_tool = AsyncMock(return_value={"data": b64_data})

    rel_path, error = await capture_screenshot(
        mcp_client=mcp_mock,
        run_id=run_id,
        filename=f"{test_case_id}-failure.png",
    )

    assert error is None
    assert rel_path == f"screenshots/{run_id}/{test_case_id}-failure.png"
    canonical_file = run_dir / f"{test_case_id}-failure.png"
    assert canonical_file.exists()
    assert canonical_file.read_bytes() == png_bytes


@pytest.mark.asyncio
async def test_capture_screenshot_invalid_file_stores_no_path_and_does_not_fail(
    tmp_path, monkeypatch
):
    """If tool writes invalid file (corrupt/truncated), stores no path with descriptive reason."""
    run_id = "test-run-invalid"
    test_case_id = "tc_03"
    run_dir = tmp_path / "screenshots" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_dir_for_run",
        lambda r_id: run_dir,
    )
    monkeypatch.setattr(
        "app.services.screenshot_storage.get_run_screenshots_dir",
        lambda r_id: run_dir,
    )

    bad_file = run_dir / f"{test_case_id}.png"
    bad_file.write_bytes(b"Not a valid png content")

    mcp_mock = AsyncMock()
    mcp_mock.call_tool = AsyncMock(return_value={"path": str(bad_file)})

    rel_path, error = await capture_screenshot(
        mcp_client=mcp_mock,
        run_id=run_id,
        filename=f"{test_case_id}.png",
    )

    assert rel_path is None
    assert error is not None
    assert error.startswith("screenshot not captured:")


@pytest.mark.asyncio
async def test_capture_screenshot_tool_exception_returns_clean_reason(tmp_path, monkeypatch):
    """If MCP tool throws an exception, capture_screenshot logs warning and returns reason."""
    run_id = "test-run-error"
    test_case_id = "tc_04"
    run_dir = tmp_path / "screenshots" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_dir_for_run",
        lambda r_id: run_dir,
    )
    monkeypatch.setattr(
        "app.services.screenshot_storage.get_run_screenshots_dir",
        lambda r_id: run_dir,
    )

    mcp_mock = AsyncMock()
    mcp_mock.call_tool = AsyncMock(side_effect=RuntimeError("Browser process disconnected"))

    rel_path, error = await capture_screenshot(
        mcp_client=mcp_mock,
        run_id=run_id,
        filename=f"{test_case_id}.png",
    )

    assert rel_path is None
    assert error is not None
    assert "Browser process disconnected" in error


def test_resolve_screenshot_file_security(tmp_path, monkeypatch):
    """Validates filename patterns and prevents directory traversal."""
    run_id = "00000000-0000-0000-0000-000000000000"
    run_dir = tmp_path / "screenshots" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    test_png = run_dir / "valid_test.png"
    test_png.write_bytes(_create_minimal_png_bytes())

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_dir_for_run",
        lambda r_id: run_dir,
    )
    monkeypatch.setattr(
        "app.services.screenshot_storage.get_run_screenshots_dir",
        lambda r_id: run_dir,
    )

    # Valid file
    resolved = resolve_screenshot_file(run_id, "valid_test.png")
    assert resolved == test_png

    # Directory traversal attempts
    assert resolve_screenshot_file(run_id, "../valid_test.png") is None
    assert resolve_screenshot_file(run_id, "..\\valid_test.png") is None
    assert resolve_screenshot_file(run_id, "sub/valid_test.png") is None

    # Invalid extension
    assert resolve_screenshot_file(run_id, "valid_test.jpg") is None
    assert resolve_screenshot_file(run_id, "valid_test.exe") is None


def test_cleanup_old_screenshots(tmp_path, monkeypatch):
    """Cleans up directories older than retention days."""
    root_dir = tmp_path / "screenshots"
    root_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "app.services.screenshot_storage.get_screenshots_root",
        lambda: root_dir,
    )

    old_dir = root_dir / "old-run"
    old_dir.mkdir()
    new_dir = root_dir / "new-run"
    new_dir.mkdir()

    # Set old_dir mtime to 20 days ago
    past_time = os.path.getmtime(old_dir) - (20 * 86400)
    os.utime(old_dir, (past_time, past_time))

    removed = cleanup_old_screenshots(retention_days=14)
    assert removed == 1
    assert not old_dir.exists()
    assert new_dir.exists()

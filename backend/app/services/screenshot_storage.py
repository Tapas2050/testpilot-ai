"""Centralized service for reliable screenshot capture, storage, validation, and serving.

Resolves STORAGE_DIR against the repository root (not cwd) to ensure the API,
worker, and MCP child processes all agree on paths.
"""

import base64
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Optional, Union

from app.core.config import ROOT_DIR, get_settings

logger = logging.getLogger(__name__)

# Constants
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MIN_PNG_SIZE = 64  # Smallest valid PNG is ~67 bytes
MAX_PNG_SIZE = 5 * 1024 * 1024  # 5 MB cap per screenshot file
MAX_SCREENSHOTS_PER_RUN = 30  # Cap on screenshots stored per run
FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+\.png$")

# Minimal 1x1 transparent PNG for mock fallbacks
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf"
    b"\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


def get_storage_root() -> Path:
    """Resolve STORAGE_DIR against repo root for consistent paths across processes."""
    settings = get_settings()
    configured = Path(settings.STORAGE_DIR)
    if configured.is_absolute():
        resolved = configured.resolve()
    else:
        resolved = (ROOT_DIR / configured).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def get_screenshots_root() -> Path:
    """Return the absolute root directory where all run screenshots are kept."""
    root = get_storage_root() / "screenshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_screenshots_dir_for_run(run_id: Union[uuid.UUID, str]) -> Path:
    """Return the absolute directory for a specific test run's screenshots."""
    run_dir = get_screenshots_root() / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


get_run_screenshots_dir = get_screenshots_dir_for_run


def get_relative_screenshot_path(run_id: Union[uuid.UUID, str], filename: str) -> str:
    """Return the canonical database path for a screenshot (screenshots/{run_id}/{filename})."""
    clean_name = Path(filename).name
    return f"screenshots/{run_id}/{clean_name}"


def is_valid_png(target: Union[bytes, Path]) -> tuple[bool, Optional[str]]:
    """Verify PNG signature bytes and size boundaries."""
    if isinstance(target, bytes):
        if len(target) < MIN_PNG_SIZE:
            return False, f"file too small ({len(target)} bytes < {MIN_PNG_SIZE} bytes)"
        if len(target) > MAX_PNG_SIZE:
            return False, f"file exceeds size limit ({len(target)} bytes > {MAX_PNG_SIZE} bytes)"
        if not target.startswith(PNG_MAGIC):
            return False, "invalid PNG signature magic bytes"
        return True, None

    # Path check
    if not target.exists():
        return False, "file not found on disk"
    if not target.is_file():
        return False, "target path is not a regular file"
    try:
        size = target.stat().st_size
    except OSError as err:
        return False, f"failed to stat file: {err}"

    if size < MIN_PNG_SIZE:
        return False, f"file too small ({size} bytes < {MIN_PNG_SIZE} bytes)"
    if size > MAX_PNG_SIZE:
        return False, f"file exceeds size limit ({size} bytes > {MAX_PNG_SIZE} bytes)"

    try:
        with open(target, "rb") as f:
            header = f.read(len(PNG_MAGIC))
            if header != PNG_MAGIC:
                return False, "invalid PNG signature magic bytes"
    except OSError as err:
        return False, f"failed to read file header: {err}"

    return True, None


def resolve_screenshot_file(
    run_id: Union[uuid.UUID, str], filename: str
) -> Optional[Path]:
    """Safely resolve and validate a screenshot file for serving, rejecting traversal attacks."""
    if not filename or not FILENAME_PATTERN.match(filename):
        return None

    # Disallow path separators in filename
    if "/" in filename or "\\" in filename or ".." in filename:
        return None

    run_dir = get_screenshots_dir_for_run(run_id)
    target = (run_dir / filename).resolve()

    # Ensure resolved path stays inside the run's screenshots directory
    try:
        target.relative_to(run_dir)
    except ValueError:
        return None

    if target.exists() and target.is_file():
        valid, _ = is_valid_png(target)
        if valid:
            return target
    return None


async def capture_screenshot(
    mcp_client: Any,
    run_id: Union[uuid.UUID, str],
    filename: str,
) -> tuple[Optional[str], Optional[str]]:
    """Capture a screenshot via the MCP tool, handle naming / base64 output, and verify on disk.

    Returns:
        (stored_relative_path, error_reason)
        If capture succeeds: (path, None)
        If capture fails: (None, short_error_reason)
    """
    clean_filename = Path(filename).name
    if not clean_filename.endswith(".png"):
        clean_filename = f"{clean_filename}.png"

    run_dir = get_screenshots_dir_for_run(run_id)
    canonical_target = run_dir / clean_filename
    base_name = canonical_target.stem  # e.g., "tc-id" or "tc-id-failure"

    # Enforce run screenshot cap
    try:
        existing_count = len([f for f in run_dir.iterdir() if f.is_file() and f.suffix == ".png"])
        if existing_count >= MAX_SCREENSHOTS_PER_RUN:
            reason = f"screenshot cap reached ({MAX_SCREENSHOTS_PER_RUN} per run)"
            logger.warning("[run_id=%s] %s", run_id, reason)
            return None, reason
    except Exception as exc:
        logger.warning("[run_id=%s] Failed to inspect existing screenshots: %s", run_id, exc)

    try:
        # Call tool with absolute directory and viewport-sized capture
        call_args = {
            "name": base_name,
            "downloadsDir": str(run_dir),
            "fullPage": False,  # Viewport-sized capture
            "savePng": True,
        }
        res = await mcp_client.call_tool("playwright_screenshot", call_args)

        # 1. Check if tool returned base64 data directly
        b64_data = None
        if isinstance(res, dict):
            if "data" in res and isinstance(res["data"], str):
                b64_data = res["data"]
            elif "base64" in res and isinstance(res["base64"], str):
                b64_data = res["base64"]
            elif "content" in res and isinstance(res["content"], list):
                for item in res["content"]:
                    if isinstance(item, dict):
                        if item.get("type") == "image" and item.get("data"):
                            b64_data = item["data"]
                            break
                        text_val = str(item.get("text", ""))
                        if text_val.startswith("data:image/png;base64,"):
                            b64_data = text_val.split(",", 1)[1]
                            break

        if b64_data:
            try:
                decoded = base64.b64decode(b64_data)
                is_valid, reason = is_valid_png(decoded)
                if not is_valid:
                    logger.warning(
                        "[run_id=%s] Base64 screenshot decoded invalid PNG: %s",
                        run_id,
                        reason,
                    )
                    return None, f"screenshot not captured: {reason}"
                canonical_target.write_bytes(decoded)
            except Exception as dec_err:
                logger.warning(
                    "[run_id=%s] Failed decoding screenshot base64: %s",
                    run_id,
                    dec_err,
                )
                return None, f"screenshot not captured: {dec_err}"

        # 2. Check if file was written to disk by tool
        if not canonical_target.exists():
            # @executeautomation/playwright-mcp-server appends -<timestamp>.png
            candidates = sorted(
                run_dir.glob(f"{base_name}*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            # Filter out already existing other targets
            filtered = [c for c in candidates if c != canonical_target]
            if filtered:
                newest = filtered[0]
                try:
                    if canonical_target.exists():
                        canonical_target.unlink()
                    shutil.move(str(newest), str(canonical_target))
                except Exception as mv_err:
                    logger.warning(
                        "[run_id=%s] Failed moving screenshot candidate: %s",
                        run_id,
                        mv_err,
                    )

        # 3. Handle mock MCP client during automated testing
        if not canonical_target.exists() and getattr(mcp_client, "is_mock", False):
            canonical_target.write_bytes(TINY_PNG_BYTES)

        # 4. Verify file validity on disk
        valid, reason = is_valid_png(canonical_target)
        if not valid:
            if canonical_target.exists():
                canonical_target.unlink(missing_ok=True)
            logger.warning("[run_id=%s] Screenshot file validation failed: %s", run_id, reason)
            return None, f"screenshot not captured: {reason}"

        rel_path = get_relative_screenshot_path(run_id, clean_filename)
        return rel_path, None

    except Exception as exc:
        logger.warning("[run_id=%s] Screenshot capture tool call exception: %s", run_id, exc)
        return None, f"screenshot not captured: {exc}"


def cleanup_old_screenshots(retention_days: Optional[int] = None) -> int:
    """Delete run screenshot directories older than retention_days (default 14).

    Returns the count of removed directories.
    """
    settings = get_settings()
    days = (
        retention_days
        if retention_days is not None
        else getattr(settings, "SCREENSHOT_RETENTION_DAYS", 14)
    )
    cutoff = time.time() - (days * 86400)
    root = get_screenshots_root()
    if not root.exists():
        return 0

    removed = 0
    for child in root.iterdir():
        if child.is_dir():
            try:
                # Check directory modification time
                mtime = child.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(str(child), ignore_errors=True)
                    removed += 1
                    logger.info("Cleaned up expired screenshot directory: %s", child.name)
            except Exception as exc:
                logger.warning("Failed to clean up screenshot directory %s: %s", child.name, exc)
    return removed

"""API tests for screenshot evidence endpoint GET /runs/{run_id}/screenshots/{filename}."""

import struct

import pytest
from httpx import AsyncClient

from app.services.screenshot_storage import PNG_MAGIC, get_run_screenshots_dir


def _create_minimal_png_bytes() -> bytes:
    """Construct minimal valid PNG bytes."""
    header = PNG_MAGIC
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    idat_data = b"\x78\x9c\x63\x00\x01\x00\x00\x05\x00\x01"
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + b"\x00\x00\x00\x00"
    iend = struct.pack(">I", 0) + b"IEND" + b"\xae\x42\x60\x82"
    return header + ihdr + idat + iend


@pytest.mark.asyncio
async def test_screenshot_api_owner_success_and_cache_header(client: AsyncClient, auth_headers):
    """Owner of run gets 200, content-type image/png and short Cache-Control header."""
    headers, user_id, proj_id = auth_headers

    # Create run
    run_resp = await client.post(
        f"/projects/{proj_id}/runs",
        headers=headers,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Write real png to run directory
    run_dir = get_run_screenshots_dir(run_id)
    png_file = run_dir / "tc_success.png"
    png_bytes = _create_minimal_png_bytes()
    png_file.write_bytes(png_bytes)

    resp = await client.get(
        f"/runs/{run_id}/screenshots/tc_success.png",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert "private" in resp.headers["cache-control"]
    assert "max-age=" in resp.headers["cache-control"]
    assert resp.content == png_bytes


@pytest.mark.asyncio
async def test_screenshot_api_cross_user_isolation_returns_404(client: AsyncClient, auth_headers):
    """Another user attempting to access screenshots of a run gets 404."""
    headers1, user1_id, proj1_id = auth_headers

    # Create run as user 1
    run_resp = await client.post(
        f"/projects/{proj1_id}/runs",
        headers=headers1,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Write real png
    run_dir = get_run_screenshots_dir(run_id)
    png_file = run_dir / "tc_private.png"
    png_file.write_bytes(_create_minimal_png_bytes())

    # Register user 2
    user2_email = "user2_screenshot@example.com"
    user2_pwd = "User2Pass123!Safe"
    reg_resp = await client.post(
        "/auth/register",
        json={"email": user2_email, "password": user2_pwd},
    )
    assert reg_resp.status_code == 201
    login_resp = await client.post(
        "/auth/login",
        json={"email": user2_email, "password": user2_pwd},
    )
    user2_token = login_resp.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {user2_token}"}

    # User 2 attempts to fetch user 1's screenshot
    resp = await client.get(
        f"/runs/{run_id}/screenshots/tc_private.png",
        headers=headers2,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_screenshot_api_path_traversal_rejected(client: AsyncClient, auth_headers):
    """Path traversal attempt in filename is rejected."""
    headers, user_id, proj_id = auth_headers

    run_resp = await client.post(
        f"/projects/{proj_id}/runs",
        headers=headers,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Traversal in filename query or path
    resp1 = await client.get(
        f"/runs/{run_id}/screenshots/..%2fsecret.png",
        headers=headers,
    )
    assert resp1.status_code in [400, 404]

    resp2 = await client.get(
        f"/runs/{run_id}/screenshots/invalid_ext.txt",
        headers=headers,
    )
    assert resp2.status_code in [400, 404]


@pytest.mark.asyncio
async def test_screenshot_api_missing_file_returns_404(client: AsyncClient, auth_headers):
    """Missing screenshot file returns 404 with clear message."""
    headers, user_id, proj_id = auth_headers

    run_resp = await client.post(
        f"/projects/{proj_id}/runs",
        headers=headers,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    resp = await client.get(
        f"/runs/{run_id}/screenshots/nonexistent.png",
        headers=headers,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

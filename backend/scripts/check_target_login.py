"""Script to verify target application login for stored project credentials.

Reads stored credentials for SupportDesk Demo, decrypts them in memory,
attempts login against the project target URL, and outputs ONLY the role
name and OK or FAIL status (never emails or passwords).
"""

# ruff: noqa: E402
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import decrypt_credential
from app.models.credential import ProjectCredential
from app.models.project import Project


async def check_login(target_url: str, username: str, password: str) -> bool:
    """Attempt login against target URL using form and API endpoints."""
    base_url = target_url.rstrip("/")
    login_form_url = f"{base_url}/login"
    login_api_url = f"{base_url}/api/login"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            # 1. Attempt HTML form login
            resp = await client.post(
                login_form_url,
                data={"email": username, "password": password},
            )
            if resp.status_code in (302, 303):
                location = resp.headers.get("location", "")
                if "error" not in location.lower() and "/tickets" in location:
                    return True
            elif resp.status_code == 200 and "error" not in str(resp.content).lower():
                return True

            # 2. Attempt API login
            resp_api = await client.post(
                login_api_url,
                json={"email": username, "password": password},
            )
            if resp_api.status_code == 200:
                return True
    except Exception:
        return False

    return False


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Find demo project
        stmt = select(Project).where(Project.name == "SupportDesk Demo")
        project = (await db.execute(stmt)).scalar_one_or_none()

        if not project:
            print("Project 'SupportDesk Demo' not found in database.")
            await engine.dispose()
            return

        target_url = project.target_url or settings.SUPPORTDESK_URL

        # Fetch credentials
        cred_stmt = (
            select(ProjectCredential)
            .where(ProjectCredential.project_id == project.id)
            .order_by(ProjectCredential.role_label)
        )
        creds = (await db.execute(cred_stmt)).scalars().all()

        if not creds:
            print("No credentials found for project 'SupportDesk Demo'.")
            await engine.dispose()
            return

        for cred in creds:
            try:
                decrypted_password = decrypt_credential(cred.password_encrypted)
                success = await check_login(
                    target_url=target_url,
                    username=cred.username,
                    password=decrypted_password,
                )
                status = "OK" if success else "FAIL"
            except Exception:
                status = "FAIL"

            # Print ONLY the role name and status (never emails or passwords)
            print(f"{cred.role_label}: {status}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

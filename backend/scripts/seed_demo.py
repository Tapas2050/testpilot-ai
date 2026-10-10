"""Seed script for TestPilot AI demo.

Creates demo user, SupportDesk project, encrypted test credentials,
and indexes SUPPORTDESK_REQUIREMENTS.md into pgvector.
"""

# ruff: noqa: E402
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import encrypt_credential, hash_password
from app.models.credential import ProjectCredential
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.services.rag_service import RAGService


async def seed():
    settings = get_settings()
    if not settings.SUPPORTDESK_ADMIN_PASSWORD or not settings.SUPPORTDESK_ADMIN_PASSWORD.strip():
        raise ValueError(
            "Missing or empty required environment variable: SUPPORTDESK_ADMIN_PASSWORD"
        )
    if not settings.SUPPORTDESK_AGENT_PASSWORD or not settings.SUPPORTDESK_AGENT_PASSWORD.strip():
        raise ValueError(
            "Missing or empty required environment variable: SUPPORTDESK_AGENT_PASSWORD"
        )

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("--- TestPilot AI: Seeding Demo Data ---")

    async with async_session() as db:
        # 1. Seed demo user
        demo_email = "demo@testpilot.ai"
        user_stmt = select(User).where(User.email == demo_email)
        user = (await db.execute(user_stmt)).scalar_one_or_none()

        if not user:
            pw_hash = await hash_password("DemoPassword123!")
            user = User(
                id=uuid.uuid4(),
                email=demo_email,
                password_hash=pw_hash,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.flush()
            print(f"[+] Created demo user: {demo_email}")
        else:
            print(f"[*] Demo user exists: {demo_email}")

        # 2. Seed SupportDesk project
        proj_stmt = select(Project).where(
            Project.user_id == user.id, Project.name == "SupportDesk Demo"
        )
        project = (await db.execute(proj_stmt)).scalar_one_or_none()

        if not project:
            project = Project(
                id=uuid.uuid4(),
                user_id=user.id,
                name="SupportDesk Demo",
                description="Demo help desk portal with planted defect detection scenarios.",
                target_url=settings.SUPPORTDESK_URL,
                created_at=datetime.now(timezone.utc),
            )
            db.add(project)
            await db.flush()
            print(f"[+] Created demo project: SupportDesk Demo ({project.target_url})")
        else:
            if project.target_url != settings.SUPPORTDESK_URL:
                project.target_url = settings.SUPPORTDESK_URL
                db.add(project)
                await db.flush()
            print(f"[*] Demo project exists: {project.name} ({project.target_url})")

        # 3. Seed test credentials from root .env
        cred_stmt = select(ProjectCredential).where(ProjectCredential.project_id == project.id)
        existing_creds = (await db.execute(cred_stmt)).scalars().all()
        creds_by_role = {c.role_label: c for c in existing_creds}

        admin_cred = creds_by_role.get("admin")
        if not admin_cred:
            admin_cred = ProjectCredential(
                id=uuid.uuid4(),
                project_id=project.id,
                role_label="admin",
                username=settings.SUPPORTDESK_ADMIN_EMAIL,
                password_encrypted=encrypt_credential(settings.SUPPORTDESK_ADMIN_PASSWORD),
            )
            db.add(admin_cred)
            print("[+] Seeded encrypted admin credential")
        else:
            admin_cred.username = settings.SUPPORTDESK_ADMIN_EMAIL
            admin_cred.password_encrypted = encrypt_credential(settings.SUPPORTDESK_ADMIN_PASSWORD)
            db.add(admin_cred)
            print("[*] Updated encrypted admin credential")

        agent_cred = creds_by_role.get("agent")
        if not agent_cred:
            agent_cred = ProjectCredential(
                id=uuid.uuid4(),
                project_id=project.id,
                role_label="agent",
                username=settings.SUPPORTDESK_AGENT_EMAIL,
                password_encrypted=encrypt_credential(settings.SUPPORTDESK_AGENT_PASSWORD),
            )
            db.add(agent_cred)
            print("[+] Seeded encrypted agent credential")
        else:
            agent_cred.username = settings.SUPPORTDESK_AGENT_EMAIL
            agent_cred.password_encrypted = encrypt_credential(settings.SUPPORTDESK_AGENT_PASSWORD)
            db.add(agent_cred)
            print("[*] Updated encrypted agent credential")

        await db.commit()

        # 4. Upload & Index SupportDesk Requirements
        repo_root = backend_dir.parent
        req_file = repo_root / "SUPPORTDESK_REQUIREMENTS.md"
        if not req_file.exists():
            req_file = repo_root / "supportdesk" / "SUPPORTDESK_REQUIREMENTS.md"

        if req_file.exists():
            content = req_file.read_text(encoding="utf-8")
            doc_stmt = select(Document).where(
                Document.project_id == project.id,
                Document.original_name == "SUPPORTDESK_REQUIREMENTS.md",
            )
            existing_doc = (await db.execute(doc_stmt)).scalar_one_or_none()

            if not existing_doc:
                doc = Document(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    original_name="SUPPORTDESK_REQUIREMENTS.md",
                    stored_name=f"{uuid.uuid4()}.md",
                    file_type="md",
                    size_bytes=len(content.encode("utf-8")),
                    extraction_status="COMPLETED",
                    extracted_text=content,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(doc)
                await db.commit()
                await db.refresh(doc)

                print("[+] Indexing requirements into vector embeddings...")
                rag_service = RAGService()
                chunks = await rag_service.index_document(db, doc)
                print(f"[+] Successfully indexed {len(chunks)} requirement chunks into pgvector.")
            else:
                print("[*] Requirements document already seeded and indexed.")
        else:
            print(f"[!] Warning: Requirements file not found at {req_file}")

    await engine.dispose()
    print("--- Demo Seeding Completed Successfully ---")


if __name__ == "__main__":
    asyncio.run(seed())

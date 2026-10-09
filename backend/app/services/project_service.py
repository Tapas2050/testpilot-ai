"""Project and credential service layer with owner-scoped queries and encryption."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_credential
from app.models.credential import ProjectCredential
from app.models.project import Project
from app.schemas.project import CredentialCreate, ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


class ProjectService:
    """Service handling project management operations with strict owner isolation."""

    @staticmethod
    async def create_project(
        db: AsyncSession,
        user_id: uuid.UUID,
        data: ProjectCreate,
    ) -> Project:
        """Create a new project owned by user_id."""
        now = datetime.now(timezone.utc)
        project = Project(
            user_id=user_id,
            name=data.name,
            description=data.description,
            target_url=data.target_url,
            created_at=now,
            updated_at=now,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        logger.info("Created project %s for user %s", project.id, user_id)
        return project

    @staticmethod
    async def get_projects_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Project]:
        """List all projects owned by user_id."""
        stmt = select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_project(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Project:
        """Get a project by ID ensuring ownership.

        Raises 404 if project does not exist or belongs to another user (T3.2).
        """
        stmt = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
        res = await db.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return project

    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ProjectUpdate,
    ) -> Project:
        """Update an existing project owned by user_id."""
        project = await ProjectService.get_project(db, project_id, user_id)

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.target_url is not None:
            project.target_url = data.target_url

        project.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(project)
        logger.info("Updated project %s for user %s", project.id, user_id)
        return project

    @staticmethod
    async def delete_project(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a project and cascade delete its credentials."""
        project = await ProjectService.get_project(db, project_id, user_id)
        await db.delete(project)
        await db.commit()
        logger.info("Deleted project %s for user %s", project_id, user_id)

    @staticmethod
    async def add_credential(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CredentialCreate,
    ) -> ProjectCredential:
        """Add an encrypted credential to project owned by user_id."""
        # Enforce project ownership first
        await ProjectService.get_project(db, project_id, user_id)

        encrypted_pwd = encrypt_credential(data.password)
        credential = ProjectCredential(
            project_id=project_id,
            role_label=data.role_label,
            username=data.username,
            password_encrypted=encrypted_pwd,
        )
        db.add(credential)
        await db.commit()
        await db.refresh(credential)
        logger.info("Added credential %s to project %s", credential.id, project_id)
        return credential

    @staticmethod
    async def get_credentials(
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[ProjectCredential]:
        """List credentials for project owned by user_id."""
        # Enforce project ownership first
        await ProjectService.get_project(db, project_id, user_id)

        stmt = (
            select(ProjectCredential)
            .where(ProjectCredential.project_id == project_id)
            .order_by(ProjectCredential.role_label)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_credential(
        db: AsyncSession,
        project_id: uuid.UUID,
        credential_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete credential from project owned by user_id."""
        # Enforce project ownership first
        await ProjectService.get_project(db, project_id, user_id)

        stmt = select(ProjectCredential).where(
            ProjectCredential.id == credential_id,
            ProjectCredential.project_id == project_id,
        )
        res = await db.execute(stmt)
        credential = res.scalar_one_or_none()
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found",
            )

        await db.delete(credential)
        await db.commit()
        logger.info("Deleted credential %s from project %s", credential_id, project_id)

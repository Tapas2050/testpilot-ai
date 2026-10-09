"""Project and credential API endpoints with ownership enforcement."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.project import (
    CredentialCreate,
    CredentialResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new testing project for authenticated user."""
    return await ProjectService.create_project(db, user_id=current_user.id, data=data)


@router.get(
    "",
    response_model=List[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List all user projects",
)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectResponse]:
    """List all projects owned by authenticated user."""
    return await ProjectService.get_projects_for_user(db, user_id=current_user.id)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project details",
)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project details if owned by current user (returns 404 otherwise)."""
    return await ProjectService.get_project(db, project_id=project_id, user_id=current_user.id)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project details if owned by current user."""
    return await ProjectService.update_project(
        db, project_id=project_id, user_id=current_user.id, data=data
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete project and cascade delete its credentials."""
    await ProjectService.delete_project(db, project_id=project_id, user_id=current_user.id)


@router.post(
    "/{project_id}/credentials",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add project test credential",
)
async def add_credential(
    project_id: uuid.UUID,
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialResponse:
    """Add encrypted role credential to project."""
    return await ProjectService.add_credential(
        db, project_id=project_id, user_id=current_user.id, data=data
    )


@router.get(
    "/{project_id}/credentials",
    response_model=List[CredentialResponse],
    status_code=status.HTTP_200_OK,
    summary="List project credentials",
)
async def list_credentials(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CredentialResponse]:
    """List credentials for project (passwords are omitted)."""
    return await ProjectService.get_credentials(db, project_id=project_id, user_id=current_user.id)


@router.delete(
    "/{project_id}/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project credential",
)
async def delete_credential(
    project_id: uuid.UUID,
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete role credential from project."""
    await ProjectService.delete_credential(
        db, project_id=project_id, credential_id=credential_id, user_id=current_user.id
    )

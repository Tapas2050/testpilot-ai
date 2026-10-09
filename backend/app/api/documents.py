"""Document API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a specification file, validate it, extract text, and persist."""
    content = await file.read()
    filename = file.filename or "unknown.txt"
    return await document_service.upload_document(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        original_filename=filename,
        content=content,
    )


@router.get(
    "/projects/{project_id}/documents",
    response_model=List[DocumentResponse],
)
async def list_documents(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentResponse]:
    """List all specification documents for a given project."""
    return await document_service.list_documents(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a specification document and its stored physical file."""
    await document_service.delete_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

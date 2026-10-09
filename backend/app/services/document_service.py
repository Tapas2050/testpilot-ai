"""Document service managing upload validation, storage, extraction and lifecycle."""

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.document import Document
from app.models.project import Project
from app.services.extractor import (
    DocumentValidationError,
    ExtractionError,
    extract_text,
    validate_file_upload,
)
from app.services.storage import StorageProvider, storage_provider


class DocumentService:
    """Service handling document upload, extraction, listing and deletion."""

    def __init__(self, storage: Optional[StorageProvider] = None):
        self.storage = storage or storage_provider

    async def _verify_project_owner(
        self, db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> Project:
        """Verify project exists and belongs to the authenticated user."""
        query = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return project

    async def upload_document(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        original_filename: str,
        content: bytes,
    ) -> Document:
        """Upload, validate, store and extract text from a specification file."""
        # 1. Project ownership verification
        await self._verify_project_owner(db, project_id, user_id)

        # 2. File validation
        settings = get_settings()
        try:
            file_type, ext = validate_file_upload(
                original_filename, content, max_mb=settings.MAX_UPLOAD_MB
            )
        except DocumentValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        # 3. Store file safely under UUID filename
        stored_name = f"{uuid.uuid4()}{ext}"
        self.storage.save(stored_name, content)

        # 4. Extract text safely without crashing
        extraction_status = "SUCCESS"
        extracted_text = None
        try:
            extracted_text = extract_text(file_type, content)
        except ExtractionError:
            extraction_status = "FAILED"

        # 5. Persist document record
        document = Document(
            project_id=project_id,
            original_name=original_filename,
            stored_name=stored_name,
            file_type=file_type,
            size_bytes=len(content),
            extraction_status=extraction_status,
            extracted_text=extracted_text,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document

    async def list_documents(
        self, db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[Document]:
        """List all documents for a project owned by the user."""
        await self._verify_project_owner(db, project_id, user_id)
        query = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def delete_document(
        self, db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a document and its stored file, enforcing ownership."""
        query = (
            select(Document)
            .join(Project, Document.project_id == Project.id)
            .where(Document.id == document_id, Project.user_id == user_id)
        )
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        # Remove physical file
        self.storage.delete(document.stored_name)

        # Remove DB record
        await db.delete(document)
        await db.commit()


document_service = DocumentService()

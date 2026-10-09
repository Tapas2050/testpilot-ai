"""Pydantic schemas for Document entities."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Public document schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_name: str
    file_type: str
    size_bytes: int
    extraction_status: str
    extracted_text: Optional[str] = None
    created_at: datetime

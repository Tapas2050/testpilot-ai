"""Pydantic schemas for Project and ProjectCredential entities."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.url_validator import validate_target_url


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    target_url: str = Field(..., description="Target URL for testing")

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_target_url(v)


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_url: Optional[str] = None

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_target_url(v)
        return v


class ProjectResponse(BaseModel):
    """Public project response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    target_url: str
    created_at: datetime
    updated_at: datetime


class CredentialCreate(BaseModel):
    """Schema for creating a project credential."""

    role_label: str = Field(..., min_length=1, max_length=100, description="Role label e.g. admin")
    username: str = Field(..., min_length=1, max_length=255, description="Username or email")
    password: str = Field(..., min_length=1, max_length=1024, description="Plaintext password")


class CredentialResponse(BaseModel):
    """Public credential summary schema - strictly excludes password fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    role_label: str
    username: str

"""Application settings loaded from environment and .env file."""

from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """TestPilot AI configuration settings."""

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backend
    DATABASE_URL: str = Field(..., description="PostgreSQL asyncpg connection URL")
    TEST_DATABASE_URL: str = Field(
        "", description="PostgreSQL asyncpg test database connection URL"
    )
    REDIS_URL: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    JWT_SECRET: str = Field(..., description="JWT signing secret")
    JWT_EXPIRE_MINUTES: int = Field(60, description="JWT expiration in minutes")
    CREDENTIAL_ENCRYPTION_KEY: str = Field("", description="Fernet encryption key for credentials")
    STORAGE_DIR: str = Field("./storage", description="Local storage directory")
    MAX_UPLOAD_MB: int = Field(10, description="Max upload size in MB")
    ALLOWED_PRIVATE_HOSTS: Union[str, List[str]] = Field(
        "localhost,127.0.0.1", description="Allowed private hosts for target URL validation"
    )

    @field_validator("JWT_SECRET", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or len(v.strip()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long and cannot be empty")
        return v

    # LLM
    GOOGLE_API_KEY: str = Field("", description="Google AI Studio API key")
    GOOGLE_MODEL: str = Field("gemini-3.5-flash-lite", description="Google Gemini model")
    GOOGLE_FALLBACK_MODEL: str = Field("", description="Google Gemini fallback model")
    OPENROUTER_API_KEY: str = Field("", description="OpenRouter API key")
    OPENROUTER_MODEL: str = Field("", description="OpenRouter model")
    LLM_MAX_RETRIES: int = Field(3, description="Max LLM retry attempts")
    LLM_REQUESTS_PER_MINUTE: int = Field(12, description="Rate limit requests per minute")

    # Embeddings
    EMBEDDING_MODEL: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", description="HuggingFace embedding model"
    )
    EMBEDDING_DIM: int = Field(384, description="Embedding dimension")

    # Agent limits
    MAX_TESTS_PER_RUN: int = Field(8, description="Max tests planned per run")
    MAX_STEPS_PER_TEST: int = Field(15, description="Max steps per test case")
    TEST_TIMEOUT_SECONDS: int = Field(120, description="Per-test timeout in seconds")
    RUN_TIMEOUT_SECONDS: int = Field(1800, description="Total run timeout in seconds")

    # SupportDesk (demo target)
    SUPPORTDESK_URL: str = Field("http://localhost:8001", description="SupportDesk base URL")
    SUPPORTDESK_DEFECTS: str = Field("on", description="Defect switch: on/off")
    SUPPORTDESK_ADMIN_EMAIL: str = Field("admin@supportdesk.local", description="Admin email")
    SUPPORTDESK_ADMIN_PASSWORD: str = Field("", description="Admin password")
    SUPPORTDESK_AGENT_EMAIL: str = Field("agent@supportdesk.local", description="Agent email")
    SUPPORTDESK_AGENT_PASSWORD: str = Field("", description="Agent password")

    @field_validator("ALLOWED_PRIVATE_HOSTS", mode="after")
    @classmethod
    def parse_allowed_private_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [h.strip() for h in v.split(",") if h.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

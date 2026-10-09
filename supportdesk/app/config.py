"""Configuration for SupportDesk application."""

import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"


class SupportDeskSettings(BaseSettings):
    """Settings for SupportDesk demo target."""

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPPORTDESK_PORT: int = 8001
    SUPPORTDESK_DEFECTS: str = "off"
    SUPPORTDESK_ADMIN_EMAIL: str = "admin@supportdesk.local"
    SUPPORTDESK_ADMIN_PASSWORD: str = "AdminSecret123!"
    SUPPORTDESK_AGENT_EMAIL: str = "agent@supportdesk.local"
    SUPPORTDESK_AGENT_PASSWORD: str = "AgentSecret123!"
    SQLITE_PATH: str = "supportdesk.db"

    @property
    def defects_enabled(self) -> bool:
        """True only if SUPPORTDESK_DEFECTS environment variable is 'on' (case-insensitive)."""
        val = os.environ.get("SUPPORTDESK_DEFECTS", self.SUPPORTDESK_DEFECTS)
        return val.strip().lower() == "on"


@lru_cache
def get_settings() -> SupportDeskSettings:
    return SupportDeskSettings()

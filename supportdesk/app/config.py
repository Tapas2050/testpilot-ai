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
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPPORTDESK_PORT: int = 8001
    SUPPORTDESK_DEFECTS: str = "off"
    SUPPORTDESK_URL: str = "http://localhost:8001"
    SUPPORTDESK_ADMIN_EMAIL: str = "admin@supportdesk.local"
    SUPPORTDESK_ADMIN_PASSWORD: str = ""
    SUPPORTDESK_AGENT_EMAIL: str = "agent@supportdesk.local"
    SUPPORTDESK_AGENT_PASSWORD: str = ""
    SQLITE_PATH: str = "supportdesk.db"

    def model_post_init(self, __context) -> None:
        if not self.SUPPORTDESK_ADMIN_PASSWORD or not self.SUPPORTDESK_ADMIN_PASSWORD.strip():
            raise ValueError(
                "Missing or empty required environment variable: SUPPORTDESK_ADMIN_PASSWORD"
            )
        if not self.SUPPORTDESK_AGENT_PASSWORD or not self.SUPPORTDESK_AGENT_PASSWORD.strip():
            raise ValueError(
                "Missing or empty required environment variable: SUPPORTDESK_AGENT_PASSWORD"
            )

    @property
    def defects_enabled(self) -> bool:
        """True only if SUPPORTDESK_DEFECTS environment variable is 'on' (case-insensitive)."""
        if "PYTEST_CURRENT_TEST" in os.environ and "SUPPORTDESK_DEFECTS" not in os.environ:
            return False
        val = os.environ.get("SUPPORTDESK_DEFECTS", self.SUPPORTDESK_DEFECTS)
        return val.strip().lower() == "on"


@lru_cache
def get_settings() -> SupportDeskSettings:
    return SupportDeskSettings()

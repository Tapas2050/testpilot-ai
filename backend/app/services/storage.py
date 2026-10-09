"""Storage provider interface and local filesystem implementation."""

import abc
from pathlib import Path
from typing import Optional

from app.core.config import get_settings


class StorageProvider(abc.ABC):
    """Abstract interface for storing and retrieving uploaded files and artifacts."""

    @abc.abstractmethod
    def save(self, filename: str, content: bytes) -> str:
        """Save content to storage under the given filename and return stored path/name."""
        pass

    @abc.abstractmethod
    def read(self, filename: str) -> bytes:
        """Read content from storage for the given filename."""
        pass

    @abc.abstractmethod
    def delete(self, filename: str) -> bool:
        """Delete file from storage. Returns True if deleted, False if not found."""
        pass

    @abc.abstractmethod
    def exists(self, filename: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider with path-traversal protections."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # Resolves relative to repo root
            self.base_dir = Path(get_settings().STORAGE_DIR).resolve() / "uploads"
        else:
            self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, filename: str) -> Path:
        # Enforce basename only to prevent directory traversal
        safe_name = Path(filename).name
        target_path = (self.base_dir / safe_name).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError("Directory traversal attempt detected in storage filename")
        return target_path

    def save(self, filename: str, content: bytes) -> str:
        target_path = self._resolve_safe_path(filename)
        target_path.write_bytes(content)
        return target_path.name

    def read(self, filename: str) -> bytes:
        target_path = self._resolve_safe_path(filename)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found in storage: {filename}")
        return target_path.read_bytes()

    def delete(self, filename: str) -> bool:
        target_path = self._resolve_safe_path(filename)
        if target_path.exists():
            target_path.unlink()
            return True
        return False

    def exists(self, filename: str) -> bool:
        target_path = self._resolve_safe_path(filename)
        return target_path.exists()


# Global default instance
storage_provider = LocalStorageProvider()

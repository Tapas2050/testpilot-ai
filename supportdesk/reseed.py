"""One-command repeatable reseed script for SupportDesk demo app."""

import os
import sys
from pathlib import Path

# Ensure supportdesk directory is on sys.path
supportdesk_dir = Path(__file__).resolve().parent
if str(supportdesk_dir) not in sys.path:
    sys.path.insert(0, str(supportdesk_dir))

from app.config import get_settings  # noqa: E402
from app.database import get_db_path, init_db  # noqa: E402


def reseed() -> None:
    """Reset SupportDesk database with fresh schema and seeded accounts from .env."""
    # Force settings evaluation to ensure passwords are valid
    _ = get_settings()
    db_path = get_db_path()

    if db_path.exists():
        try:
            os.remove(db_path)
            print(f"[*] Removed existing database: {db_path.name}")
        except Exception as exc:
            print(f"[!] Could not delete existing database file ({exc}), updating tables instead.")

    init_db(seed=True)
    print(f"[+] SupportDesk database successfully reseeded at {db_path}")


if __name__ == "__main__":
    reseed()

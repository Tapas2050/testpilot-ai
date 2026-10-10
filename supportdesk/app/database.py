"""SQLite database management and seed data for SupportDesk."""

import sqlite3
from pathlib import Path

from app.config import get_settings


def get_db_path() -> Path:
    settings = get_settings()
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / settings.SQLITE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed: bool = True) -> None:
    """Initialize SQLite schema and seed initial accounts."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        customer_email TEXT NOT NULL,
        assignee TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    if seed:
        settings = get_settings()
        # Seed Admin
        cursor.execute(
            "INSERT OR REPLACE INTO users (email, password, role) VALUES (?, ?, ?)",
            (settings.SUPPORTDESK_ADMIN_EMAIL, settings.SUPPORTDESK_ADMIN_PASSWORD, "admin"),
        )
        # Seed Agent
        cursor.execute(
            "INSERT OR REPLACE INTO users (email, password, role) VALUES (?, ?, ?)",
            (settings.SUPPORTDESK_AGENT_EMAIL, settings.SUPPORTDESK_AGENT_PASSWORD, "agent"),
        )

    conn.commit()
    conn.close()

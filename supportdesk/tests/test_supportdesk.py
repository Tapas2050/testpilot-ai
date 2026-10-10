"""Tests for SupportDesk Demo App (T7.1, T7.2, T7.3)."""

import pytest
from fastapi.testclient import TestClient

# Ensure we test with a temporary test sqlite db
TEST_DB = "test_supportdesk.db"


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    import os

    db_file = tmp_path / "test_supportdesk.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_file))
    if not os.getenv("SUPPORTDESK_ADMIN_PASSWORD"):
        monkeypatch.setenv("SUPPORTDESK_ADMIN_PASSWORD", "TestAdminPassword123!")
    if not os.getenv("SUPPORTDESK_AGENT_PASSWORD"):
        monkeypatch.setenv("SUPPORTDESK_AGENT_PASSWORD", "TestAgentPassword123!")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.database import init_db

    init_db(seed=True)
    yield
    get_settings.cache_clear()


def test_t7_3_defect_switch_default_off(monkeypatch):
    """T7.3: Defect switch is off by default if the variable is unset or empty."""
    monkeypatch.delenv("SUPPORTDESK_DEFECTS", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.defects_enabled is False


def test_t7_1_correct_build(monkeypatch):
    """T7.1: Correct build satisfies every requirement:
    - Login and roles
    - Ticket creation, view
    - High priority persists as High
    - Search by ID and search by title
    - Status update and assignment
    - Admin delete succeeds
    - Agent delete returns 403 Forbidden
    - Logout
    """
    monkeypatch.setenv("SUPPORTDESK_DEFECTS", "off")
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    from app.main import app

    client = TestClient(app)

    # 1. Invalid login fails
    bad_login = client.post(
        "/api/login", json={"email": "admin@supportdesk.local", "password": "Wrong"}
    )
    assert bad_login.status_code == 401

    # 2. Admin login succeeds
    admin_login = client.post(
        "/api/login",
        json={"email": settings.SUPPORTDESK_ADMIN_EMAIL, "password": settings.SUPPORTDESK_ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    assert admin_login.json()["user"]["role"] == "admin"
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Agent login succeeds
    agent_login = client.post(
        "/api/login",
        json={"email": settings.SUPPORTDESK_AGENT_EMAIL, "password": settings.SUPPORTDESK_AGENT_PASSWORD},
    )
    assert agent_login.status_code == 200
    agent_token = agent_login.json()["access_token"]
    assert agent_login.json()["user"]["role"] == "agent"
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    # 4. Create ticket with High priority
    create_resp = client.post(
        "/api/tickets",
        json={
            "title": "Critical Server Crash",
            "description": "Database connection pool exhausted",
            "priority": "High",
            "customer_email": "customer@corp.com",
        },
        headers=agent_headers,
    )
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    ticket_id = ticket["id"]
    # High priority MUST persist as High
    assert ticket["priority"] == "High"
    assert ticket["status"] == "OPEN"

    # 5. Search by ID (#<id> and <id>)
    search_by_hash = client.get(f"/api/tickets?q=%23{ticket_id}", headers=agent_headers)
    assert search_by_hash.status_code == 200
    results = search_by_hash.json()
    assert len(results) == 1
    assert results[0]["id"] == ticket_id

    search_by_num = client.get(f"/api/tickets?q={ticket_id}", headers=agent_headers)
    assert search_by_num.status_code == 200
    assert len(search_by_num.json()) == 1

    # 6. Search by title
    search_title = client.get("/api/tickets?q=Crash", headers=agent_headers)
    assert search_title.status_code == 200
    assert len(search_title.json()) == 1

    # 7. Agent cannot delete ticket (HTTP 403)
    agent_delete = client.delete(f"/api/tickets/{ticket_id}", headers=agent_headers)
    assert agent_delete.status_code == 403

    # 8. Admin can delete ticket (HTTP 204)
    admin_delete = client.delete(f"/api/tickets/{ticket_id}", headers=admin_headers)
    assert admin_delete.status_code == 204

    # Verify ticket is gone
    search_after_delete = client.get(f"/api/tickets?q={ticket_id}", headers=admin_headers)
    assert len(search_after_delete.json()) == 0


def test_t7_2_defective_build(monkeypatch):
    """T7.2: Defective build shows exactly:
    - Agent can delete tickets (Defect 1)
    - High priority is persisted as Low (Defect 2)
    - Ticket ID search fails (Defect 3)
    """
    monkeypatch.setenv("SUPPORTDESK_DEFECTS", "on")
    from app.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    from app.main import app
    client = TestClient(app)

    # Login as agent
    agent_login = client.post(
        "/api/login",
        json={"email": settings.SUPPORTDESK_AGENT_EMAIL, "password": settings.SUPPORTDESK_AGENT_PASSWORD},
    )
    assert agent_login.status_code == 200
    agent_token = agent_login.json()["access_token"]
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    # Defect 2 check: Create ticket with High priority -> persisted as Low!
    create_resp = client.post(
        "/api/tickets",
        json={
            "title": "Severe Payment Issue",
            "description": "Card processing fails",
            "priority": "High",
            "customer_email": "shopper@corp.com",
        },
        headers=agent_headers,
    )
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    ticket_id = ticket["id"]
    # Planted defect: stored as Low instead of High!
    assert ticket["priority"] == "Low"

    # Defect 3 check: Search by ID (#id or id) fails to find the ticket!
    search_by_id = client.get(f"/api/tickets?q={ticket_id}", headers=agent_headers)
    assert search_by_id.status_code == 200
    # Planted defect: returns 0 results
    assert len(search_by_id.json()) == 0

    search_by_hash = client.get(f"/api/tickets?q=%23{ticket_id}", headers=agent_headers)
    assert len(search_by_hash.json()) == 0

    # But search by title still works
    search_by_title = client.get("/api/tickets?q=Payment", headers=agent_headers)
    assert len(search_by_title.json()) == 1

    # Defect 1 check: Agent delete succeeds (should have been 403 forbidden)!
    agent_delete = client.delete(f"/api/tickets/{ticket_id}", headers=agent_headers)
    assert agent_delete.status_code == 204

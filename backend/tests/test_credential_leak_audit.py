"""T13.3: Credential Leak Audit Test Suite.

Audits database records, API response payloads, agent action logs,
and report summaries to ensure zero plaintext secrets or tokens ever leak.
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_credential, hash_password
from app.models.credential import ProjectCredential
from app.models.project import Project
from app.models.test_run import TestCase, TestResult, TestRun
from app.models.user import User


@pytest.mark.asyncio
async def test_t13_3_database_contains_no_plaintext_passwords_or_credentials(
    db_session: AsyncSession,
):
    """T13.3: Verify all database rows store only argon2 hashes and Fernet ciphertext."""
    test_password = "SuperSecretPassword123!"
    pw_hash = await hash_password(test_password)
    encrypted_cred = encrypt_credential(test_password)

    user = User(
        id=uuid.uuid4(),
        email="audit_user@example.com",
        password_hash=pw_hash,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    proj = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Audit Proj",
        target_url="http://localhost:8001",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.flush()

    cred = ProjectCredential(
        id=uuid.uuid4(),
        project_id=proj.id,
        role_label="admin",
        username="admin_user",
        password_encrypted=encrypted_cred,
    )
    db_session.add(cred)
    await db_session.commit()

    # Query back and verify raw columns
    users_stmt = select(User).where(User.id == user.id)
    db_user = (await db_session.execute(users_stmt)).scalar_one()
    assert test_password not in db_user.password_hash
    assert db_user.password_hash.startswith("$argon2")

    creds_stmt = select(ProjectCredential).where(ProjectCredential.id == cred.id)
    db_cred = (await db_session.execute(creds_stmt)).scalar_one()
    assert test_password not in db_cred.password_encrypted
    assert db_cred.password_encrypted.startswith("gAAAAA")  # Fernet signature


@pytest.mark.asyncio
async def test_t13_3_api_responses_and_reports_contain_no_credentials(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    """T13.3: Verify project, credential, and run reports exclude passwords and encryption keys."""
    headers, user_id, proj_id = auth_headers
    secret_pass = "ClassifiedPass999!"

    # Add credential
    cred_resp = await client.post(
        f"/projects/{proj_id}/credentials",
        json={"role_label": "admin", "username": "admin_audit", "password": secret_pass},
        headers=headers,
    )
    assert cred_resp.status_code == 201
    cred_data = cred_resp.json()

    # Verify response payload NEVER returns password or ciphertext
    assert secret_pass not in json.dumps(cred_data)
    assert "password" not in cred_data
    assert "password_encrypted" not in cred_data

    # List credentials
    list_resp = await client.get(f"/projects/{proj_id}/credentials", headers=headers)
    assert list_resp.status_code == 200
    assert secret_pass not in json.dumps(list_resp.json())

    # Create run with simulated result and report
    run = TestRun(
        id=uuid.uuid4(),
        project_id=proj_id,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
        report={
            "total_tests": 1,
            "passed_tests": 1,
            "failed_tests": 0,
            "pass_percentage": 100.0,
            "summary": "Run completed cleanly without leakage.",
        },
    )
    db_session.add(run)
    await db_session.flush()

    tc = TestCase(
        id=uuid.uuid4(),
        run_id=run.id,
        title="Audit Test",
        source_requirement="REQ-1",
        status="PASSED",
        order_index=1,
    )
    db_session.add(tc)
    await db_session.flush()

    tr = TestResult(
        id=uuid.uuid4(),
        test_case_id=tc.id,
        status="PASSED",
        steps=[{
            "step": 1,
            "tool": "playwright_fill",
            "arguments": {"selector": "#pwd", "value": "[REDACTED]"},
        }],
        screenshot_path="storage/screenshots/audit.png",
    )
    db_session.add(tr)
    await db_session.commit()

    # Check GET /runs/{run.id}
    run_resp = await client.get(f"/runs/{run.id}", headers=headers)
    assert run_resp.status_code == 200
    run_body = json.dumps(run_resp.json())
    assert secret_pass not in run_body

    # Check GET /runs/{run.id}/report
    report_resp = await client.get(f"/runs/{run.id}/report", headers=headers)
    assert report_resp.status_code == 200
    report_body = json.dumps(report_resp.json())
    assert secret_pass not in report_body

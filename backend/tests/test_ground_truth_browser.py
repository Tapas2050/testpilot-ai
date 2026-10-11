"""Scripted end-to-end ground-truth verification using real Playwright MCP against SupportDesk.

Marked as 'browser' so it only runs on demand (not in default test suite).
Verifies 7 ground-truth scenarios with:
1. SUPPORTDESK_DEFECTS=on:
   - "agent cannot delete a ticket" -> FAILED (agent can delete)
   - "ticket priority High is stored as High" -> FAILED (stored as Low)
   - "search by ticket ID finds the ticket" -> FAILED (no results)
   - "admin can delete a ticket" -> PASSED
   - "create a ticket" -> PASSED
   - "search by title" -> PASSED
   - "filter by status" -> PASSED
2. SUPPORTDESK_DEFECTS=off:
   - All 7 scenarios -> PASSED
"""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, List

import httpx
import pytest

from app.agent.executor import CheckResult, ExecutorAction, execute_single_test_case
from app.agent.llm import set_mock_llm
from app.agent.mcp_client import PlaywrightMCPClient, kill_process_tree
from app.models.test_run import TestCase

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SUPPORTDESK_DIR = REPO_ROOT / "supportdesk"


class ScriptedSequenceLLM:
    """Deterministic LLM that returns a pre-scripted sequence of ExecutorActions."""

    def __init__(self, actions: List[ExecutorAction]) -> None:
        self.actions = list(actions)
        self.call_index = 0

    async def ainvoke(self, messages: Any, **kwargs: Any) -> ExecutorAction:
        if self.call_index < len(self.actions):
            action = self.actions[self.call_index]
            self.call_index += 1
            return action
        # Default safety finish if steps exceed sequence
        return ExecutorAction(
            thought="Scripted sequence exhausted",
            action="finish",
            final_status="FAILED",
            observation="Scripted actions exhausted without explicit finish",
            check_results=[],
        )


@asynccontextmanager
async def run_supportdesk_server(defects_mode: str) -> AsyncGenerator[None, None]:
    """Start SupportDesk server on port 8001 with specified defects mode and reseeded database."""
    # 1. Reseed database via dedicated subprocess to prevent package namespace conflicts
    res = subprocess.run(
        [sys.executable, str(SUPPORTDESK_DIR / "reseed.py")],
        cwd=str(SUPPORTDESK_DIR),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if res.returncode != 0:
        logger.error("Reseed failed: %s %s", res.stdout, res.stderr)
        raise RuntimeError(f"Reseed failed: {res.stderr}")

    # 2. Spawn uvicorn process
    env = os.environ.copy()
    env["SUPPORTDESK_DEFECTS"] = defects_mode
    env.setdefault("SUPPORTDESK_ADMIN_PASSWORD", "TestAdminPassword123!")
    env.setdefault("SUPPORTDESK_AGENT_PASSWORD", "TestAgentPassword123!")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            "8001",
            "--host",
            "127.0.0.1",
        ],
        cwd=str(SUPPORTDESK_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 3. Poll until reachable
    started = False
    async with httpx.AsyncClient(timeout=1.0) as client:
        for _ in range(30):
            try:
                resp = await client.get("http://127.0.0.1:8001/login")
                if resp.status_code == 200:
                    started = True
                    break
            except Exception:
                await asyncio.sleep(0.5)

    if not started:
        kill_process_tree(proc.pid)
        raise RuntimeError("SupportDesk failed to start on port 8001 within 15 seconds")

    try:
        yield
    finally:
        kill_process_tree(proc.pid)
        await asyncio.sleep(0.5)


def get_test_credentials() -> dict[str, dict[str, str]]:
    """Return credentials for admin and agent roles without printing secrets."""
    admin_pw = os.getenv("SUPPORTDESK_ADMIN_PASSWORD", "TestAdminPassword123!")
    agent_pw = os.getenv("SUPPORTDESK_AGENT_PASSWORD", "TestAgentPassword123!")
    return {
        "admin": {"email": "admin@supportdesk.local", "password": admin_pw},
        "agent": {"email": "agent@supportdesk.local", "password": agent_pw},
    }


def get_scenario_plan_and_actions(
    scenario_name: str, defects_mode: str
) -> tuple[TestCase, List[ExecutorAction]]:
    """Build the planned TestCase and deterministic scripted actions for a given scenario."""
    defects_on = defects_mode.lower() == "on"

    if scenario_name == "agent_cannot_delete":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Agent cannot delete a ticket",
            description="Support agents must be prohibited from deleting tickets",
            source_requirement="REQ-SEC-02",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-SEC-02",
                    "description": "Agent cannot delete a ticket",
                    "source_requirement": "REQ-SEC-02",
                }
            ],
        )
        if defects_on:
            actions = [
                ExecutorAction(
                    thought="Navigate to ticket 5",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets/5",
                ),
                ExecutorAction(
                    thought="Attempt delete", action="click", selector="#delete-ticket-btn"
                ),
                ExecutorAction(
                    thought="Observe deletion allowed instead of 403",
                    action="finish",
                    final_status="FAILED",
                    observation="Agent deletion succeeded and was redirected to tickets",
                    evidence="Support Tickets",
                    check_results=[
                        CheckResult(
                            check_id="CHK-SEC-02",
                            result="FAILED",
                            evidence="Support Tickets",
                            observation="Agent deletion succeeded and was redirected to tickets",
                        )
                    ],
                ),
            ]
        else:
            actions = [
                ExecutorAction(
                    thought="Navigate to ticket 5",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets/5",
                ),
                ExecutorAction(
                    thought="Attempt delete", action="click", selector="#delete-ticket-btn"
                ),
                ExecutorAction(
                    thought="Observe 403 Forbidden rejection",
                    action="finish",
                    final_status="PASSED",
                    observation="Agent deletion was correctly rejected with 403 Forbidden",
                    evidence="Forbidden",
                    check_results=[
                        CheckResult(
                            check_id="CHK-SEC-02",
                            result="PASSED",
                            evidence="Forbidden",
                            observation="Agent deletion was correctly rejected with 403 Forbidden",
                        )
                    ],
                ),
            ]
        return tc, actions

    elif scenario_name == "high_priority_stored":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Ticket priority High is stored as High",
            description="Creating a high priority ticket persists priority as High",
            source_requirement="REQ-TKT-01",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-PRIO-01",
                    "description": "Ticket priority High is stored as High",
                    "source_requirement": "REQ-TKT-01",
                }
            ],
        )
        if defects_on:
            actions = [
                ExecutorAction(
                    thought="Navigate to create ticket",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets/new",
                ),
                ExecutorAction(
                    thought="Fill title",
                    action="fill",
                    selector="#title",
                    value="Critical Server Failure",
                ),
                ExecutorAction(
                    thought="Fill customer email",
                    action="fill",
                    selector="#customer_email",
                    value="corp@example.com",
                ),
                ExecutorAction(
                    thought="Fill description",
                    action="fill",
                    selector="#description",
                    value="Production down",
                ),
                ExecutorAction(
                    thought="Select high priority",
                    action="select",
                    selector="#priority",
                    value="High",
                ),
                ExecutorAction(
                    thought="Submit form", action="click", selector="#submit-ticket-btn"
                ),
                ExecutorAction(
                    thought="Observe priority stored as Low",
                    action="finish",
                    final_status="FAILED",
                    observation="Ticket was created with High priority but stored as Low",
                    evidence="Low",
                    check_results=[
                        CheckResult(
                            check_id="CHK-PRIO-01",
                            result="FAILED",
                            evidence="Low",
                            observation="Ticket created with High priority was stored as Low",
                        )
                    ],
                ),
            ]
        else:
            actions = [
                ExecutorAction(
                    thought="Navigate to create ticket",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets/new",
                ),
                ExecutorAction(
                    thought="Fill title",
                    action="fill",
                    selector="#title",
                    value="Critical Server Failure",
                ),
                ExecutorAction(
                    thought="Fill customer email",
                    action="fill",
                    selector="#customer_email",
                    value="corp@example.com",
                ),
                ExecutorAction(
                    thought="Fill description",
                    action="fill",
                    selector="#description",
                    value="Production down",
                ),
                ExecutorAction(
                    thought="Select high priority",
                    action="select",
                    selector="#priority",
                    value="High",
                ),
                ExecutorAction(
                    thought="Submit form", action="click", selector="#submit-ticket-btn"
                ),
                ExecutorAction(
                    thought="Observe priority stored as High",
                    action="finish",
                    final_status="PASSED",
                    observation="Ticket priority High was verified on ticket view",
                    evidence="High",
                    check_results=[
                        CheckResult(
                            check_id="CHK-PRIO-01",
                            result="PASSED",
                            evidence="High",
                            observation="Ticket priority High was verified on ticket view",
                        )
                    ],
                ),
            ]
        return tc, actions

    elif scenario_name == "search_by_ticket_id":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Search by ticket ID finds the ticket",
            description="Searching by ticket ID returns the corresponding ticket",
            source_requirement="REQ-SRCH-01",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-SRCH-ID",
                    "description": "Search by ticket ID finds the ticket",
                    "source_requirement": "REQ-SRCH-01",
                }
            ],
        )
        if defects_on:
            actions = [
                ExecutorAction(
                    thought="Navigate to tickets",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets",
                ),
                ExecutorAction(
                    thought="Fill search input with ID 1",
                    action="fill",
                    selector="#search-input",
                    value="1",
                ),
                ExecutorAction(thought="Submit search", action="click", selector="#search-btn"),
                ExecutorAction(
                    thought="Observe no tickets found message",
                    action="finish",
                    final_status="FAILED",
                    observation="Search by ticket ID 1 failed to return the ticket",
                    evidence="No tickets found.",
                    check_results=[
                        CheckResult(
                            check_id="CHK-SRCH-ID",
                            result="FAILED",
                            evidence="No tickets found.",
                            observation="Search by ticket ID 1 failed to return the ticket",
                        )
                    ],
                ),
            ]
        else:
            actions = [
                ExecutorAction(
                    thought="Navigate to tickets",
                    action="navigate",
                    url="http://127.0.0.1:8001/tickets",
                ),
                ExecutorAction(
                    thought="Fill search input with ID 1",
                    action="fill",
                    selector="#search-input",
                    value="1",
                ),
                ExecutorAction(thought="Submit search", action="click", selector="#search-btn"),
                ExecutorAction(
                    thought="Observe ticket 1 returned in results",
                    action="finish",
                    final_status="PASSED",
                    observation="Search by ID 1 displays ticket Cannot reset user password",
                    evidence="Cannot reset user password",
                    check_results=[
                        CheckResult(
                            check_id="CHK-SRCH-ID",
                            result="PASSED",
                            evidence="Cannot reset user password",
                            observation="Search by ID 1 displays ticket Cannot reset user password",
                        )
                    ],
                ),
            ]
        return tc, actions

    elif scenario_name == "admin_can_delete":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Admin can delete a ticket",
            description="Administrators are permitted to permanently delete tickets",
            source_requirement="REQ-SEC-01",
            target_role="admin",
            checks=[
                {
                    "check_id": "CHK-SEC-01",
                    "description": "Admin can delete a ticket",
                    "source_requirement": "REQ-SEC-01",
                }
            ],
        )
        actions = [
            ExecutorAction(
                thought="Navigate to ticket 4",
                action="navigate",
                url="http://127.0.0.1:8001/tickets/4",
            ),
            ExecutorAction(
                thought="Click delete button", action="click", selector="#delete-ticket-btn"
            ),
            ExecutorAction(
                thought="Observe redirect to tickets list after deletion",
                action="finish",
                final_status="PASSED",
                observation="Admin user deleted ticket and was redirected to dashboard",
                evidence="Support Tickets",
                check_results=[
                    CheckResult(
                        check_id="CHK-SEC-01",
                        result="PASSED",
                        evidence="Support Tickets",
                        observation="Admin user deleted ticket and was redirected to dashboard",
                    )
                ],
            ),
        ]
        return tc, actions

    elif scenario_name == "create_a_ticket":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Create a ticket",
            description="Users can create a new support ticket and verify its details",
            source_requirement="REQ-TKT-01",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-TKT-01",
                    "description": "Create a ticket and view details",
                    "source_requirement": "REQ-TKT-01",
                }
            ],
        )
        actions = [
            ExecutorAction(
                thought="Navigate to new ticket page",
                action="navigate",
                url="http://127.0.0.1:8001/tickets/new",
            ),
            ExecutorAction(
                thought="Fill title",
                action="fill",
                selector="#title",
                value="Printer Connection Timeout",
            ),
            ExecutorAction(
                thought="Fill customer email",
                action="fill",
                selector="#customer_email",
                value="office@corp.local",
            ),
            ExecutorAction(
                thought="Fill description",
                action="fill",
                selector="#description",
                value="Printer offline on 2nd floor",
            ),
            ExecutorAction(
                thought="Select Medium priority",
                action="select",
                selector="#priority",
                value="Medium",
            ),
            ExecutorAction(
                thought="Submit creation", action="click", selector="#submit-ticket-btn"
            ),
            ExecutorAction(
                thought="Observe created ticket title on detail page",
                action="finish",
                final_status="PASSED",
                observation="Ticket created with title Printer Connection Timeout",
                evidence="Printer Connection Timeout",
                check_results=[
                    CheckResult(
                        check_id="CHK-TKT-01",
                        result="PASSED",
                        evidence="Printer Connection Timeout",
                        observation="Ticket created with title Printer Connection Timeout",
                    )
                ],
            ),
        ]
        return tc, actions

    elif scenario_name == "search_by_title":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Search by title",
            description="Searching by text query returns tickets matching title",
            source_requirement="REQ-SRCH-02",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-SRCH-02",
                    "description": "Search by title returns matching tickets",
                    "source_requirement": "REQ-SRCH-02",
                }
            ],
        )
        actions = [
            ExecutorAction(
                thought="Navigate to tickets page",
                action="navigate",
                url="http://127.0.0.1:8001/tickets",
            ),
            ExecutorAction(
                thought="Search for password",
                action="fill",
                selector="#search-input",
                value="password",
            ),
            ExecutorAction(thought="Click search filter", action="click", selector="#search-btn"),
            ExecutorAction(
                thought="Observe matching password ticket in results",
                action="finish",
                final_status="PASSED",
                observation="Title search returned Cannot reset user password",
                evidence="Cannot reset user password",
                check_results=[
                    CheckResult(
                        check_id="CHK-SRCH-02",
                        result="PASSED",
                        evidence="Cannot reset user password",
                        observation="Title search returned Cannot reset user password",
                    )
                ],
            ),
        ]
        return tc, actions

    elif scenario_name == "filter_by_status":
        tc = TestCase(
            id=uuid.uuid4(),
            title="Filter by status",
            description="Filtering by ticket status returns only tickets with that status",
            source_requirement="REQ-SRCH-03",
            target_role="agent",
            checks=[
                {
                    "check_id": "CHK-SRCH-03",
                    "description": "Filter by status returns tickets with that status",
                    "source_requirement": "REQ-SRCH-03",
                }
            ],
        )
        actions = [
            ExecutorAction(
                thought="Navigate to tickets page",
                action="navigate",
                url="http://127.0.0.1:8001/tickets",
            ),
            ExecutorAction(
                thought="Select status RESOLVED",
                action="select",
                selector="#status-filter",
                value="RESOLVED",
            ),
            ExecutorAction(thought="Click filter button", action="click", selector="#search-btn"),
            ExecutorAction(
                thought="Observe resolved dark mode ticket in results",
                action="finish",
                final_status="PASSED",
                observation="Filtering by RESOLVED returned Feature request: Dark mode",
                evidence="Feature request: Dark mode",
                check_results=[
                    CheckResult(
                        check_id="CHK-SRCH-03",
                        result="PASSED",
                        evidence="Feature request: Dark mode",
                        observation="Filtering by RESOLVED returned Feature request: Dark mode",
                    )
                ],
            ),
        ]
        return tc, actions

    raise ValueError(f"Unknown scenario name: {scenario_name}")


SCENARIOS = [
    "agent_cannot_delete",
    "high_priority_stored",
    "search_by_ticket_id",
    "admin_can_delete",
    "create_a_ticket",
    "search_by_title",
    "filter_by_status",
]


@pytest.mark.browser
@pytest.mark.asyncio
async def test_part7_scripted_ground_truth_defects_on(tmp_path: Path):
    """Part 7: Execute 7 scenarios with SUPPORTDESK_DEFECTS=on using real Playwright MCP."""
    async with run_supportdesk_server(defects_mode="on"):
        credentials = get_test_credentials()
        run_id = uuid.uuid4()

        mcp_client = PlaywrightMCPClient(is_mock=False)
        await mcp_client.start()

        verdicts = {}
        try:
            for scenario in SCENARIOS:
                tc, actions = get_scenario_plan_and_actions(scenario, defects_mode="on")
                scripted_llm = ScriptedSequenceLLM(actions)
                set_mock_llm(scripted_llm)

                result = await execute_single_test_case(
                    test_case=tc,
                    target_url="http://127.0.0.1:8001",
                    credentials=credentials,
                    mcp_client=mcp_client,
                    run_id=run_id,
                    storage_dir=tmp_path,
                )
                verdicts[scenario] = result.status
        finally:
            set_mock_llm(None)
            await mcp_client.close()

        # Expected verdicts with defects ON:
        assert verdicts["agent_cannot_delete"] == "FAILED"
        assert verdicts["high_priority_stored"] == "FAILED"
        assert verdicts["search_by_ticket_id"] == "FAILED"
        assert verdicts["admin_can_delete"] == "PASSED"
        assert verdicts["create_a_ticket"] == "PASSED"
        assert verdicts["search_by_title"] == "PASSED"
        assert verdicts["filter_by_status"] == "PASSED"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_part7_scripted_ground_truth_defects_off(tmp_path: Path):
    """Part 7: Execute 7 scenarios with SUPPORTDESK_DEFECTS=off using real Playwright MCP."""
    async with run_supportdesk_server(defects_mode="off"):
        credentials = get_test_credentials()
        run_id = uuid.uuid4()

        mcp_client = PlaywrightMCPClient(is_mock=False)
        await mcp_client.start()

        verdicts = {}
        try:
            for scenario in SCENARIOS:
                tc, actions = get_scenario_plan_and_actions(scenario, defects_mode="off")
                scripted_llm = ScriptedSequenceLLM(actions)
                set_mock_llm(scripted_llm)

                result = await execute_single_test_case(
                    test_case=tc,
                    target_url="http://127.0.0.1:8001",
                    credentials=credentials,
                    mcp_client=mcp_client,
                    run_id=run_id,
                    storage_dir=tmp_path,
                )
                verdicts[scenario] = result.status
        finally:
            set_mock_llm(None)
            await mcp_client.close()

        # Expected verdicts with defects OFF:
        for scenario in SCENARIOS:
            v = verdicts[scenario]
            assert v == "PASSED", f"{scenario} expected PASSED, got {v}"


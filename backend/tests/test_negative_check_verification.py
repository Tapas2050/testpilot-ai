"""Tests for negative check verification in executor (Part 4).

Proves that:
1. If an executor attempts a prohibited action (e.g. agent ticket deletion) and the
   action succeeds without rejection (landed on /tickets with 'Support Tickets'),
   the verdict is forced to FAILED even if the LLM wrongly claimed PASSED.
2. If the attempt was correctly rejected (e.g. 403 Forbidden), the check PASSES.
3. If no action was attempted at all, the check is INCONCLUSIVE and test status is BLOCKED.
"""

from unittest.mock import MagicMock

from app.agent.executor import CheckResult, evaluate_check_result


def test_prohibited_action_succeeds_is_marked_failed():
    """Regression for real run 3098: LLM misread /tickets after-state as prohibition."""
    obs_text = (
        "Support agents are successfully prevented from deleting tickets as verified by redirect."
    )
    mr = {
        "check_id": "CHK-1",
        "description": "Users with the Support Agent role MUST NOT be allowed to delete tickets.",
        "source_requirement": "REQ-SEC-02",
        "result": "PASSED",
        "evidence": "Support Tickets",
        "observation": obs_text,
    }
    c_res = CheckResult(
        check_id="CHK-1",
        result="PASSED",
        evidence="Support Tickets",
        observation=obs_text,
        attempted_step=3,
    )

    tickets_page_text = (
        "Support Tickets\nSearch tickets...\nOpen Tickets\n#1 - Cannot reset password"
    )

    # Fixture of real run steps
    steps_taken = [
        {"step": 1, "action": "login", "status": "ok"},
        {
            "step": 2,
            "action": "click",
            "selector": "#ticket-id-link-6",
            "status": "ok",
            "visible_text_after": "#6 - Cannot access billing\nDelete Ticket",
            "url_after": "http://127.0.0.1:8001/tickets/6",
        },
        {
            "step": 3,
            "action": "click",
            "selector": "#delete-ticket-btn",
            "status": "ok",
            "visible_text_after": tickets_page_text,
            "url_after": "http://127.0.0.1:8001/tickets",
        },
    ]

    obs = MagicMock()
    obs.visible_text = tickets_page_text
    obs.url = "http://127.0.0.1:8001/tickets"

    status, obs_msg = evaluate_check_result(mr, c_res, steps_taken, obs)

    # Must be evaluated to FAILED because the action succeeded
    assert status == "FAILED"
    assert "Prohibited action was permitted" in obs_msg


def test_prohibited_action_rejected_is_marked_passed():
    """Correct build: Attempting delete results in 403 Forbidden in after-state."""
    mr = {
        "check_id": "CHK-1",
        "description": "Users with the Support Agent role MUST NOT be allowed to delete tickets.",
        "source_requirement": "REQ-SEC-02",
        "result": "PASSED",
        "evidence": "Forbidden",
        "observation": "Agent deletion was correctly rejected with 403 Forbidden.",
    }
    c_res = CheckResult(
        check_id="CHK-1",
        result="PASSED",
        evidence="Forbidden",
        observation="Agent deletion was correctly rejected with 403 Forbidden.",
        attempted_step=3,
    )

    steps_taken = [
        {"step": 1, "action": "login", "status": "ok"},
        {
            "step": 2,
            "action": "click",
            "selector": "#ticket-id-link-6",
            "status": "ok",
            "visible_text_after": "#6 - Cannot access billing\nDelete Ticket",
            "url_after": "http://127.0.0.1:8001/tickets/6",
        },
        {
            "step": 3,
            "action": "click",
            "selector": "#delete-ticket-btn",
            "status": "ok",
            "visible_text_after": "Forbidden: Only administrators can delete tickets",
            "url_after": "http://127.0.0.1:8001/tickets/6/delete",
        },
    ]

    obs = MagicMock()
    obs.visible_text = "Forbidden: Only administrators can delete tickets"
    obs.url = "http://127.0.0.1:8001/tickets/6/delete"

    status, obs_msg = evaluate_check_result(mr, c_res, steps_taken, obs)

    assert status == "PASSED"
    assert "rejected" in obs_msg.lower() or "forbidden" in obs_msg.lower()


def test_negative_check_without_attempt_is_inconclusive():
    """Negative check without an attempted action must be INCONCLUSIVE (test BLOCKED)."""
    mr = {
        "check_id": "CHK-1",
        "description": "Users with the Support Agent role MUST NOT be allowed to delete tickets.",
        "source_requirement": "REQ-SEC-02",
        "result": "PASSED",
        "evidence": "Support Tickets",
        "observation": "Delete button is absent so agent cannot delete.",
    }
    c_res = CheckResult(
        check_id="CHK-1",
        result="PASSED",
        evidence="Support Tickets",
        observation="Delete button is absent so agent cannot delete.",
    )

    # Only login, no attempt made
    steps_taken = [
        {"step": 1, "action": "login", "status": "ok"},
    ]

    obs = MagicMock()
    obs.visible_text = "Support Tickets"
    obs.url = "http://127.0.0.1:8001/tickets"

    status, obs_msg = evaluate_check_result(mr, c_res, steps_taken, obs)

    assert status == "INCONCLUSIVE"
    assert "No attempted action recorded" in obs_msg

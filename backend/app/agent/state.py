"""State definitions for the TestPilot agent graph."""

from typing import Any, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Execution state carried across LangGraph nodes."""

    run_id: str
    project_id: str
    db_url: Optional[str]
    current_stage: str  # QUEUED, PLANNING, EXECUTING, ANALYZING, REPORTING, COMPLETED, FAILED
    status: str
    test_cases: list[dict[str, Any]]
    results: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    report: Optional[dict[str, Any]]
    error: Optional[str]
    cancel_requested: bool

"""LangGraph agent orchestration graph with stub nodes for Phase 8."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agent.checkpointer import get_checkpointer
from app.agent.state import AgentState
from app.core.database import get_async_session_factory
from app.models.test_run import TestCase, TestResult
from app.services.run_service import (
    cache_run_status,
    is_cancel_flag_set,
    release_run_lock,
    update_run_in_db,
)


async def check_cancellation(state: AgentState) -> bool:
    """Return True if cancellation has been requested."""
    if state.get("cancel_requested"):
        return True
    run_id_str = state.get("run_id")
    if run_id_str:
        return await is_cancel_flag_set(uuid.UUID(run_id_str))
    return False


# --- Node Definitions ---

async def plan_node(state: AgentState) -> dict[str, Any]:
    """Stub Planner node: Generates planned test cases."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "PLANNING"
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)

    # In Phase 8 foundation, insert 2 stub test cases into DB if not present
    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        tc1 = TestCase(
            run_id=run_id,
            title="Verify user login with valid credentials",
            description="Login with admin credentials and verify redirect to /tickets",
            source_requirement="REQ-AUTH-01",
            target_role="admin",
            status="PENDING",
            order_index=1,
        )
        tc2 = TestCase(
            run_id=run_id,
            title="Verify support agent cannot delete tickets",
            description="Attempt ticket deletion as support agent and expect 403",
            source_requirement="REQ-SEC-02",
            target_role="agent",
            status="PENDING",
            order_index=2,
        )
        session.add_all([tc1, tc2])
        await session.commit()
        await session.refresh(tc1)
        await session.refresh(tc2)

        test_cases = [
            {"id": str(tc1.id), "title": tc1.title, "role": tc1.target_role},
            {"id": str(tc2.id), "title": tc2.title, "role": tc2.target_role},
        ]

    return {
        "current_stage": "PLANNING",
        "status": "PLANNING",
        "test_cases": test_cases,
    }


async def execute_node(state: AgentState) -> dict[str, Any]:
    """Stub Executor node: Runs test cases and collects results."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "EXECUTING"
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)

    results = []
    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        from sqlalchemy import select
        stmt = select(TestCase).where(TestCase.run_id == run_id).order_by(TestCase.order_index)
        tcs = (await session.execute(stmt)).scalars().all()

        for idx, tc in enumerate(tcs):
            tc.status = "PASSED"
            res = TestResult(
                test_case_id=tc.id,
                status="PASSED",
                steps=[{"step": 1, "action": "navigate", "status": "ok"}],
                duration_seconds=1.2,
            )
            session.add(res)
            results.append({"test_case_id": str(tc.id), "status": "PASSED"})

        await session.commit()

    return {
        "current_stage": "EXECUTING",
        "status": "EXECUTING",
        "results": results,
    }


async def analyze_node(state: AgentState) -> dict[str, Any]:
    """Stub Analyst node: Evaluates failed tests."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "ANALYZING"
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)

    # In Phase 8 stub, no failures by default
    return {
        "current_stage": "ANALYZING",
        "status": "ANALYZING",
        "failures": [],
    }


async def report_node(state: AgentState) -> dict[str, Any]:
    """Stub Report node: Generates summary report."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "REPORTING"
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)

    report_data = {
        "total_tests": len(state.get("test_cases", [])),
        "passed_tests": len(state.get("results", [])),
        "failed_tests": len(state.get("failures", [])),
        "pass_rate": 100.0,
        "summary": "Stub execution completed successfully.",
    }

    await update_run_in_db(run_id, report=report_data, db_url=db_url)

    return {
        "current_stage": "REPORTING",
        "status": "REPORTING",
        "report": report_data,
    }


async def complete_node(state: AgentState) -> dict[str, Any]:
    """Final node: Marks run as COMPLETED with timestamp."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    now = datetime.now(timezone.utc)
    status = "COMPLETED"

    await update_run_in_db(run_id, status=status, completed_at=now, db_url=db_url)
    await cache_run_status(run_id, status=status, stage=status)

    project_id = uuid.UUID(state["project_id"])
    await release_run_lock(project_id)

    return {
        "current_stage": status,
        "status": status,
    }


async def cancel_node(state: AgentState) -> dict[str, Any]:
    """Handles cancellation: Marks run as CANCELLED."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    now = datetime.now(timezone.utc)
    status = "CANCELLED"

    await update_run_in_db(
        run_id, status=status, completed_at=now, cancel_requested=True, db_url=db_url
    )
    await cache_run_status(run_id, status=status, stage=status)

    project_id = uuid.UUID(state["project_id"])
    await release_run_lock(project_id)

    return {
        "current_stage": status,
        "status": status,
        "cancel_requested": True,
    }


# Router logic
def route_step(state: AgentState) -> str:
    if state.get("cancel_requested"):
        return "cancel"
    return "next"


def build_agent_graph(checkpointer=None):
    """Build and compile the LangGraph workflow with checkpointer."""
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("report", report_node)
    workflow.add_node("complete", complete_node)
    workflow.add_node("cancel", cancel_node)

    # Edge from START to plan
    workflow.add_edge(START, "plan")

    workflow.add_conditional_edges("plan", route_step, {"next": "execute", "cancel": "cancel"})
    workflow.add_conditional_edges("execute", route_step, {"next": "analyze", "cancel": "cancel"})
    workflow.add_conditional_edges("analyze", route_step, {"next": "report", "cancel": "cancel"})
    workflow.add_conditional_edges("report", route_step, {"next": "complete", "cancel": "cancel"})

    workflow.add_edge("complete", END)
    workflow.add_edge("cancel", END)

    return workflow.compile(checkpointer=checkpointer)


async def execute_agent_run(
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    db_url: Optional[str] = None,
    force_fail_at: Optional[str] = None,
) -> None:
    """Execute the full agent workflow for a given TestRun."""
    now = datetime.now(timezone.utc)
    await update_run_in_db(run_id, started_at=now, db_url=db_url)

    checkpointer = get_checkpointer(db_url)
    graph = build_agent_graph(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": str(run_id)}}
    initial_state: AgentState = {
        "run_id": str(run_id),
        "project_id": str(project_id),
        "db_url": db_url,
        "current_stage": "QUEUED",
        "status": "QUEUED",
        "test_cases": [],
        "results": [],
        "failures": [],
        "cancel_requested": False,
    }

    try:
        # Check if forced failure requested for testing T8.3
        if force_fail_at == "start":
            raise RuntimeError("Forced node exception during execution")

        async for _output in graph.astream(initial_state, config=config):
            if force_fail_at == "midway":
                raise RuntimeError("Forced node exception midway through execution")

    except Exception as exc:
        err_msg = str(exc)
        status = "FAILED"
        now = datetime.now(timezone.utc)
        await update_run_in_db(
            run_id, status=status, completed_at=now, error_message=err_msg, db_url=db_url
        )
        await cache_run_status(run_id, status=status, stage=status, error=err_msg)
        await release_run_lock(project_id)
        # We catch and do not re-raise so worker task completes cleanly and API stays up

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

    # Retrieve project documents and generate test plan via Planner Agent
    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        from sqlalchemy import select

        from app.agent.planner import generate_test_plan
        from app.models.document import Document
        from app.models.project import Project
        from app.services.rag_service import RAGService

        project_id = uuid.UUID(state["project_id"])
        proj_stmt = select(Project).where(Project.id == project_id)
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        target_url = project.target_url if project else "http://localhost:8001"

        rag = RAGService()
        rag_query = (
            "user roles authentication login ticket creation "
            "status search filter delete permissions"
        )
        chunks = await rag.retrieve(
            session,
            project_id,
            query=rag_query,
            top_k=8,
        )

        requirements_parts = [c["content"] for c in chunks] if chunks else []

        if not requirements_parts:
            doc_stmt = select(Document.extracted_text).where(
                Document.project_id == project_id,
                Document.extracted_text.isnot(None),
            )
            docs = (await session.execute(doc_stmt)).scalars().all()
            requirements_parts = [d for d in docs if d and d.strip()]

        if not requirements_parts:
            requirements_text = "No specification documents uploaded for this project."
        else:
            requirements_text = "\n\n---\n\n".join(requirements_parts)

        plan = await generate_test_plan(requirements_text=requirements_text, project_url=target_url)

        db_test_cases = []
        for idx, tc in enumerate(plan.test_cases, start=1):
            db_tc = TestCase(
                run_id=run_id,
                title=tc.title,
                description=tc.description,
                source_requirement=tc.source_requirement,
                target_role=tc.target_role,
                status="PENDING",
                order_index=idx,
            )
            session.add(db_tc)
            db_test_cases.append(db_tc)

        await session.commit()
        for db_tc in db_test_cases:
            await session.refresh(db_tc)

        test_cases = [
            {
                "id": str(db_tc.id),
                "title": db_tc.title,
                "role": db_tc.target_role,
                "source_requirement": db_tc.source_requirement,
            }
            for db_tc in db_test_cases
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

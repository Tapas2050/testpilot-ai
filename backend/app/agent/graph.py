"""LangGraph agent orchestration graph with stub nodes for Phase 8."""

import asyncio
import logging
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

import app.agent.executor as executor
from app.agent.checkpointer import get_checkpointer
from app.agent.llm import get_live_call_count
from app.agent.mcp_client import PlaywrightMCPClient, ToolTimeoutError
from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.database import get_async_session_factory
from app.core.security import format_run_failure_message, sanitize_secret_values
from app.models.test_run import Failure, TestCase, TestResult, TestRun
from app.services.run_service import (
    cache_run_status,
    clear_live_progress_keys,
    is_cancel_flag_set,
    release_run_lock,
    set_worker_heartbeat,
    update_live_progress,
    update_run_in_db,
)

logger = logging.getLogger(__name__)


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
    logger.info("[run_id=%s] Stage changed to PLANNING", run_id)
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)
    await update_live_progress(run_id, stage=stage, total_tests=0, completed_tests=0)

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

        await update_live_progress(
            run_id, stage="PLANNING", total_tests=len(db_test_cases), completed_tests=0
        )

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
    """Executor node: Runs test cases step-by-step using Playwright MCP client."""
    run_id = uuid.UUID(state["run_id"])
    project_id = uuid.UUID(state["project_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "EXECUTING"
    logger.info("[run_id=%s] Stage changed to EXECUTING", run_id)
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)

    from pathlib import Path

    from app.core.security import decrypt_credential
    from app.models.credential import ProjectCredential
    from app.models.project import Project

    settings = get_settings()
    storage_dir = Path(settings.STORAGE_DIR)

    results = []
    auth_failures: list[dict[str, Any]] = []
    consecutive_auth_failures = 0
    last_failed_role = ""
    auth_aborted = False
    consecutive_llm_failures = 0
    last_llm_error = ""
    llm_aborted = False
    abort_message = ""

    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        # 1. Fetch project target URL
        proj_stmt = select(Project).where(Project.id == project_id)
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        target_url = project.target_url if project else "http://localhost:8001"

        # 2. Fetch and decrypt stored project credentials
        cred_stmt = select(ProjectCredential).where(ProjectCredential.project_id == project_id)
        db_creds = (await session.execute(cred_stmt)).scalars().all()
        credentials: dict[str, dict[str, str]] = {}
        for c in db_creds:
            try:
                decrypted_pw = decrypt_credential(c.password_encrypted)
            except Exception:
                decrypted_pw = ""
            credentials[c.role_label.lower()] = {
                "email": c.username,
                "password": decrypted_pw,
            }

        # 3. Retrieve planned test cases
        stmt = select(TestCase).where(TestCase.run_id == run_id).order_by(TestCase.order_index)
        tcs = (await session.execute(stmt)).scalars().all()

        await update_live_progress(
            run_id, stage=stage, total_tests=len(tcs), completed_tests=0
        )

        import os
        is_mock_mcp = state.get("is_mock_mcp", False) or bool(os.getenv("PYTEST_CURRENT_TEST"))
        mcp_client = PlaywrightMCPClient(is_mock=is_mock_mcp)
        _active_mcp_clients[run_id] = mcp_client
        try:
            await mcp_client.start()
        except Exception as mcp_start_exc:
            logger.error(
                "[run_id=%s] Failed to start Playwright MCP client: %s",
                run_id,
                mcp_start_exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"Playwright MCP server failed to start: {mcp_start_exc}"
            ) from mcp_start_exc

        try:
            for tc_idx, tc in enumerate(tcs):
                if await check_cancellation(state):
                    return {"cancel_requested": True, "current_stage": "CANCELLED"}

                tc_key = getattr(tc, "test_key", None) or f"tc_{tc.order_index + 1}"
                _active_test_keys[run_id] = tc_key
                tc.status = "RUNNING"
                session.add(tc)
                await session.commit()
                logger.info(
                    "[run_id=%s] Test started: %s (id=%s, role=%s)",
                    run_id,
                    tc.title,
                    tc.id,
                    tc.target_role,
                )
                await update_live_progress(
                    run_id,
                    stage=stage,
                    current_test=tc.title,
                    current_step=0,
                    completed_tests=len(results),
                )

                test_start_mono = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        executor.execute_single_test_case(
                            test_case=tc,
                            target_url=target_url,
                            credentials=credentials,
                            mcp_client=mcp_client,
                            run_id=run_id,
                            storage_dir=storage_dir,
                        ),
                        timeout=float(settings.TEST_TIMEOUT_SECONDS),
                    )
                except (ToolTimeoutError, asyncio.TimeoutError, TimeoutError) as exc:
                    elapsed = round(time.monotonic() - test_start_mono, 2)
                    tool_or_step = getattr(exc, "tool_name", None) or "browser_tool"
                    logger.error(
                        "[run_id=%s] Test '%s' timed out (TEST_TIMEOUT_SECONDS=%ds): %s",
                        run_id,
                        tc.title,
                        settings.TEST_TIMEOUT_SECONDS,
                        exc,
                    )
                    try:
                        await mcp_client.restart()
                    except Exception as restart_exc:
                        logger.error(
                            "[run_id=%s] Failed to restart MCP client: %s",
                            run_id,
                            restart_exc,
                        )

                    detail_msg = exc or "operation timed out"
                    result = TestResult(
                        test_case_id=tc.id,
                        status="FAILED",
                        error_message=(
                            f"ENVIRONMENT_FAILURE: Tool '{tool_or_step}' "
                            f"timed out after {elapsed}s: {detail_msg}"
                        ),
                        duration_seconds=elapsed,
                    )
                finally:
                    _active_test_keys.pop(run_id, None)

                tc.status = result.status
                session.add(tc)
                session.add(result)
                results.append({"test_case_id": str(tc.id), "status": result.status})
                logger.info(
                    "[run_id=%s] Test ended: %s (id=%s) -> status=%s",
                    run_id,
                    tc.title,
                    tc.id,
                    result.status,
                )

                is_env_failure = (
                    result.status == "FAILED"
                    and (
                        "Environment failure" in (result.error_message or "")
                        or "timed out" in (result.error_message or "").lower()
                    )
                )
                if is_env_failure:
                    env_msg = result.error_message or "Tool timeout"
                    env_failure_entry = {
                        "test_case_id": str(tc.id),
                        "title": tc.title,
                        "source_requirement": tc.source_requirement,
                        "classification": "ENVIRONMENT_FAILURE",
                        "severity": "HIGH",
                        "confidence": 1.0,
                        "expected": "Browser tool execution succeeds within allocated timeout",
                        "observed": env_msg,
                        "explanation": (
                            f"Browser tool timed out and MCP server was restarted: {env_msg}"
                        ),
                        "suggested_action": "Check target app responsiveness and resources.",
                    }
                    auth_failures.append(env_failure_entry)
                    db_failure = Failure(
                        test_case_id=tc.id,
                        classification="ENVIRONMENT_FAILURE",
                        severity="HIGH",
                        confidence=1.0,
                        expected=env_failure_entry["expected"],
                        observed=env_failure_entry["observed"],
                        explanation=env_failure_entry["explanation"],
                        suggested_action=env_failure_entry["suggested_action"],
                    )
                    session.add(db_failure)

                is_auth_failure = (
                    result.status == "BLOCKED"
                    and "Authentication failed" in (result.error_message or "")
                )
                if is_auth_failure:
                    consecutive_auth_failures += 1
                    last_failed_role = tc.target_role or "user"
                    auth_failure_entry = {
                        "test_case_id": str(tc.id),
                        "title": tc.title,
                        "source_requirement": tc.source_requirement,
                        "classification": "AUTHENTICATION_FAILURE",
                        "severity": "HIGH",
                        "confidence": 1.0,
                        "expected": f"Successful authentication for role '{tc.target_role}'",
                        "observed": result.error_message or "Authentication failure",
                        "explanation": f"Scripted login for role '{tc.target_role}' failed.",
                        "suggested_action": (
                            "Check project's saved credentials in Project Settings."
                        ),
                    }
                    auth_failures.append(auth_failure_entry)
                    db_failure = Failure(
                        test_case_id=tc.id,
                        classification="AUTHENTICATION_FAILURE",
                        severity="HIGH",
                        confidence=1.0,
                        expected=auth_failure_entry["expected"],
                        observed=auth_failure_entry["observed"],
                        explanation=auth_failure_entry["explanation"],
                        suggested_action=auth_failure_entry["suggested_action"],
                    )
                    session.add(db_failure)
                else:
                    consecutive_auth_failures = 0

                is_llm_failure = (
                    result.status == "BLOCKED"
                    and (
                        "All LLM providers failed" in (result.error_message or "")
                        or "LLM provider failure" in (result.error_message or "")
                    )
                )
                if is_llm_failure:
                    consecutive_llm_failures += 1
                    last_llm_error = result.error_message or "All LLM providers failed"
                    llm_failure_entry = {
                        "test_case_id": str(tc.id),
                        "title": tc.title,
                        "source_requirement": tc.source_requirement,
                        "classification": "ENVIRONMENT_FAILURE",
                        "severity": "HIGH",
                        "confidence": 1.0,
                        "expected": "LLM provider responds with valid test step decision",
                        "observed": result.error_message or "All LLM providers failed",
                        "explanation": (
                            f"All LLM providers failed on '{tc.title}': {result.error_message}"
                        ),
                        "suggested_action": "Check LLM API keys, quotas, or provider status.",
                    }
                    auth_failures.append(llm_failure_entry)
                    db_failure = Failure(
                        test_case_id=tc.id,
                        classification="ENVIRONMENT_FAILURE",
                        severity="HIGH",
                        confidence=1.0,
                        expected=llm_failure_entry["expected"],
                        observed=llm_failure_entry["observed"],
                        explanation=llm_failure_entry["explanation"],
                        suggested_action=llm_failure_entry["suggested_action"],
                    )
                    session.add(db_failure)
                else:
                    consecutive_llm_failures = 0

                await session.commit()
                await update_live_progress(
                    run_id,
                    stage=stage,
                    completed_tests=len(results),
                )

                # Stop early if two consecutive tests fail to log in
                if consecutive_auth_failures >= 2:
                    auth_aborted = True
                    abort_message = (
                        f"Authentication failed for role '{last_failed_role}'. "
                        f"Please check the project's saved credentials in Project Settings."
                    )
                    # Mark remaining tests BLOCKED
                    for remaining_tc in tcs[tc_idx + 1:]:
                        remaining_tc.status = "BLOCKED"
                        session.add(remaining_tc)
                        blocked_res = TestResult(
                            test_case_id=remaining_tc.id,
                            status="BLOCKED",
                            error_message=(
                                "Blocked: Run stopped early due to repeated "
                                f"authentication failures ({abort_message})"
                            ),
                        )
                        session.add(blocked_res)
                        results.append({
                            "test_case_id": str(remaining_tc.id),
                            "status": "BLOCKED",
                        })
                    await session.commit()
                    break

                # Stop early if two consecutive tests fail due to LLM provider failures
                if consecutive_llm_failures >= 2:
                    llm_aborted = True
                    abort_message = (
                        f"All LLM providers failed on consecutive tests ({last_llm_error}). "
                        "Please check LLM API keys, daily quotas, or provider service status."
                    )
                    # Mark remaining tests BLOCKED
                    for remaining_tc in tcs[tc_idx + 1:]:
                        remaining_tc.status = "BLOCKED"
                        session.add(remaining_tc)
                        blocked_res = TestResult(
                            test_case_id=remaining_tc.id,
                            status="BLOCKED",
                            error_message=(
                                "Blocked: Run stopped early due to repeated "
                                f"LLM provider failures ({abort_message})"
                            ),
                        )
                        session.add(blocked_res)
                        results.append({
                            "test_case_id": str(remaining_tc.id),
                            "status": "BLOCKED",
                        })
                    await session.commit()
                    break

        finally:
            await mcp_client.close()

    return {
        "current_stage": "EXECUTING",
        "status": "EXECUTING",
        "results": results,
        "failures": auth_failures,
        "auth_aborted": auth_aborted,
        "llm_aborted": llm_aborted,
        "abort_message": abort_message,
    }


async def analyze_node(state: AgentState) -> dict[str, Any]:
    """Failure Analyst node: Evaluates failed tests only and persists Failure records."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "ANALYZING"
    logger.info("[run_id=%s] Stage changed to ANALYZING", run_id)
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)
    await update_live_progress(run_id, stage=stage)

    from sqlalchemy import select

    from app.agent.analyst import analyze_test_failure
    from app.models.test_run import Failure, TestResult

    failures = list(state.get("failures", []))
    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        # T11.2: Analyst runs only for failed tests
        stmt = (
            select(TestCase)
            .where(TestCase.run_id == run_id, TestCase.status == "FAILED")
            .order_by(TestCase.order_index)
        )
        failed_tcs = (await session.execute(stmt)).scalars().all()

        for tc in failed_tcs:
            if await check_cancellation(state):
                return {"cancel_requested": True, "current_stage": "CANCELLED"}

            # Load the corresponding test result
            res_stmt = (
                select(TestResult)
                .where(TestResult.test_case_id == tc.id)
                .order_by(TestResult.id.desc())
            )
            res = (await session.execute(res_stmt)).scalars().first()
            steps = res.steps if res and res.steps else []
            err_msg = res.error_message if res else None

            analysis = await analyze_test_failure(
                title=tc.title,
                description=tc.description,
                source_requirement=tc.source_requirement,
                target_role=tc.target_role,
                steps=steps,
                error_message=err_msg,
            )

            db_failure = Failure(
                test_case_id=tc.id,
                classification=analysis.classification,
                severity=analysis.severity,
                confidence=analysis.confidence,
                expected=analysis.expected,
                observed=analysis.observed,
                explanation=analysis.explanation,
                suggested_action=analysis.suggested_action,
            )
            session.add(db_failure)

            failures.append({
                "test_case_id": str(tc.id),
                "title": tc.title,
                "source_requirement": tc.source_requirement,
                "classification": analysis.classification,
                "severity": analysis.severity,
                "confidence": analysis.confidence,
                "expected": analysis.expected,
                "observed": analysis.observed,
                "explanation": analysis.explanation,
                "suggested_action": analysis.suggested_action,
                "screenshot_path": res.screenshot_path if res else None,
            })

        await session.commit()

    return {
        "current_stage": "ANALYZING",
        "status": "ANALYZING",
        "failures": failures,
    }


async def report_node(state: AgentState) -> dict[str, Any]:
    """Report Generator node: Generates complete metrics, breakdowns, and report JSON."""
    run_id = uuid.UUID(state["run_id"])
    db_url = state.get("db_url")
    if await check_cancellation(state):
        return {"cancel_requested": True, "current_stage": "CANCELLED"}

    stage = "REPORTING"
    logger.info("[run_id=%s] Stage changed to REPORTING", run_id)
    await update_run_in_db(run_id, status=stage, db_url=db_url)
    await cache_run_status(run_id, status=stage, stage=stage)
    await update_live_progress(run_id, stage=stage)

    from sqlalchemy import select

    from app.agent.report import generate_run_report
    from app.models.test_run import TestResult

    session_factory = get_async_session_factory(db_url)
    async with session_factory() as session:
        tc_stmt = select(TestCase).where(TestCase.run_id == run_id).order_by(TestCase.order_index)
        tcs = (await session.execute(tc_stmt)).scalars().all()
        tcs_data = [{"id": str(tc.id), "status": tc.status, "title": tc.title} for tc in tcs]

        res_stmt = (
            select(TestResult)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .where(TestCase.run_id == run_id)
        )
        results = (await session.execute(res_stmt)).scalars().all()
        results_data = [{"status": r.status, "test_case_id": str(r.test_case_id)} for r in results]

    report_data = generate_run_report(
        test_cases=tcs_data,
        results=results_data,
        failures=state.get("failures", []),
    )

    await update_run_in_db(run_id, report=report_data, db_url=db_url)

    return {
        "current_stage": "REPORTING",
        "status": "REPORTING",
        "report": report_data,
    }


async def complete_node(state: AgentState) -> dict[str, Any]:
    """Final node: Marks run as COMPLETED with timestamp, or FAILED if authentication blocked."""
    run_id = uuid.UUID(state["run_id"])
    project_id = uuid.UUID(state["project_id"])
    db_url = state.get("db_url")
    now = datetime.now(timezone.utc)

    results = state.get("results", [])
    auth_aborted = state.get("auth_aborted", False)
    llm_aborted = state.get("llm_aborted", False)
    all_blocked = bool(results) and all(
        r.get("status") == "BLOCKED" for r in results
    )

    if auth_aborted or llm_aborted or all_blocked:
        status = "FAILED"
        err_msg = state.get("abort_message") or (
            "Authentication or LLM provider failure for all executed tests."
        )
        logger.info("[run_id=%s] Stage changed to %s (error=%s)", run_id, status, err_msg)
        await update_run_in_db(
            run_id,
            status=status,
            completed_at=now,
            error_message=err_msg,
            db_url=db_url,
        )
        await cache_run_status(run_id, status=status, stage=status, error=err_msg)
        await update_live_progress(run_id, stage=status)
        await release_run_lock(project_id)
        return {
            "current_stage": status,
            "status": status,
            "error_message": err_msg,
        }

    status = "COMPLETED"
    logger.info("[run_id=%s] Stage changed to %s", run_id, status)
    await update_run_in_db(run_id, status=status, completed_at=now, db_url=db_url)
    await cache_run_status(run_id, status=status, stage=status)
    await update_live_progress(run_id, stage=status)
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
    logger.info("[run_id=%s] Stage changed to %s", run_id, status)

    await update_run_in_db(
        run_id, status=status, completed_at=now, cancel_requested=True, db_url=db_url
    )
    await cache_run_status(run_id, status=status, stage=status)
    await update_live_progress(run_id, stage=status)

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


_active_mcp_clients: dict[uuid.UUID, Any] = {}
_active_test_keys: dict[uuid.UUID, str] = {}


async def _finalize_run(
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    db_url: Optional[str] = None,
    exit_status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Guaranteed clean finalization for test runs on ANY exit.

    Protected against cancellation via asyncio.shield.
    """
    logger.info("[run_id=%s] Running clean finalizer (exit_status=%s)", run_id, exit_status)
    _active_test_keys.pop(run_id, None)

    # 1. Shut down any active MCP client / Chromium child process
    client = _active_mcp_clients.pop(run_id, None)
    if client:
        try:
            await client.close()
        except Exception as e:
            logger.warning("[run_id=%s] Failed to close MCP client in finalizer: %s", run_id, e)

    # 2. Check if user requested cancellation
    user_cancelled = False
    try:
        user_cancelled = await is_cancel_flag_set(run_id)
    except Exception:
        pass

    session_factory = get_async_session_factory(db_url)
    now = datetime.now(timezone.utc)

    # 3. Update database state
    try:
        async with session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == run_id)
            run = (await session.execute(stmt)).scalar_one_or_none()
            if run:
                is_terminal = run.status in ("COMPLETED", "FAILED", "CANCELLED")

                if not is_terminal or exit_status:
                    if user_cancelled or exit_status == "CANCELLED":
                        final_status = "CANCELLED"
                        final_err = error_message or "Run cancelled by user"
                    else:
                        final_status = "FAILED"
                        final_err = error_message or "Worker was interrupted"

                    run.status = final_status
                    run.error_message = final_err
                    run.completed_at = now
                    run.cancel_requested = (final_status == "CANCELLED")

                # Mark test cases that never finished as BLOCKED
                tc_stmt = (
                    select(TestCase).where(TestCase.run_id == run_id).order_by(TestCase.order_index)
                )
                tcs = (await session.execute(tc_stmt)).scalars().all()
                for tc in tcs:
                    if tc.status not in ("PASSED", "FAILED", "BLOCKED"):
                        tc.status = "BLOCKED"
                        session.add(tc)

                # Ensure a TestResult exists for every test case
                res_stmt = (
                    select(TestResult)
                    .join(TestCase, TestResult.test_case_id == TestCase.id)
                    .where(TestCase.run_id == run_id)
                )
                existing_results = (await session.execute(res_stmt)).scalars().all()
                existing_tc_ids = {r.test_case_id for r in existing_results}

                for tc in tcs:
                    if tc.id not in existing_tc_ids:
                        blocked_res = TestResult(
                            test_case_id=tc.id,
                            status="BLOCKED",
                            error_message="Test did not finish before run terminated",
                        )
                        session.add(blocked_res)
                        existing_results.append(blocked_res)

                # Build and store partial report if not already generated
                if not run.report:
                    from app.agent.report import generate_run_report

                    tcs_data = [
                        {"id": str(tc.id), "status": tc.status, "title": tc.title}
                        for tc in tcs
                    ]
                    results_data = [
                        {"status": r.status, "test_case_id": str(r.test_case_id)}
                        for r in existing_results
                    ]
                    run.report = generate_run_report(
                        test_cases=tcs_data, results=results_data, failures=[]
                    )

                session.add(run)
                await session.commit()

                # Update Redis status cache
                await cache_run_status(
                    run_id,
                    status=run.status,
                    stage=run.status,
                    error=run.error_message,
                )
            elif exit_status:
                if user_cancelled or exit_status == "CANCELLED":
                    final_status = "CANCELLED"
                    final_err = error_message or "Run cancelled by user"
                else:
                    final_status = exit_status
                    final_err = error_message or "Worker was interrupted"
                await update_run_in_db(
                    run_id,
                    status=final_status,
                    error_message=final_err,
                    completed_at=now,
                    cancel_requested=(final_status == "CANCELLED"),
                    db_url=db_url,
                )
                await cache_run_status(
                    run_id,
                    status=final_status,
                    stage=final_status,
                    error=final_err,
                )
    except Exception as e:
        logger.error("[run_id=%s] Error updating DB in finalizer: %s", run_id, e)

    # 4. Release Redis run lock
    try:
        await release_run_lock(project_id)
    except Exception as e:
        logger.warning("[run_id=%s] Failed to release run lock in finalizer: %s", run_id, e)

    # 5. Clear Redis live progress keys
    try:
        await clear_live_progress_keys(run_id)
    except Exception as e:
        logger.warning("[run_id=%s] Failed to clear live progress keys in finalizer: %s", run_id, e)


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

    logger.info("[run_id=%s] Agent run started for project %s", run_id, project_id)
    settings = get_settings()
    exit_status = None
    err_msg = None

    start_monotonic = time.monotonic()
    deadline = start_monotonic + float(settings.RUN_TIMEOUT_SECONDS)
    active_stage = "QUEUED"

    stop_heartbeat = asyncio.Event()

    async def _heartbeat_loop() -> None:
        while not stop_heartbeat.is_set():
            try:
                await set_worker_heartbeat(run_id, ttl=60)
            except Exception as e:
                logger.debug("[run_id=%s] Failed to write heartbeat: %s", run_id, e)
            try:
                await asyncio.wait_for(stop_heartbeat.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                pass

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        # Check if forced failure requested for testing T8.3
        if force_fail_at == "start":
            raise RuntimeError("Forced node exception during execution")

        async def _stream_graph():
            nonlocal active_stage
            active_stage = "PLANNING"
            async for output in graph.astream(initial_state, config=config):
                for node_name in output:
                    if node_name == "plan":
                        active_stage = "EXECUTING"
                    elif node_name == "execute":
                        active_stage = "ANALYZING"
                    elif node_name == "analyze":
                        active_stage = "REPORTING"
                    elif node_name == "report":
                        active_stage = "COMPLETED"
                if force_fail_at == "midway":
                    raise RuntimeError("Forced node exception midway through execution")

        await asyncio.wait_for(_stream_graph(), timeout=float(settings.RUN_TIMEOUT_SECONDS))

    except (asyncio.TimeoutError, TimeoutError) as exc:
        now_mono = time.monotonic()
        if now_mono >= (deadline - 0.1):
            exit_status = "FAILED"
            err_msg = f"Run exceeded the time limit of {settings.RUN_TIMEOUT_SECONDS} seconds"
            logger.error("[run_id=%s] %s", run_id, err_msg)
        else:
            exit_status = "FAILED"
            active_tc_key = _active_test_keys.get(run_id)
            err_msg = format_run_failure_message(
                stage=active_stage,
                exc=exc,
                test_key=active_tc_key,
            )
            tb_str = traceback.format_exc()
            clean_tb = sanitize_secret_values(tb_str)
            logger.error("[run_id=%s] %s\n%s", run_id, err_msg, clean_tb)
    except asyncio.CancelledError:
        logger.warning("[run_id=%s] Execution cancelled", run_id)
        is_user_cancel = False
        try:
            is_user_cancel = await is_cancel_flag_set(run_id)
        except Exception:
            pass
        if is_user_cancel:
            exit_status = "CANCELLED"
            err_msg = "Run cancelled by user"
        else:
            exit_status = "FAILED"
            err_msg = "Worker was interrupted"
    except Exception as exc:
        is_user_cancel = False
        try:
            is_user_cancel = await is_cancel_flag_set(run_id)
        except Exception:
            pass
        if is_user_cancel:
            exit_status = "CANCELLED"
            err_msg = "Run cancelled by user"
        else:
            exit_status = "FAILED"
            active_tc_key = _active_test_keys.get(run_id)
            err_msg = format_run_failure_message(
                stage=active_stage,
                exc=exc,
                test_key=active_tc_key,
            )
            tb_str = traceback.format_exc()
            clean_tb = sanitize_secret_values(tb_str)
            logger.error("[run_id=%s] %s\n%s", run_id, err_msg, clean_tb)
    finally:
        stop_heartbeat.set()
        try:
            await heartbeat_task
        except Exception:
            pass

        await asyncio.shield(
            _finalize_run(
                run_id=run_id,
                project_id=project_id,
                db_url=db_url,
                exit_status=exit_status,
                error_message=err_msg,
            )
        )
        logger.info(
            "[run_id=%s] Agent run finished. Total live LLM calls: %d",
            run_id,
            get_live_call_count(),
        )

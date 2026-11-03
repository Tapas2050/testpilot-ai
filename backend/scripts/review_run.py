"""Run review script (evaluation tool, read-only).

Reviews test run details from the TestPilot database and compares against ground truth.
Uses read-only SELECTs only and NEVER prints or accesses secrets.

NOTE: The expectation mapping for --expect-supportdesk-defects is strictly for
evaluating the SupportDesk demo against known ground truth. It MUST NEVER be used
by the agent planning, execution, or analysis logic.
"""

import argparse
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_async_session_factory  # noqa: E402
from app.models.test_run import TestCase, TestRun  # noqa: E402

# SupportDesk planted defect requirements (DEMO EVALUATION ONLY - DO NOT USE IN AGENT LOGIC)
SUPPORTDESK_PLANTED_DEFECT_REQS = {
    "REQ-SEC-02": "Agent Deletion Prohibition",
    "REQ-TKT-02": "High Priority Persistence",
    "REQ-SRCH-01": "Ticket ID Search",
}


def format_duration(started: Optional[datetime], completed: Optional[datetime]) -> str:
    """Format duration between start and completion times."""
    if not started or not completed:
        return "N/A"
    seconds = int((completed - started).total_seconds())
    if seconds < 0:
        return "0s"
    mins, secs = divmod(seconds, 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


async def fetch_review_data(
    session: AsyncSession,
    run_id: Optional[uuid.UUID] = None,
) -> Optional[dict[str, Any]]:
    """Fetch run review details using read-only SELECT queries."""
    if run_id:
        stmt = (
            select(TestRun)
            .options(selectinload(TestRun.test_cases).selectinload(TestCase.results))
            .where(TestRun.id == run_id)
        )
        run = (await session.execute(stmt)).scalar_one_or_none()
    else:
        # Default: latest finished run, or latest run if none finished
        stmt = (
            select(TestRun)
            .options(selectinload(TestRun.test_cases).selectinload(TestCase.results))
            .where(TestRun.status.in_(["COMPLETED", "FAILED", "CANCELLED"]))
            .order_by(TestRun.created_at.desc())
        )
        run = (await session.execute(stmt)).scalars().first()
        if not run:
            stmt_any = (
                select(TestRun)
                .options(selectinload(TestRun.test_cases).selectinload(TestCase.results))
                .order_by(TestRun.created_at.desc())
            )
            run = (await session.execute(stmt_any)).scalars().first()

    if not run:
        return None

    # Calculate run duration
    duration_str = format_duration(run.started_at, run.completed_at)
    if duration_str == "N/A" and run.created_at and run.completed_at:
        duration_str = format_duration(run.created_at, run.completed_at)

    # Live LLM calls count from report
    live_llm_calls = 0
    if run.report and isinstance(run.report, dict):
        live_llm_calls = run.report.get("live_llm_calls", 0)

    # Order test cases
    sorted_tcs = sorted(run.test_cases, key=lambda t: t.order_index)
    min_order = min((t.order_index for t in sorted_tcs), default=0)

    tests_data = []
    for tc in sorted_tcs:
        test_key = getattr(tc, "test_key", None)
        if not test_key:
            test_key = f"TC-{tc.order_index}" if min_order == 1 else f"TC-{tc.order_index + 1}"
        elif min_order == 1 and test_key == f"TC-{tc.order_index + 1}":
            test_key = f"TC-{tc.order_index}"

        # Fetch latest result
        results = tc.results or []
        res = results[0] if results else None

        final_status = res.status if res else tc.status
        steps = res.steps if res and res.steps else []
        step_count = len(steps)

        # Extract final observation
        final_obs = None
        if steps:
            for s in reversed(steps):
                obs = s.get("observation")
                if obs and str(obs).strip():
                    final_obs = str(obs).strip()
                    break
        if not final_obs and res and res.error_message:
            final_obs = res.error_message
        if not final_obs:
            final_obs = tc.description or "No observation recorded"

        # Truncate final observation to 160 characters
        if len(final_obs) > 160:
            final_obs = final_obs[:157] + "..."

        # Check screenshot presence
        has_screenshot = False
        if res:
            p = getattr(res, "screenshot_path", None)
            fp = getattr(res, "failure_screenshot_path", None)
            if p or fp:
                has_screenshot = True

        tests_data.append({
            "test_key": test_key,
            "title": tc.title,
            "target_role": tc.target_role or "N/A",
            "source_requirement": tc.source_requirement or "N/A",
            "final_status": final_status,
            "step_count": step_count,
            "final_observation": final_obs,
            "screenshot_present": "yes" if has_screenshot else "no",
        })

    return {
        "run_id": str(run.id),
        "status": run.status,
        "duration": duration_str,
        "live_llm_calls": live_llm_calls,
        "tests_planned": len(sorted_tcs),
        "tests": tests_data,
    }


def format_review_text(data: dict[str, Any], expect_defects: bool = False) -> str:
    """Format review data as human-readable text."""
    lines = []
    lines.append("=" * 80)
    lines.append("                         TESTPILOT RUN REVIEW")
    lines.append("=" * 80)
    lines.append(f"Run ID:             {data['run_id']}")
    lines.append(f"Status:             {data['status']}")
    lines.append(f"Duration:           {data['duration']}")
    lines.append(f"Live LLM Calls:     {data['live_llm_calls']}")
    lines.append(f"Tests Planned:      {data['tests_planned']}")
    lines.append("=" * 80)

    lines.append(
        f"{'Key':<6} {'Role':<8} {'Requirement':<14} {'Status':<8} "
        f"{'Steps':<6} {'Screen':<7} {'Final Observation'}"
    )
    lines.append("-" * 80)

    for t in data["tests"]:
        lines.append(
            f"{t['test_key']:<6} {t['target_role']:<8} {t['source_requirement']:<14} "
            f"{t['final_status']:<8} {t['step_count']:<6} {t['screenshot_present']:<7} "
            f"{t['final_observation']}"
        )

    if expect_defects:
        lines.append("")
        lines.append("=" * 80)
        lines.append("       SUPPORTDESK GROUND TRUTH EVALUATION (SUPPORTDESK_DEFECTS=on)")
        lines.append("=" * 80)
        lines.append(
            f"{'Key':<6} {'Requirement':<14} {'Expected':<10} {'Actual':<10} {'Verdict':<8}"
        )
        lines.append("-" * 80)

        matches = 0
        total_eval = 0
        found_defects = set()

        for t in data["tests"]:
            req = t["source_requirement"]
            is_defect_req = req in SUPPORTDESK_PLANTED_DEFECT_REQS
            expected = "FAILED" if is_defect_req else "PASSED"
            actual = t["final_status"]
            is_match = (actual == expected)
            verdict = "MATCH" if is_match else "MISMATCH"

            if is_match:
                matches += 1
            total_eval += 1

            if is_defect_req and actual == "FAILED":
                found_defects.add(req)

            lines.append(
                f"{t['test_key']:<6} {req:<14} {expected:<10} {actual:<10} {verdict:<8}"
            )

        lines.append("-" * 80)
        defects_found_count = len(found_defects)
        total_defects = len(SUPPORTDESK_PLANTED_DEFECT_REQS)
        lines.append(f"Defects found: {defects_found_count} of {total_defects}")
        for req_id, name in SUPPORTDESK_PLANTED_DEFECT_REQS.items():
            status_text = "FOUND (FAILED)" if req_id in found_defects else "MISSED (not FAILED)"
            lines.append(f"  - {req_id} ({name}): {status_text}")
        lines.append(f"Total requirements matched: {matches} of {total_eval}")
        lines.append("=" * 80)

    return "\n".join(lines)


def format_review_markdown(data: dict[str, Any], expect_defects: bool = False) -> str:
    """Format review data as GitHub Flavored Markdown."""
    lines = []
    lines.append(f"# TestPilot Run Review — `{data['run_id']}`\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Status** | `{data['status']}` |")
    lines.append(f"| **Duration** | {data['duration']} |")
    lines.append(f"| **Live LLM Calls** | {data['live_llm_calls']} |")
    lines.append(f"| **Tests Planned** | {data['tests_planned']} |\n")

    lines.append("## Test Case Execution Summary\n")
    lines.append("| Key | Role | Requirement | Status | Steps | Screenshots | Final Observation |")
    lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|---|")

    for t in data["tests"]:
        obs_escaped = t["final_observation"].replace("|", "\\|")
        lines.append(
            f"| `{t['test_key']}` | `{t['target_role']}` | `{t['source_requirement']}` | "
            f"**{t['final_status']}** | {t['step_count']} | {t['screenshot_present']} | "
            f"{obs_escaped} |"
        )

    if expect_defects:
        lines.append("\n## SupportDesk Ground Truth Evaluation\n")
        lines.append("| Key | Requirement | Expected | Actual | Ground Truth Verdict |")
        lines.append("|:---:|:---:|:---:|:---:|:---:|")

        matches = 0
        total_eval = 0
        found_defects = set()

        for t in data["tests"]:
            req = t["source_requirement"]
            is_defect_req = req in SUPPORTDESK_PLANTED_DEFECT_REQS
            expected = "FAILED" if is_defect_req else "PASSED"
            actual = t["final_status"]
            is_match = (actual == expected)
            verdict = "✅ MATCH" if is_match else "❌ MISMATCH"

            if is_match:
                matches += 1
            total_eval += 1

            if is_defect_req and actual == "FAILED":
                found_defects.add(req)

            lines.append(
                f"| `{t['test_key']}` | `{req}` | `{expected}` | `{actual}` | {verdict} |"
            )

        defects_found_count = len(found_defects)
        total_defects = len(SUPPORTDESK_PLANTED_DEFECT_REQS)
        lines.append(f"\n> **Defects Detected**: {defects_found_count} of {total_defects}")
        for req_id, name in SUPPORTDESK_PLANTED_DEFECT_REQS.items():
            status_text = "✅ **FOUND** (`FAILED`)" if req_id in found_defects else "❌ **MISSED**"
            lines.append(f"> - `{req_id}` ({name}): {status_text}")
        lines.append(f"> \n> **Total Requirements Aligned**: {matches} of {total_eval}")

    return "\n".join(lines)


async def run_review(
    run_id: Optional[uuid.UUID] = None,
    expect_defects: bool = False,
    db_url: Optional[str] = None,
    as_markdown: bool = False,
) -> int:
    """Execute review and print results."""
    settings = get_settings()
    url = db_url or settings.DATABASE_URL
    session_factory = get_async_session_factory(url)

    async with session_factory() as session:
        data = await fetch_review_data(session, run_id=run_id)
        if not data:
            print("No matching test run found in database.")
            return 1

        if as_markdown:
            output = format_review_markdown(data, expect_defects=expect_defects)
        else:
            output = format_review_text(data, expect_defects=expect_defects)
        print(output)
        return 0


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Read-only review of TestPilot test runs and evaluation comparison."
    )
    parser.add_argument(
        "run_id",
        nargs="?",
        default=None,
        help="UUID of test run to inspect (default: latest finished run)",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id_opt",
        default=None,
        help="UUID of test run to inspect (alternative to positional argument)",
    )
    parser.add_argument(
        "--expect-supportdesk-defects",
        action="store_true",
        help="Compare verdicts against SupportDesk ground truth (SUPPORTDESK_DEFECTS=on)",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output review as GitHub Flavored Markdown",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Optional database URL override",
    )

    args = parser.parse_args(argv)
    target_id_str = args.run_id or args.run_id_opt
    target_uuid = None
    if target_id_str:
        try:
            target_uuid = uuid.UUID(target_id_str)
        except ValueError:
            print(f"Error: Invalid run_id UUID '{target_id_str}'")
            return 1

    return asyncio.run(
        run_review(
            run_id=target_uuid,
            expect_defects=args.expect_supportdesk_defects,
            db_url=args.db_url,
            as_markdown=args.markdown,
        )
    )


if __name__ == "__main__":
    sys.exit(main())

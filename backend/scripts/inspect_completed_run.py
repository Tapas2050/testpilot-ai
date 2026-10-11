"""Read-only inspection of the most recent COMPLETED test run in the TestPilot database."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402

from app.agent.executor import sanitize_steps  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import get_async_session_factory  # noqa: E402
from app.models.test_run import TestCase, TestResult, TestRun  # noqa: E402


async def inspect_most_recent_completed_run() -> None:
    settings = get_settings()
    session_factory = get_async_session_factory(settings.DATABASE_URL)

    async with session_factory() as session:
        stmt = (
            select(TestRun)
            .where(TestRun.status == "COMPLETED")
            .order_by(TestRun.created_at.desc())
        )
        run = (await session.execute(stmt)).scalars().first()

        if not run:
            print("No COMPLETED run found in database.")
            all_stmt = select(TestRun).order_by(TestRun.created_at.desc())
            runs = (await session.execute(all_stmt)).scalars().all()
            print(f"Total runs found: {len(runs)}")
            for r in runs[:5]:
                print(f"  Run {r.id}: status={r.status}, error={r.error_message}")
            return

        print(f"=== Most Recent COMPLETED Run: {run.id} ===")
        print(f"Project ID: {run.project_id}")
        print(f"Created At: {run.created_at}")
        print(f"Completed At: {run.completed_at}")
        print(f"Error Message: {run.error_message}")

        tc_stmt = (
            select(TestCase)
            .where(TestCase.run_id == run.id)
            .order_by(TestCase.order_index)
        )
        test_cases = (await session.execute(tc_stmt)).scalars().all()
        print(f"\nTotal Test Cases: {len(test_cases)}\n")

        for tc in test_cases:
            res_stmt = (
                select(TestResult)
                .where(TestResult.test_case_id == tc.id)
                .order_by(TestResult.id.desc())
            )
            res = (await session.execute(res_stmt)).scalars().first()

            status = res.status if res else tc.status
            err_msg = res.error_message if res else None
            steps = res.steps if res and res.steps else []

            print("--------------------------------------------------")
            print(f"Test #{tc.order_index}: {tc.title}")
            print(f"ID: {tc.id}")
            print(f"Role: {tc.target_role}")
            print(f"Source Requirement: {tc.source_requirement}")
            print(f"Final Status: {status}")
            print(f"Error Message: {err_msg or 'None'}")

            clean_steps = sanitize_steps(steps, [])
            last_5 = clean_steps[-5:] if clean_steps else []
            print(f"Total Steps: {len(steps)}, Showing Last {len(last_5)}:")
            for s in last_5:
                step_copy = dict(s)
                step_copy.pop("page_text", None)
                step_copy.pop("screenshot", None)
                action = step_copy.get("action")
                st = step_copy.get("status")
                detail = step_copy.get("observation") or step_copy.get("error") or ""
                print(f"  - Step {step_copy.get('step')}: {action} | status={st} | {detail}")


if __name__ == "__main__":
    asyncio.run(inspect_most_recent_completed_run())

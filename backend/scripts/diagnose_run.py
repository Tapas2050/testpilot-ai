"""Read-only inspection of run 85109bf4-7983-405b-baa6-b7074bb717e9."""

import asyncio
import sys
import uuid
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_async_session_factory  # noqa: E402
from app.models.test_run import Failure, TestCase, TestResult, TestRun  # noqa: E402

TARGET_RUN_ID = uuid.UUID("85109bf4-7983-405b-baa6-b7074bb717e9")


async def main():
    settings = get_settings()
    session_factory = get_async_session_factory(settings.DATABASE_URL)

    async with session_factory() as session:
        stmt = select(TestRun).where(TestRun.id == TARGET_RUN_ID)
        run = (await session.execute(stmt)).scalar_one_or_none()
        if not run:
            print(f"Run {TARGET_RUN_ID} not found!")
            return

        print(f"=== TestRun: {run.id} ===")
        print(f"Status: {run.status}")
        print(f"Started At: {run.started_at}")
        print(f"Completed At: {run.completed_at}")
        print(f"Error Message: {run.error_message}")
        print(f"Report JSON present: {bool(run.report)}")
        if run.report:
            print(f"Report keys: {list(run.report.keys())}")
            print(f"Report failures count: {len(run.report.get('failures', []))}")
            for idx, f in enumerate(run.report.get('failures', [])):
                print(f"  Report failure #{idx}: {list(f.keys())}")
                print(f"    title: {f.get('title')}")
                print(f"    expected: {repr(f.get('expected'))}")
                print(f"    observed: {repr(f.get('observed'))}")
                expl = repr(f.get('explanation') or f.get('root_cause'))
                print(f"    root_cause/explanation: {expl}")
                print(f"    suggested_action: {repr(f.get('suggested_action'))}")

        # Fetch TestCases
        tc_stmt = (
            select(TestCase)
            .where(TestCase.run_id == TARGET_RUN_ID)
            .order_by(TestCase.order_index)
        )
        tcs = (await session.execute(tc_stmt)).scalars().all()
        print(f"\nTotal TestCases: {len(tcs)}")

        for tc in tcs:
            print(f"\n--- TestCase #{tc.order_index}: {tc.title} ({tc.id}) ---")
            print(f"Role: {tc.target_role}, Req: {tc.source_requirement}, Status: {tc.status}")
            print(f"Description: {tc.description}")

            # TestResult
            res_stmt = (
                select(TestResult)
                .where(TestResult.test_case_id == tc.id)
                .order_by(TestResult.id.desc())
            )
            results = (await session.execute(res_stmt)).scalars().all()
            print(f"TestResults count: {len(results)}")
            for res in results:
                steps_len = len(res.steps) if res.steps else 0
                print(
                    f"  Result ID: {res.id}, Status: {res.status}, "
                    f"Duration: {res.duration_seconds}s"
                )
                print(f"  Screenshot Path: {repr(res.screenshot_path)}")
                print(f"  Error Message: {repr(res.error_message)}")
                print(f"  Steps Count: {steps_len}")
                if res.steps:
                    for s in res.steps[:3]:
                        target = repr(s.get('selector') or s.get('url'))
                        print(
                            f"    Step {s.get('step')}: {s.get('action')} "
                            f"on {target} -> status={s.get('status')}"
                        )
                    if steps_len > 3:
                        print(f"    ... and {steps_len - 3} more steps")

            # Failures table
            fail_stmt = select(Failure).where(Failure.test_case_id == tc.id)
            fails = (await session.execute(fail_stmt)).scalars().all()
            print(f"Failures count: {len(fails)}")
            for fail in fails:
                print(f"  Failure ID: {fail.id}")
                print(f"  Classification: {fail.classification}")
                print(f"  Severity: {fail.severity}, Confidence: {fail.confidence}")
                print(f"  Expected: {repr(fail.expected)}")
                print(f"  Observed: {repr(fail.observed)}")
                print(f"  Explanation: {repr(fail.explanation)}")
                print(f"  Suggested Action: {repr(fail.suggested_action)}")


if __name__ == "__main__":
    asyncio.run(main())

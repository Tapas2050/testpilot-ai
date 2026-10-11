from datetime import datetime, timezone
from typing import Any, Optional


def generate_run_report(
    test_cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    live_llm_calls: Optional[int] = None,
) -> dict[str, Any]:
    """Generate final JSON report with totals, pass percentage, and failure breakdowns."""
    total = len(test_cases)
    passed = sum(1 for r in results if r.get("status") == "PASSED")
    failed = sum(1 for r in results if r.get("status") == "FAILED")

    # Math-sound pass percentage (T11.3)
    pass_pct = round((passed / total) * 100.0, 2) if total > 0 else 0.0

    # Categorize breakdowns
    classification_counts: dict[str, int] = {
        "PRODUCT_BUG": 0,
        "TEST_FAILURE": 0,
        "AUTHENTICATION_FAILURE": 0,
        "ENVIRONMENT_FAILURE": 0,
        "FLAKY_TEST": 0,
    }
    severity_counts: dict[str, int] = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    for f in failures:
        cls_name = f.get("classification", "PRODUCT_BUG")
        if cls_name in classification_counts:
            classification_counts[cls_name] += 1
        sev_name = f.get("severity", "MEDIUM")
        if sev_name in severity_counts:
            severity_counts[sev_name] += 1

    # AI summary analysis text
    if failed == 0:
        summary_text = (
            f"All {total} planned test scenarios passed successfully. "
            f"Zero product defects or regressions were detected."
        )
    else:
        product_bugs = classification_counts.get("PRODUCT_BUG", 0)
        summary_text = (
            f"Test execution identified {failed} failed test(s) out of {total} total tests "
            f"({pass_pct}% pass rate). {product_bugs} issue(s) were classified as confirmed "
            f"PRODUCT_BUGs requiring engineering attention."
        )

    if live_llm_calls is not None:
        summary_text += f" Total live LLM calls: {live_llm_calls}."

    return {
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": failed,
        "pass_percentage": pass_pct,
        "pass_rate": pass_pct,
        "summary": summary_text,
        "classification_breakdown": classification_counts,
        "severity_breakdown": severity_counts,
        "failures": failures,
        "test_cases": test_cases,
        "results": results,
        "live_llm_calls": live_llm_calls if live_llm_calls is not None else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


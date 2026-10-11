"""Failure Analyst Agent: Classifies failed test cases into 5 standard categories."""

import logging
from typing import Any, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from app.agent.llm import enforce_rate_limit, get_llm

logger = logging.getLogger(__name__)

FailureClassification = Literal[
    "PRODUCT_BUG",
    "TEST_FAILURE",
    "AUTHENTICATION_FAILURE",
    "ENVIRONMENT_FAILURE",
    "FLAKY_TEST",
]

FailureSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class FailureAnalysisOutput(BaseModel):
    """Structured classification output produced by the Failure Analyst."""

    classification: FailureClassification = Field(
        description="Root cause category of the test failure"
    )
    severity: FailureSeverity = Field(description="Severity level of the defect or failure")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    expected: str = Field(min_length=1, description="Expected behavior per requirement")
    observed: str = Field(min_length=1, description="Observed behavior during browser test")
    explanation: str = Field(min_length=1, description="Detailed explanation of root cause")
    suggested_action: str = Field(
        min_length=1,
        description="Recommended action to remediate defect or fix agent planning",
    )


ANALYST_SYSTEM_PROMPT = """You are TestPilot AI's autonomous Failure Analyst agent.
Analyze the failed browser test case and categorize the root cause.

CRITICAL INSTRUCTIONS:
1. There are NO test scripts in TestPilot AI (tests are executed autonomously).
   NEVER tell the user or engineering team to "update the test script" or "fix the test script".
2. PRODUCT_BUG means the target application violated a requirement or specification
   (e.g., unauthorized role allowed to delete, invalid persistence, broken search).
   The suggested action must be about fixing or patching the APPLICATION code.
3. TEST_FAILURE means the testing agent made a mistake (e.g. invalid selector, empty target,
   misunderstood the page UI, or took an erroneous step).
   The suggested action must be about improving agent execution or planning, NOT the application.
4. AUTHENTICATION_FAILURE means target credentials or login flows were rejected.
5. ENVIRONMENT_FAILURE means the target server crashed, timed out, or connection failed.
6. FLAKY_TEST means transient timing or animation race condition.

Allowed Classifications:
PRODUCT_BUG, TEST_FAILURE, AUTHENTICATION_FAILURE, ENVIRONMENT_FAILURE, FLAKY_TEST.
Allowed Severities: LOW, MEDIUM, HIGH, CRITICAL.

You must provide a non-empty explanation and a clear, actionable suggested action."""


def build_deterministic_expected(
    title: str,
    description: Optional[str] = None,
    source_requirement: Optional[str] = None,
    expected_result: Optional[str] = None,
    checks: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Deterministically construct expected behavior statement from requirement facts."""
    if expected_result and expected_result.strip():
        return expected_result.strip()
    if checks and len(checks) > 0:
        chk_strs = [
            c.get("description") or c.get("check_id")
            for c in checks
            if c.get("description") or c.get("check_id")
        ]
        if chk_strs:
            req_prefix = f"[{source_requirement}] " if source_requirement else ""
            return f"{req_prefix}{'; '.join(chk_strs)}"
    if description and description.strip():
        req_prefix = f"[{source_requirement}] " if source_requirement else ""
        return f"{req_prefix}{description.strip()}"
    req_prefix = f"[{source_requirement}] " if source_requirement else ""
    return f"{req_prefix}Expected {title} to succeed per specifications."


def build_deterministic_observed(
    steps: list[dict[str, Any]],
    error_message: Optional[str] = None,
) -> str:
    """Deterministically construct observed behavior statement from executor facts."""
    final_obs = None
    evidence_quote = None
    last_url = None
    last_text = None

    for s in reversed(steps or []):
        if not evidence_quote and s.get("evidence"):
            evidence_quote = s.get("evidence")
        if not last_url and s.get("url"):
            last_url = s.get("url")
        if not last_text and (s.get("observation") or s.get("thought")):
            last_text = s.get("observation") or s.get("thought")
        act = s.get("action")
        if not final_obs and act in ("finish", "loop_detected") and s.get("observation"):
            final_obs = s.get("observation")

    parts = []
    if final_obs:
        parts.append(final_obs)
    elif error_message:
        parts.append(error_message)
    elif last_text:
        parts.append(last_text[:150])
    else:
        parts.append("Test scenario concluded with failure")

    if evidence_quote:
        parts.append(f"Evidence: '{evidence_quote}'")
    if last_url:
        parts.append(f"Last URL: {last_url}")

    return ". ".join(p.rstrip(".") for p in parts) + "."


async def analyze_test_failure(
    title: str,
    description: Optional[str],
    source_requirement: Optional[str],
    target_role: Optional[str],
    steps: list[dict[str, Any]],
    error_message: Optional[str],
    expected_result: Optional[str] = None,
    checks: Optional[list[dict[str, Any]]] = None,
) -> FailureAnalysisOutput:
    """Analyze a failed test case and produce a structured diagnosis."""
    # Deterministic expected & observed behaviors (Part 3a)
    exp = build_deterministic_expected(
        title=title,
        description=description,
        source_requirement=source_requirement,
        expected_result=expected_result,
        checks=checks,
    )
    obs = build_deterministic_observed(steps=steps, error_message=error_message)

    # Failures that skip the LLM (Part 3b)
    err_lower = (error_message or "").lower()
    if "execution loop detected" in err_lower or "loop detected" in err_lower:
        return FailureAnalysisOutput(
            classification="TEST_FAILURE",
            severity="MEDIUM",
            confidence=0.85,
            expected=exp,
            observed=obs,
            explanation=f"Testing agent encountered an execution loop: {error_message}",
            suggested_action="Refine agent actions or selectors to avoid repetitive states.",
        )
    is_timeout = "environment failure" in err_lower or "timed out" in err_lower
    if is_timeout or "tool timeout" in err_lower:
        return FailureAnalysisOutput(
            classification="ENVIRONMENT_FAILURE",
            severity="HIGH",
            confidence=0.9,
            expected=exp,
            observed=obs,
            explanation=f"Test execution halted due to environment failure: {error_message}",
            suggested_action="Verify target app availability and browser environment stability.",
        )
    if "authentication failed" in err_lower or "stored credential" in err_lower:
        return FailureAnalysisOutput(
            classification="AUTHENTICATION_FAILURE",
            severity="CRITICAL",
            confidence=0.95,
            expected=exp,
            observed=obs,
            explanation=f"Authentication blocked test execution: {error_message}",
            suggested_action="Verify project credentials and encryption keys in Settings.",
        )

    # Format execution steps history
    history = "\n".join(
        f"- Step {s.get('step')}: {s.get('action')} on {s.get('selector', s.get('url', ''))} "
        f"-> status={s.get('status')}, obs={s.get('observation', s.get('thought', ''))}"
        for s in steps
    )
    if not history:
        history = "(No steps recorded)"

    user_prompt = f"""Failed Test Case:
Title: {title}
Description: {description or "N/A"}
Source Requirement: {source_requirement or "N/A"}
Target Role: {target_role or "None"}
Expected Behavior: {exp}
Observed Behavior: {obs}
Error Message: {error_message or "None"}

Execution Steps & Observations:
{history}

Please classify this failure, determine severity, and provide root cause analysis."""

    messages = [
        SystemMessage(content=ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    await enforce_rate_limit()
    llm = get_llm(temperature=0.0, structured_schema=FailureAnalysisOutput)

    analysis: Any = None
    try:
        analysis = await llm.ainvoke(messages)
    except Exception as exc:
        logger.warning("Analyst initial invocation error: %s. Retrying once.", exc)
        # Retry once with validation error message (Part 3b)
        retry_prompt = (
            f"Previous output was invalid ({exc}). Return valid output with non-empty "
            f"explanation and suggested_action."
        )
        try:
            analysis = await llm.ainvoke(messages + [HumanMessage(content=retry_prompt)])
        except Exception as retry_exc:
            logger.warning("Analyst retry failed: %s. Fallback to deterministic.", retry_exc)
            analysis = None

    # Validate output
    if isinstance(analysis, dict):
        try:
            analysis = FailureAnalysisOutput.model_validate(analysis)
        except ValidationError:
            analysis = None

    is_invalid = (
        not isinstance(analysis, FailureAnalysisOutput)
        or not analysis.explanation
        or not analysis.suggested_action
    )
    if is_invalid:
        # Fall back to deterministic explanation built from stored facts (Part 3b)
        cls_name = "PRODUCT_BUG" if source_requirement else "TEST_FAILURE"
        action = (
            "Review application backend handler and ensure requirements are enforced."
            if cls_name == "PRODUCT_BUG"
            else "Review agent test plan checks and selectors."
        )
        return FailureAnalysisOutput(
            classification=cls_name,
            severity="MEDIUM",
            confidence=0.5,
            expected=exp,
            observed=obs,
            explanation=f"Execution observed unexpected outcome: {obs} contrary to {exp}.",
            suggested_action=action,
        )

    # Sanitize suggested action: no 'test script' phrasing (Part 3c)
    act_text = analysis.suggested_action
    if "script" in act_text.lower():
        if analysis.classification == "PRODUCT_BUG":
            act_text = "Review and patch application logic to comply with requirement specs."
        else:
            act_text = "Adjust testing agent execution checks and selector definitions."

    return FailureAnalysisOutput(
        classification=analysis.classification,
        severity=analysis.severity,
        confidence=analysis.confidence,
        expected=analysis.expected or exp,
        observed=analysis.observed or obs,
        explanation=analysis.explanation,
        suggested_action=act_text,
    )

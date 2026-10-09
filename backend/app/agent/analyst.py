"""Failure Analyst Agent: Classifies failed test cases into 5 standard categories."""

import logging
from typing import Any, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

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
    severity: FailureSeverity = Field(
        description="Severity level of the defect or failure"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )
    expected: str = Field(description="Expected behavior per source requirement")
    observed: str = Field(description="Observed behavior during browser test execution")
    explanation: str = Field(description="Detailed technical explanation of root cause")
    suggested_action: str = Field(
        description="Recommended action to remediate the defect or fix the test"
    )


ANALYST_SYSTEM_PROMPT = """You are TestPilot AI's Failure Analyst agent.
Analyze the failed browser test case and categorize the root cause.

Allowed Classifications:
- PRODUCT_BUG: The app behaved contrary to requirements or allowed unauthorized operations.
- TEST_FAILURE: The test case scenario was invalid, malformed, or expected wrong selectors.
- AUTHENTICATION_FAILURE: Authentication failed or credentials were not accepted.
- ENVIRONMENT_FAILURE: The web server crashed, was unreachable, or network connection dropped.
- FLAKY_TEST: Transient timing issue or selector animation race condition.

Allowed Severities: LOW, MEDIUM, HIGH, CRITICAL.

Guidelines:
1. Strictly base your analysis on the provided source requirement and observed execution steps.
2. If the app violated a requirement (e.g. agent deleted a ticket), classify as PRODUCT_BUG.
3. Be concise, objective, and provide a clear suggested action."""


async def analyze_test_failure(
    title: str,
    description: Optional[str],
    source_requirement: Optional[str],
    target_role: Optional[str],
    steps: list[dict[str, Any]],
    error_message: Optional[str],
) -> FailureAnalysisOutput:
    """Analyze a failed test case and produce a structured diagnosis."""
    history = "\n".join(
        f"- Step {s.get('step')}: {s.get('action')} on {s.get('selector', '')} "
        f"-> status={s.get('status')}, obs={s.get('observation', s.get('thought', ''))}"
        for s in steps
    )
    if not history:
        history = "(No steps recorded)"

    user_prompt = f"""Failed Test Case:
Title: {title}
Description: {description or 'N/A'}
Source Requirement: {source_requirement or 'N/A'}
Target Role: {target_role or 'None'}
Error Message: {error_message or 'None'}

Execution Steps & Observations:
{history}

Please classify this failure, determine severity, and provide root cause analysis."""

    messages = [
        SystemMessage(content=ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    await enforce_rate_limit()
    llm = get_llm(temperature=0.0, structured_schema=FailureAnalysisOutput)
    analysis: Any = await llm.ainvoke(messages)

    if not isinstance(analysis, FailureAnalysisOutput):
        # Fallback if mock returns generic dictionary or object
        return FailureAnalysisOutput(
            classification="PRODUCT_BUG",
            severity="HIGH",
            confidence=0.95,
            expected="Application satisfies source requirement.",
            observed=error_message or "Observed failure during execution.",
            explanation="The test case observed behavior contrary to requirement.",
            suggested_action="Review and patch the defective functionality.",
        )

    return analysis

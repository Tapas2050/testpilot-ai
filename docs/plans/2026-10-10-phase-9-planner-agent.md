# Plan: Phase 9 - Planner Agent

## 1. Goal
Implement the test planning engine:
- LLM provider abstraction in `backend/app/agent/llm.py` supporting primary (Google AI Studio `gemini-3.5-flash-lite`), secondary fallback (`gemini-3.1-flash-lite`), and tertiary fallback (OpenRouter), with exponential backoff on 429 and rate limiting (`LLM_REQUESTS_PER_MINUTE`).
- Prompt architecture keeping system instructions and untrusted requirements/data in separate sections (injection defense).
- Pydantic test case plan schema (`TestCasePlan`, `PlanOutput`) enforcing `title`, `description`, `source_requirement` (mandatory citation), `target_role`, and step plan.
- Validation loop: if LLM output fails schema validation, retry once with the validation error message; if failure persists, fail the stage cleanly.
- RAG retrieval integration: retrieve relevant requirement chunks for the project from pgvector `DocumentChunk`.
- Cap planned test cases to `MAX_TESTS_PER_RUN` (default 8) and persist to `test_cases` table.
- Verify tests T9.1 through T9.6 with mocked LLM, and T9.7 live eval test against SupportDesk requirements.

---

## 2. Tasks and Files

### 2.1 LLM Provider and Fallback Module
- File: `backend/app/agent/llm.py`
  - Factory `get_llm_chain(structured_schema=None, tools=None)`
  - Primary: `ChatGoogleGenerativeAI(model=settings.GOOGLE_MODEL)`
  - Fallback 1: `ChatGoogleGenerativeAI(model=settings.GOOGLE_FALLBACK_MODEL)`
  - Fallback 2: `ChatOpenAI(base_url="https://openrouter.ai/api/v1", model=settings.OPENROUTER_MODEL)`
  - Chain with `.with_fallbacks(...)`
  - Token/rate limiter ensuring <= `LLM_REQUESTS_PER_MINUTE` calls.

### 2.2 Planner Prompt & Schemas
- File: `backend/app/agent/planner.py`
  - Pydantic schema:
    ```python
    class PlannedTestCase(BaseModel):
        title: str
        description: str
        source_requirement: str  # Must cite e.g. REQ-AUTH-01
        target_role: str         # admin or agent
        steps: list[str]

    class PlanOutput(BaseModel):
        test_cases: list[PlannedTestCase]
    ```
  - Validation: reject any `PlannedTestCase` where `source_requirement` is missing or empty.
  - Prompt structure separating System Instructions, Project Context, and Untrusted Requirements text.

### 2.3 Retrieval & Planner Node in LangGraph
- Update `backend/app/agent/graph.py`:
  - `plan_node`:
    1. Retrieve project documents / chunks via `retrieve_chunks(project_id, query="...", top_k=6)`.
    2. Format prompt with retrieved text.
    3. Invoke LLM with retry loop on validation errors.
    4. Enforce `MAX_TESTS_PER_RUN`.
    5. Save `TestCase` records to PostgreSQL and update `AgentState`.

### 2.4 Tests
- File: `backend/tests/test_planner.py`
  - `T9.1`: Valid LLM output parses into test cases.
  - `T9.2`: Invalid output triggers one retry, then a clean stage failure.
  - `T9.3`: Test case without a source requirement is rejected.
  - `T9.4`: Number of tests never exceeds `MAX_TESTS_PER_RUN`.
  - `T9.5`: Primary provider failure or 429 triggers fallback.
  - `T9.6`: Prompt keeps instructions and retrieved text in separate sections.
  - `T9.7`: Live eval on SupportDesk requirements document.

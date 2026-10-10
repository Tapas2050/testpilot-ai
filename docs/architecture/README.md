# TestPilot AI Architecture Documentation

Welcome to the architectural specifications and developer reference for **TestPilot AI**.

This directory contains a complete, verified, code-grounded architectural review of the entire system. Every diagram, flow, constraint, and assertion is based on the active source code, configuration files, and database schemas in this repository.

---

## Documentation Index & Recommended Reading Order

For engineers, security auditors, or developers onboarding to this codebase, the recommended reading progression is:

### 1. [System Architecture & Deep Dive (ARCHITECTURE.md)](ARCHITECTURE.md)
*Start here for the complete architectural review.*
- **Sections 1–3**: Executive summary, system capabilities, repository layout, and runtime process topology.
- **Sections 4–5**: Complete configuration audit (all environment variables) and relational/vector data models with ER diagram.
- **Sections 7–9**: Authentication/session revocation lifecycle, credential encryption & SSRF defenses, and RAG document ingestion pipeline.
- **Section 10**: **The Run, End-to-End** — step-by-step trace from frontend button click, arq queue, LangGraph nodes, checkpointing, to live polling, including real database JSON payloads.
- **Sections 11–13**: Detailed agent node prompt/guardrail architecture, multi-provider LLM fallback chain, and Playwright MCP browser automation layer.
- **Section 14**: **Honesty Audit of the Executor** — candid technical assessment of autonomous reasoning vs scripted flows, MCP usage, target specificity, and PRD criteria reality.
- **Sections 15–18**: Failure classification engine, React frontend architecture, SupportDesk defect toggle mechanics, and security controls verification.
- **Sections 19–22**: Test suite topology, operations runbook, documentation vs code reality discrepancy audit, and ranked risks.

### 2. [Complete API Reference (ENDPOINTS.md)](ENDPOINTS.md)
*Consult for day-to-day backend development, API integration, and security audits.*
- Covers all 17 REST endpoints grouped by router (`/auth`, `/projects`, `/documents`, `/runs`, `/health`).
- Detail includes HTTP method, path, authentication dependency, ownership validation, rate limits, request/response Pydantic schemas, status codes, service functions, and read/write database actions.

---

## Architectural Principles Enforced in Code

1. **Defense-in-Depth Authentication**: Argon2 password hashing with constant-time dummy verification, database-backed JWT session revocation, and strict tenant ownership checks on every private route.
2. **Deterministic Background Workers**: Distributed task execution via `arq` and Redis, single-concurrency execution (`max_jobs = 1`) to respect host memory limits (D-018), and LangGraph workflow checkpointing in PostgreSQL.
3. **SSRF & Browser Isolation**: Strict IP-range and DNS-resolution blocking for target URLs, allowlist-only Playwright MCP child process communication over stdio, and headless browser sandboxing.
4. **Credential Privacy**: Fernet symmetric encryption at rest for target application passwords, with automated regex scrubbing in test step logs, database error messages, and frontend payloads.

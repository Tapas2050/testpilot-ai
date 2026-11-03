# TestPilot AI — Project Documentation Index

This directory contains the complete technical specifications, architectural decisions, task tracking, testing guides, and memory records for **TestPilot AI**.

---

## Document Map

| Document | Purpose & Scope |
|---|---|
| [`PRD.md`](PRD.md) | **Product Requirements Document**: Problem statement, core user journeys, target personas, non-functional requirements, and acceptance criteria. |
| [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | **Technical Implementation Specification**: Database schema, API contracts, LangGraph state machine, RAG chunking pipeline, and phases 1–13 breakdown. |
| [`DESIGN.md`](DESIGN.md) | **Design & UI System**: Design tokens, component specs, responsive layout patterns, color palettes, and accessibility guidelines. |
| [`RULES.md`](RULES.md) | **Development Rules & Guardrails**: Environment variable names, port assignments, credential redaction policies, and development conventions. |
| [`TASKS.md`](TASKS.md) | **Milestone & Task Tracking**: Granular checklist covering phases 1–14, bug fixes, and hardening milestones. |
| [`DECISIONS.md`](DECISIONS.md) | **Architecture Decision Records (ADRs)**: Decisions D-001 through D-046 recording technical choices, alternatives, and consequences. |
| [`TEST_PLAN.md`](TEST_PLAN.md) | **Quality Assurance & Verification**: Unit, integration, security, and browser ground-truth test specifications. |
| [`SECURITY.md`](SECURITY.md) | **Security Model**: Asset inventory, threat models, SSRF mitigations, credential encryption, and prompt injection defenses. |
| [`MEMORY.md`](MEMORY.md) | **Coding Agent Memory**: Cross-session project state, verified facts, gotchas, lessons learned, and active operational keys. |
| [`INTERVIEW_GUIDE.md`](INTERVIEW_GUIDE.md) | **Technical Deep Dive & Interview Guide**: Comprehensive Q&A covering system architecture, debugging war stories, and design trade-offs. |
| [`UNDERSTANDING_TESTPILOT.md`](../UNDERSTANDING_TESTPILOT.md) | **Plain-English Architecture Guide**: High-level walkthrough of how components interact on the developer's laptop. |

---

## Architecture Subdirectory

The [`architecture/`](architecture/) subdirectory contains deep architectural reviews, endpoint catalogues, and interactive runtime sequence diagrams:
- [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md): Structural architectural deep dive.
- [`architecture/ENDPOINTS.md`](architecture/ENDPOINTS.md): Comprehensive REST API endpoint reference.
- [`architecture/runtime-diagram.html`](architecture/runtime-diagram.html): Interactive runtime visualization.

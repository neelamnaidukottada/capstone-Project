# Copilot Instructions

## Golden Rule
Implement only frozen in-scope requirements first. Do not expand scope without explicit requirement update approval.

## Tech Stack Guardrails
- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- Orchestration: LangGraph-based agent workflow
- Data: Supabase Postgres
- Testing: pytest, Vitest, Playwright

## Folder Structure Guardrails
- backend/apps/api: API routes, auth, orchestration integration
- frontend/apps/web: UI pages, realtime views, campaign workflows
- backend/packages/agents: agent logic and orchestrator behavior
- backend/packages/database: schema, migrations, typed client access
- frontend/packages/types: shared TypeScript contracts
- docs: architecture and demonstration documentation

## Agent Rules
1. Read REQUIREMENTS.md first and treat it as frozen.
2. Follow SPEC.md contracts before writing implementation code.
3. Respect DEPENDENCIES.md order: models -> schemas -> services -> agents -> graph -> routes -> UI.
4. Use CHECKPOINTS.md gates; do not start next phase on yellow/red.
5. Keep changes small, testable, and traceable to one in-scope deliverable.
6. If a request is out-of-scope, log it in FUTURE_VISION.md stretch section instead of implementing immediately.

## Quality Rules
- Preserve API and schema consistency across backend, agents, and UI.
- Add or update tests for all behavior-changing modifications.
- Keep README phase status and DELIVERABLES.md in sync with progress.

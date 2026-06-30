# CHECKPOINTS

## Gate Policy
You cannot start the next phase until the current phase gate is green.

## Phase 1 Gate: Scope and Contracts
Green criteria:
- REQUIREMENTS.md frozen and approved.
- SPEC.md includes agent specs, schemas, data model, and API/WebSocket contracts.
- PLAN.md and DEPENDENCIES.md aligned to in-scope only.

## Phase 2 Gate: Backend and Data Foundations
Green criteria:
- Auth and campaign creation paths function end-to-end.
- Persistence model supports campaign run state and approvals.
- Critical backend tests for auth/campaign flow pass.

## Phase 3 Gate: Agent Orchestration
Green criteria:
- All in-scope agents execute under orchestrator control.
- Lifecycle events emitted for major state transitions.
- Strategy and budget approvals are required and enforce pause/resume.

## Phase 4 Gate: UI Realtime + Reporting
Green criteria:
- UI renders realtime campaign events from WebSocket stream.
- Approval actions are available and update state correctly.
- Report page shows JSON/Markdown outputs from final state.

## Phase 5 Gate: Demo Ready
Green criteria:
- DELIVERABLES.md final checklist is fully checked.
- README phase status and run instructions are current.
- Critical-path automated tests pass.
- Demo script rehearsed without blocker defects.

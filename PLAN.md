# PLAN

## Planning Rule
Milestones map only to in-scope features in REQUIREMENTS.md.

## Week 1

### Milestone 1 (Days 1-2): Requirements Freeze + Contract Baseline
- Freeze REQUIREMENTS.md.
- Finalize SPEC.md schema and endpoint contract baseline.
- Confirm architecture diagram and dependency chain.

### Milestone 2 (Days 3-4): Core Backend + Data Foundations
- Validate auth and campaign creation flow.
- Align Supabase tables/migrations with MVP data model.
- Establish campaign run state persistence and retrieval.

### Milestone 3 (Day 5): Agent + Orchestrator Baseline
- Wire planner/content/media/performance/reporter into orchestrator.
- Produce deterministic stage transitions and structured outputs.
- Emit lifecycle events for each stage.

## Week 2

### Milestone 4 (Days 6-7): Human Gates + Realtime UX
- Implement/verify strategy and budget approval gates.
- Connect WebSocket event stream to campaign detail UI.
- Ensure pause/resume flow is reliable.

### Milestone 5 (Days 8-9): Reporting + Validation
- Complete report view from aggregated execution outputs.
- Validate JSON and Markdown export outputs.
- Execute backend, frontend, and e2e critical-path tests.

### Milestone 6 (Day 10): Stabilization + Demo Readiness
- Fix critical defects only.
- Perform demo rehearsal and script final walkthrough.
- Lock release notes and final deliverables checklist.

## Capacity Reality Alignment
- Limit scope to one polished end-to-end workflow.
- Defer non-critical enhancements to FUTURE_VISION stretch list.
- Keep at least 20 percent of total effort for hardening and demo prep.

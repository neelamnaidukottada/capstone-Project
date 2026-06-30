# REQUIREMENTS

## Freeze Rule
This document is frozen before implementation starts. Any change to scope here requires a full review and revision of SPEC, PLAN, DEPENDENCIES, CHECKPOINTS, DELIVERABLES, and README.

## 1. Problem Statement
Small marketing teams often have to plan, execute, and optimize campaigns across multiple channels with limited time and specialist support. They lose momentum switching between strategy, creative, budget decisions, and reporting tools. This project solves that by coordinating specialized AI agents in one workflow with clear human approval points. The result is faster campaign execution with traceable decisions and real-time visibility.

## 2. In-Scope Features (2-Week Demo)
1. Authentication and campaign creation flow from the web app.
2. Multi-agent orchestration for planner, content creator, media buyer, performance analyst, and reporter.
3. Human-in-the-loop approvals for strategy and budget checkpoints.
4. Real-time campaign event streaming to the UI via WebSocket.
5. Supabase-backed campaign state persistence and retrieval.
6. Report generation and viewing in JSON and Markdown (PDF allowed as placeholder output).
7. End-to-end demonstration flow with automated tests for critical paths.

## 3. Out-of-Scope Features
- Multi-tenant enterprise account management: requires broader auth and org modeling beyond MVP.
- Ad platform live publishing integrations (Meta/Google APIs): integration and compliance effort exceeds 2 weeks.
- Advanced budget optimization models with continuous retraining: needs larger data pipeline and MLOps setup.
- Native mobile apps: web responsive UI is sufficient for this demo window.
- Full analytics warehouse and BI dashboards: current reporting is enough to validate product direction.

## 4. Assumptions
- Environment: Node.js 20+, pnpm 9+, Python 3.11+.
- Data: Supabase Postgres is reachable and seeded with minimum auth and campaign data.
- User: Demo users can approve or reject strategy and budget checkpoints.
- Integrations: External ad network APIs are mocked or simulated for this phase.
- LLM: Model responses are available through configured provider keys and constrained by schemas.

## 5. Success Criteria
1. A user can authenticate, create a campaign, and start orchestration without manual DB intervention.
2. All 5 specialist agents execute in sequence/graph flow and produce structured outputs captured in state.
3. At least 2 human approval gates pause and resume workflow correctly during demo.
4. Web client shows near-real-time campaign events with less than 3-second perceived lag in local demo.
5. Core quality checks pass: backend tests, agent tests, frontend tests, and one happy-path e2e flow.

## 6. Deliverables List
The complete deliverables list is maintained in DELIVERABLES.md.

## 7. 2-Week Capacity Reality Check
- Team capacity assumption: 2-3 contributors, ~10 working days, ~120-180 total engineering hours.
- Feasible scope: complete one robust end-to-end path, not every edge case.
- Risk-managed tradeoffs: prioritize reliability of orchestration, approvals, and live status over advanced optimization features.
- Contingency: reserve final 2 days for stabilization, bug fixing, and demo rehearsal only.

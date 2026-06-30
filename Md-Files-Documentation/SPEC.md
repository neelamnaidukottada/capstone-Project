# SPEC

## AI-First Development Strategy
This project follows Specification-Driven Development with prompt-governed implementation:
1. Freeze requirements first.
2. Define explicit schemas and contracts.
3. Implement minimal vertical slices that satisfy contracts.
4. Use Copilot Agent Mode with structured prompts and gate checks.
5. Block phase advancement until checkpoint gates are green.

## Agent Specifications

### 1. Planner Agent
- Input: campaign brief (goal, budget, audience, channels, constraints).
- Output: strategy object (positioning, channel plan, KPI targets, timeline).
- Failure mode: insufficient constraints -> request clarification payload.

### 2. Content Creator Agent
- Input: planner strategy and brand guardrails.
- Output: creative asset drafts (copy variants, hooks, CTA, format metadata).
- Failure mode: guardrail mismatch -> regenerate with strict constraints.

### 3. Media Buyer Agent
- Input: strategy targets, budget envelope, channel preferences.
- Output: allocation plan by channel, pacing, and spend rationale.
- Failure mode: budget inconsistency -> normalized allocation proposal.

### 4. Performance Analyst Agent
- Input: run metrics and historical snapshots.
- Output: performance insights, anomalies, and optimization suggestions.
- Failure mode: sparse metrics -> confidence flag and fallback recommendations.

### 5. Reporter Agent
- Input: all prior stage outputs and final metrics snapshot.
- Output: structured report sections and executive summary.
- Failure mode: missing sections -> default section template with warnings.

### 6. Orchestrator
- Role: controls execution graph/state transitions, approvals, retries, and completion.
- Gate controls: strategy approval and budget approval before downstream execution.

## I/O Schemas (Contract-Level)

### CampaignBrief
- campaign_name: string
- business_goal: string
- target_audience: string
- budget_total: number
- channels: string[]
- start_date: string (ISO-8601)
- end_date: string (ISO-8601)

### AgentEvent
- campaign_id: string
- event_type: string (agent_started | agent_completed | approval_required | approval_received | workflow_completed | workflow_failed)
- agent_name: string
- timestamp: string (ISO-8601)
- payload: object

### ApprovalDecision
- campaign_id: string
- gate: string (strategy | budget)
- approved: boolean
- reviewer_id: string
- comments: string

### ReportBundle
- campaign_id: string
- summary: string
- sections: object[]
- recommendations: string[]
- export_formats: string[]

## Data Model (MVP)
- users: id, email, role, created_at
- campaigns: id, user_id, name, objective, status, created_at, updated_at
- campaign_runs: id, campaign_id, state_json, started_at, completed_at
- approvals: id, campaign_run_id, gate, approved, reviewer_id, comments, decided_at
- reports: id, campaign_run_id, report_json, report_markdown, created_at
- events: id, campaign_run_id, event_type, payload_json, created_at

## API Contracts (In-Scope)
- POST /auth/register
- POST /auth/login
- GET /auth/me
- POST /campaigns
- GET /campaigns/{campaign_id}
- POST /campaigns/{campaign_id}/start
- POST /campaigns/{campaign_id}/approve
- GET /campaigns/{campaign_id}/report
- GET /health

## WebSocket Contract (In-Scope)
- WS /ws/campaigns/{campaign_id}
- Server emits AgentEvent messages for timeline updates and gate prompts.

## Definition of Contract Complete
- Request and response schemas documented and used consistently by API, agents, and UI state handling.
- Validation errors are explicit and actionable.
- Any contract change requires updates to tests and README phase status.

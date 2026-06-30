# Architecture Guide

## System Overview

The Autonomous Campaign Manager is a distributed, event-driven system composed of three primary layers:

1. **Frontend Layer** - Next.js web application for user interaction
2. **API Layer** - FastAPI backend for business logic and orchestration
3. **Agent Layer** - LangGraph-based autonomous agents for workflow execution

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                            │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Auth Pages  │  │ Campaign UI  │  │ Approval Interface  │   │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │                │
│         └─────────────────┼──────────────────────┘                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                        API Layer                                 │
│  ┌────────────┐  ┌───────────────┐  ┌────────────────────┐     │
│  │ Auth Routes│  │Campaign Routes│  │ Approval Routes   │     │
│  └────────────┘  └───────────────┘  └────────────────────┘     │
│  ┌─────────────────────────────────────────────────────┐         │
│  │         Service Layer                                │        │
│  │  ├─ AuthService    ├─ CampaignService               │        │
│  │  └─ ApprovalService└─ ReportService                │        │
│  └─────────────────┬───────────────────────────────────┘         │
│                    │                                              │
│  ┌─────────────────▼───────────────────────────────────┐         │
│  │  Orchestration Integration (starts graph execution) │         │
│  └─────────────────┬───────────────────────────────────┘         │
└──────────────────┬──────────────────────────────────────────────┘
                   │ Task Queue / Direct Call
┌──────────────────▼──────────────────────────────────────────────┐
│                      Agent Layer                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              LangGraph Orchestrator                    │    │
│  │                                                        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────┐    │    │
│  │  │ Planner  │  │ Content  │  │ Media Buyer    │    │    │
│  │  │ Agent    │  │ Creator  │  │ Agent          │    │    │
│  │  │          │  │ Agent    │  │                │    │    │
│  │  └──────────┘  └──────────┘  └─────────────────┘    │    │
│  │                                                       │    │
│  │  ┌──────────────────┐  ┌──────────────────────┐    │    │
│  │  │ Performance      │  │ Reporter Agent      │    │    │
│  │  │ Analyst Agent    │  │                     │    │    │
│  │  └──────────────────┘  └──────────────────────┘    │    │
│  │                                                       │    │
│  │  Gate Control: Strategy Approval → Budget Approval   │    │
│  │  Output: Structured JSON → Events → Persistence     │    │
│  └────────────────────────────────────────────────────┘    │
└───────────┬──────────────────────────────────────────────────┘
            │ Events + State
┌───────────▼──────────────────────────────────────────────────┐
│                  Data Layer                                  │
│  ┌─────────────────┐  ┌──────────────────────────────┐      │
│  │ Supabase        │  │ PostgreSQL Database          │      │
│  │ (Auth + Files)  │  │ - Users                      │      │
│  │                 │  │ - Campaigns                  │      │
│  │                 │  │ - Campaign Runs              │      │
│  │                 │  │ - Approvals                  │      │
│  │                 │  │ - Reports                    │      │
│  │                 │  │ - Events                     │      │
│  └─────────────────┘  └──────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### Campaign Execution Flow

```
1. User Creates Campaign
   └─> POST /campaigns
       └─> CampaignService stores draft
           └─> Database: campaigns table

2. User Starts Orchestration
   └─> POST /campaigns/{id}/start
       └─> Create campaign_run entry
           └─> Initialize agent state
               └─> Emit campaign_started event

3. Orchestrator Graph Execution
   └─> Planner Node
       ├─> Generates strategy
       ├─> Emits strategy_completed event
       └─> GATE: Strategy Approval
   
   └─> [Awaits User Approval]
       └─> POST /campaigns/{id}/approve (gate: strategy)
           └─> Update campaign_run state
               └─> Resume graph

   └─> Content Creator Node
       ├─> Generates creative assets
       ├─> Emits content_completed event
       └─> Continues to Media Buyer

   └─> Media Buyer Node
       ├─> Allocates budget
       ├─> Emits budget_ready event
       └─> GATE: Budget Approval

   └─> [Awaits User Approval]
       └─> POST /campaigns/{id}/approve (gate: budget)
           └─> Resume graph

   └─> Performance Analyst Node
       ├─> Analyzes projections
       ├─> Emits analysis_completed event
       └─> Continues to Reporter

   └─> Reporter Node
       ├─> Compiles report
       ├─> Emits workflow_completed event
       └─> Store report in database

4. Workflow Completion
   └─> Event loop broadcasts to connected clients
       └─> UI updates final report view
```

## Technology Stack Rationale

### Frontend: Next.js + TypeScript

**Why**: 
- Built-in routing and SSR for campaign pages
- TypeScript for type safety across UI state
- React Server Components for efficient data fetching
- Excellent integration with Supabase Auth

**Key Packages**:
- `@supabase/supabase-js`: Database and auth client
- `zustand`: Lightweight state management
- `tailwindcss`: Rapid UI development
- `shadcn/ui`: Accessible component library

### Backend: FastAPI + Python

**Why**:
- Async-native, high concurrency without callbacks
- Automatic OpenAPI documentation
- Pydantic for request/response validation
- Excellent integration with LangGraph orchestrator

**Key Packages**:
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `pydantic`: Data validation
- `supabase-py`: Database client

### Orchestration: LangGraph

**Why**:
- Native state graph management for agent workflows
- Built-in checkpoint and recovery system
- Integrates seamlessly with LangChain agents
- Deterministic execution tracing for auditing

**Key Packages**:
- `langgraph`: Graph execution engine
- `langchain`: LLM framework
- `langchain-openai` / `langchain-anthropic`: LLM providers

### Database: Supabase PostgreSQL

**Why**:
- Managed PostgreSQL with built-in auth
- Real-time subscriptions for event streaming
- Row-level security for multi-tenant safety
- SQL migrations for schema version control

**Key Tables**:
- `users`: Auth and user metadata
- `campaigns`: Campaign definitions
- `campaign_runs`: Execution state per run
- `approvals`: Approval gate records
- `reports`: Final report outputs
- `events`: Audit trail of all state changes

## Key Design Decisions

### 1. Event-Driven Architecture
- Every state change emits an event (event sourcing)
- Events persist to database for audit trail
- WebSocket broadcasts events to connected UIs
- **Benefit**: Full observability and auditability

### 2. Gate-Based Workflow Control
- Strategy gate: User approves planner output before content generation
- Budget gate: User approves spend allocation before performance analysis
- **Benefit**: Human-in-the-loop safety and accountability

### 3. Stateless API with Stateful Orchestrator
- API is stateless (can be horizontally scaled)
- LangGraph handles complex state transitions
- Campaign state persisted in database checkpoints
- **Benefit**: Scalability + reliability without distributed state

### 4. Schema-First Development
- All data contracts defined in SPEC.md before coding
- Pydantic models enforce schema consistency
- TypeScript types auto-generated from API responses
- **Benefit**: Type safety, contract clarity, reduced bugs

### 5. Real-Time Event Streaming
- WebSocket connection per active campaign
- Events broadcast to all connected clients
- Clients subscribe and update UI in real-time
- **Benefit**: Responsive UX without polling overhead

## Deployment Architecture (Reference)

```
┌─────────────────────────────────────┐
│     Frontend (Vercel / Firebase)    │
│         - Next.js App               │
└────────────────┬────────────────────┘
                 │
    ┌────────────┴───────────┐
    │                        │
    │   CDN (CloudFlare)     │
    │                        │
    └────────────┬───────────┘
                 │
┌────────────────▼──────────────────┐
│  API Gateway / Load Balancer       │
└────────────────┬──────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼────────────┐  ┌────────▼──────┐
│ FastAPI (x3)   │  │ Task Worker    │
│ - Stateless    │  │ - Orchestration│
│ - Auto-scale   │  │ - Jobs Queue   │
└────────────────┘  └────────────────┘
         │
    ┌────▼─────────────────┐
    │                      │
┌───▼──────────────┐  ┌───▼──────────┐
│  Supabase Cloud  │  │   Redis      │
│  - PostgreSQL    │  │   - Caching  │
│  - Auth          │  │   - Sessions │
│  - Real-time     │  │   - Queue    │
└──────────────────┘  └──────────────┘
```

## Scalability Considerations

### Horizontal Scaling
- API layer: Stateless FastAPI servers behind load balancer
- Worker layer: Multiple LangGraph orchestrator workers
- Database: Supabase handles automatic replication

### Vertical Optimization
- Agent parallel execution where possible
- Caching of LLM embeddings and common responses
- Batch approval requests to reduce round-trips

### Performance Budgets
- Campaign creation: < 2 seconds
- Approval decision: < 1 second
- Report generation: < 30 seconds
- WebSocket event delivery: < 3 second perceived lag

## Security Architecture

### Authentication Flow
1. User registers/logs in via Supabase Auth
2. JWT token issued with user ID and role
3. Token validated on every API request
4. WebSocket authentication via JWT in upgrade header

### Authorization
- Row-level security: Users can only see their campaigns
- API validation: Check user_id matches campaign owner
- Role-based access: `user`, `admin` roles for future expansion

### Data Protection
- All data encrypted at rest (Supabase default)
- TLS 1.2+ for all transit
- Secrets stored in environment variables (not code)
- Rate limiting on auth endpoints (brute-force protection)

## Monitoring & Observability

### Logging Strategy
- Structured logging (JSON) for all major events
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized logging to stdout (container-friendly)

### Metrics
- Campaign execution time distribution
- Agent success/failure rates
- API response times
- WebSocket connection count

### Tracing
- Request ID propagated through all layers
- Agent execution traced in LangGraph checkpoints
- Event timestamps in database for replay

---

See `docs/architecture.mmd` for the current Mermaid diagram source.

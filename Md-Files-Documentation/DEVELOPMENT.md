# Development Setup & Workflow

## Prerequisites

Before starting development, ensure you have:

- **Node.js 20+** ([Download](https://nodejs.org/))
- **pnpm 9+** (`npm install -g pnpm`)
- **Python 3.11+** ([Download](https://www.python.org/))
- **Git** ([Download](https://git-scm.com/))
- **Supabase Account** ([Sign up](https://supabase.com/))

### Verify Installation

```bash
node --version    # Should be v20.x or higher
pnpm --version    # Should be 9.x or higher
python --version  # Should be 3.11 or higher
```

## Step 1: Clone Repository

```bash
git clone https://github.com/your-org/autonomous-campaign-manager.git
cd autonomous-campaign-manager
```

## Step 2: Install Dependencies

### Install Node Dependencies (Root Level)

```bash
pnpm install
```

This installs dependencies for:
- `frontend/apps/web` (Next.js frontend)
- `frontend/packages/types` (Shared TypeScript types)
- `backend/apps/api` (FastAPI project - no Node deps)
- `backend/packages/agents` (Agent package - no Node deps)
- `backend/packages/database` (Database migrations)

### Install Python Backend Dependencies

#### Backend API Environment

```bash
# Navigate to API directory
cd backend/apps/api

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Windows cmd:
.venv\Scripts\activate.bat

# Install in development mode
pip install -e ".[dev]"
```

#### Agents Package Environment

```bash
# Navigate to agents directory
cd backend/packages/agents

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# (same commands as above for your OS)

# Install in development mode (REQUIRED for imports)
pip install -e ".[dev]"

# This must be installed before running the API
```

## Step 3: Configure Environment Variables

### Create Backend API `.env`

```bash
cd backend/apps/api
cp .env.example .env
```

Fill in the `.env` file:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# API Configuration
API_SECRET_KEY=your-secret-key-min-32-chars
FRONTEND_URL=http://localhost:3000

# LLM Configuration (choose one provider)
OPENAI_API_KEY=your-openai-key
# OR
ANTHROPIC_API_KEY=your-anthropic-key

# Optional: Analytics API Key
AMZUR_API_KEY=your-api-key
```

### Create Frontend `.env.local`

```bash
cd frontend/apps/web
cp .env.local.example .env.local
```

Fill in the `.env.local` file:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_DEBUG=true
```

### Create Agents `.env` (Optional)

```bash
cd backend/packages/agents
cp .env.example .env
```

## Step 4: Database Setup

### Local Supabase Setup (Recommended for Development)

```bash
# Install Supabase CLI
npm install -g @supabase/cli

# Initialize local Supabase
supabase init

# Start local Supabase stack
supabase start
```

This starts:
- PostgreSQL database on `localhost:5432`
- Supabase Studio on `http://localhost:54323`
- Auth service on `localhost:9999`

### Seed Database

```bash
# Navigate to database package
cd backend/packages/database

# Load initial schema
psql postgresql://postgres:postgres@localhost:5432/postgres < supabase/migrations/001_initial.sql
psql postgresql://postgres:postgres@localhost:5432/postgres < supabase/migrations/002_full_schema.sql
psql postgresql://postgres:postgres@localhost:5432/postgres < supabase/migrations/003_auth_identity.sql

# Or use Supabase CLI
supabase db pull
```

## Step 5: Start Development Servers

### Option A: Start All Services Together

```bash
# From root directory
pnpm dev
```

This command:
- Starts FastAPI backend on `http://localhost:8000`
- Starts Next.js frontend on `http://localhost:3000`
- Watches for file changes in both

### Option B: Start Services Separately

#### Terminal 1: Backend API

```bash
cd backend/apps/api
.\.venv\Scripts\Activate.ps1  # (or source .venv/bin/activate on macOS/Linux)
python main.py
```

Runs on `http://localhost:8000`

OpenAPI docs: `http://localhost:8000/docs`

#### Terminal 2: Frontend

```bash
cd frontend/apps/web
pnpm dev
```

Runs on `http://localhost:3000`

#### Terminal 3: Backend Agents (if running long-lived tasks)

```bash
cd backend/packages/agents
.\.venv\Scripts\Activate.ps1
# Agents run within the API process, no separate service needed
```

## Step 6: Validate Setup

### Check API Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-06-29T10:00:00Z"
}
```

### Check Frontend

Open `http://localhost:3000` in your browser

### Run Tests

```bash
# From root directory
pnpm test
```

This runs:
- Backend tests: `pytest backend/apps/api tests/`
- Backend agent tests: `pytest backend/packages/agents tests/`
- Frontend tests: `vitest frontend/apps/web`

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Changes

**For Backend**:
- Edit Python files in `backend/apps/api/app/`
- Changes auto-reload with `uvicorn --reload`

**For Frontend**:
- Edit TypeScript/TSX in `frontend/apps/web/src/`
- Changes auto-reload with Next.js

**For Agents**:
- Edit Python files in `backend/packages/agents/src/`
- Restart API after changes: `python main.py`

### 3. Run Tests Locally

```bash
# Backend tests
cd backend/apps/api && python -m pytest tests/

# Agent tests
cd backend/packages/agents && python -m pytest tests/

# Frontend tests

## Dynamic-First Implementation Notes

Use these rules when implementing UI and orchestration behavior:

- Avoid prefilled business/demo defaults in campaign entry forms unless explicitly requested by product requirements.
- Approval actions in UI must call backend endpoints and provide clear user feedback on success/failure.
- Keep runtime fallback/demo logic gated to non-production contexts and clearly labeled.
- Prefer environment-driven configuration for API URLs and model/provider settings.

### Recent Dynamic Fixes (2026-06-30)

- Strategy page action buttons are now wired to live approval calls.
- Strategy and report insights are rendered from campaign state instead of hidden in raw payloads.
- Campaign builder now starts with empty, user-driven inputs rather than static product-specific examples.
- Dev QA panel supports running test scenarios from frontend and injecting mock performance metrics without backend scripts.

### Dev QA Panel (Frontend)

- Location: campaign overview page in development mode.
- Required frontend env: NEXT_PUBLIC_ENABLE_DEBUG=true.
- The panel can trigger:
  - Content edge-case scenarios (budget=0, missing audience)
  - Media scenarios (low-budget students, high-budget omnichannel, invalid negative budget)
  - Performance scenarios (poor, excellent, custom metrics)
  - Report-full scenario generation

### Dev QA Simulation Endpoint (Backend)

- Endpoint: POST /api/v1/campaigns/{campaign_id}/qa/simulate
- Availability: development environment only.
- The endpoint updates campaign goal/runtime QA metrics and re-runs workflow in auto-approve mode for deterministic UI verification.

### Known Static Hotspots To Refactor Next

- backend/apps/api/app/services/campaign_service.py
  - Demo-style workflow dependency implementations currently return synthetic static outputs.
  - Initial campaign execution metrics and brand guideline defaults are synthetic and should move to dynamic sources.
- backend/packages/agents/src/*
  - Agent model and temperature defaults are hardcoded; should be configurable through environment or settings.
pnpm --filter @acm/web test

# E2E tests
pnpm test:e2e
```

### 4. Type Check & Lint

```bash
pnpm lint        # ESLint for TypeScript files
pnpm type-check  # Full TypeScript check
pnpm format      # Auto-format with Prettier
```

### 5. Commit & Push

```bash
git add .
git commit -m "feat: describe your changes"
git push origin feature/my-feature
```

### 6. Create Pull Request

- Go to repository on GitHub
- Open PR from your branch to `main`
- Link relevant issues
- Add description of changes

## Common Development Tasks

### Add a New API Endpoint

1. **Define schema** in `backend/apps/api/app/models/`
2. **Implement service** in `backend/apps/api/app/services/`
3. **Create route** in `backend/apps/api/app/routers/`
4. **Write tests** in `backend/apps/api/tests/`

Example:

```python
# models/campaign.py
from pydantic import BaseModel

class CampaignResponse(BaseModel):
    id: str
    campaign_name: str
    status: str

# services/campaign_service.py
class CampaignService:
    async def get_campaign(self, campaign_id: str) -> CampaignResponse:
        # Implementation

# routers/campaigns.py
from fastapi import APIRouter
from ..services.campaign_service import CampaignService

router = APIRouter(prefix="/campaigns")

@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    service = CampaignService()
    return await service.get_campaign(campaign_id)
```

### Add a New UI Component

1. **Create component** in `frontend/apps/web/src/components/`
2. **Write tests** in component directory or `frontend/apps/web/src/test/`
3. **Use in page** from `frontend/apps/web/src/app/`

Example:

```tsx
// components/CampaignCard.tsx
import { Campaign } from '@acm/types';

export function CampaignCard({ campaign }: { campaign: Campaign }) {
  return (
    <div className="p-4 border rounded">
      <h3>{campaign.campaign_name}</h3>
      <p>Status: {campaign.status}</p>
    </div>
  );
}

// app/campaigns/page.tsx
import { CampaignCard } from '@/components/CampaignCard';

export default function CampaignsPage() {
  return (
    <div>
      {campaigns.map(c => <CampaignCard key={c.id} campaign={c} />)}
    </div>
  );
}
```

### Add a New Agent

1. **Define agent logic** in `backend/packages/agents/src/`
2. **Add to orchestrator graph** in `orchestrator.py`
3. **Write tests** in `backend/packages/agents/tests/`
4. **Update SPEC.md** with agent contract

### Debug API Requests

```bash
# Enable request logging
export DEBUG=1
python main.py

# Or use FastAPI's built-in debug mode
from fastapi import FastAPI
app = FastAPI(debug=True)
```

### Debug Frontend State

Use React DevTools browser extension:
- [React DevTools](https://react-devtools-tutorial.vercel.app/)
- Watch state changes in real-time
- Inspect component props

## Troubleshooting

### Python Venv Not Activated

**Error**: `command not found: pip install` or `python: command not found`

**Solution**:
```bash
# Verify which Python you're using
which python  # (macOS/Linux) or Get-Command python (PowerShell)

# Activate the correct venv
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\Activate.ps1  # PowerShell
```

### Database Connection Refused

**Error**: `FATAL: could not connect to server`

**Solution**:
```bash
# Start local Supabase
supabase start

# Or check if Postgres is running
psql -U postgres
```

### Port Already in Use

**Error**: `Address already in use` on port 8000 or 3000

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwnerProcess  # PowerShell

# Kill the process
kill -9 <PID>
```

### Agents Package Import Error

**Error**: `ModuleNotFoundError: No module named 'agents'`

**Solution**:
```bash
# Install agents package in editable mode
cd backend/packages/agents
pip install -e .
```

### Type Checking Failures

**Error**: `mypy error` or type hints not working

**Solution**:
```bash
# Run full type check
cd backend/apps/api
mypy app/

# Or check specific file
mypy app/services/campaign_service.py
```

## Advanced Development

### Database Migrations

```bash
# Create new migration
psql $DATABASE_URL < new_migration.sql

# Rollback migration
psql $DATABASE_URL -c "DROP TABLE <table_name>;"

# View current schema
psql $DATABASE_URL -c "\dt"  # List tables
psql $DATABASE_URL -c "\d <table_name>"  # Show table structure
```

### Performance Profiling

**Backend** (Python):
```python
import cProfile
import pstats

pr = cProfile.Profile()
pr.enable()
# ... code to profile ...
pr.disable()
ps = pstats.Stats(pr)
ps.sort_stats('cumulative')
ps.print_stats(10)
```

**Frontend** (TypeScript/React):
```bash
# Use Next.js built-in performance monitoring
pnpm next build --profile
```

### Environment Switching

```bash
# Local development
export NODE_ENV=development
export ENVIRONMENT=local

# Staging
export NODE_ENV=staging
export ENVIRONMENT=staging

# Production
export NODE_ENV=production
export ENVIRONMENT=production
```

---

**Next Steps**:
- Read [TESTING.md](TESTING.md) for testing strategies
- Read [API.md](API.md) for API endpoint documentation
- Read [CONTRIBUTING.md](CONTRIBUTING.md) for code standards

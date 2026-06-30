# Troubleshooting Guide

## Common Issues & Solutions

### Backend (FastAPI)

#### 1. API Server Won't Start

**Error**: `Address already in use`

```
OSError: [Errno 48] Address already in use
```

**Solution**:
```bash
# Find what's using port 8000
lsof -i :8000              # macOS/Linux
Get-NetTCPConnection -LocalPort 8000  # PowerShell

# Kill the process
kill -9 <PID>              # macOS/Linux
Stop-Process -Id <PID>     # PowerShell

# Or use a different port
uvicorn main:app --port 8001
```

#### 2. Agents Package Import Error

**Error**: `ModuleNotFoundError: No module named 'src'` or `ImportError`

```
ModuleNotFoundError: No module named 'src'
```

**Solution**:
```bash
# Install agents package in editable mode
cd backend/packages/agents
pip install -e .

# Verify installation
python -c "from src.orchestrator import Orchestrator; print('OK')"

# If still failing, reinstall everything
pip uninstall acm-agents -y
pip install -e ".[dev]"
```

#### 3. Database Connection Refused

**Error**: `refused to connect` or `psycopg error`

```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Solution**:
```bash
# Check Supabase is running (local)
supabase status

# Start Supabase
supabase start

# Verify PostgreSQL connection
psql postgresql://postgres:postgres@localhost:5432/postgres

# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY
```

#### 4. Pydantic Validation Errors

**Error**: `validation error for CreateCampaignRequest`

```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for CreateCampaignRequest
```

**Solution**:
```python
# Check the actual error message for field issues
# Usually indicates:
# - Missing required field
# - Wrong data type
# - Violates Field constraints

# Example fix:
class CreateCampaignRequest(BaseModel):
    budget_total: float  # Must be numeric, not string
    start_date: str      # Must be ISO-8601 format
    channels: List[str]  # Must be array

# Send correct data
{
    "campaign_name": "Sale",
    "business_goal": "Increase sales",
    "budget_total": 5000,         # ✓ Number
    "start_date": "2026-07-01",  # ✓ ISO-8601
    "channels": ["email"]          # ✓ Array
}
```

#### 5. Async/Await Issues

**Error**: `RuntimeError: Event loop is closed`

```
RuntimeError: Event loop is closed
```

**Solution**:
```python
# Use @app.get() not just @router.get()
@router.get("/endpoint")
async def my_endpoint():  # ✓ Async function
    result = await async_call()
    return result

# Don't wrap async in lambda
async def agent_node(state):
    # ✓ CORRECT
    result = await agent.process(state)
    return result

# ❌ WRONG - Creates coroutine object
async def agent_node_wrong(state):
    return lambda: await agent.process(state)
```

#### 6. WebSocket Connection Issues

**Error**: `WebSocket connection failed` or `Connection refused`

```
WebSocketException: Handshake error - invalid HTTP status 400
```

**Solution**:
```python
# Verify WebSocket endpoint accepts connections
@router.websocket("/ws/campaigns/{campaign_id}")
async def websocket_endpoint(websocket: WebSocket, campaign_id: str):
    await websocket.accept()  # Accept before accessing attributes
    # ... implementation

# Check authentication token is valid
# Don't require authentication before accept()
try:
    user = verify_token(token)
except:
    await websocket.close(code=4001, reason="Unauthorized")
    return
```

### Frontend (Next.js / React)

#### 1. Module Not Found

**Error**: `Module not found: Can't resolve '@acm/types'`

```
Module not found: Can't resolve '@acm/types'
```

**Solution**:
```bash
# Install all workspace dependencies
pnpm install

# Rebuild TypeScript types
pnpm type-check

# Clear Next.js cache
cd frontend/apps/web
rm -rf .next
pnpm dev
```

#### 2. Type Errors in Components

**Error**: `Type 'string' is not assignable to type 'never'`

```
Type 'string' is not assignable to type 'never'
```

**Solution**:
```typescript
// This is usually caused by discriminated union issues
// ❌ WRONG
type Status = 'active' | 'inactive';
function getStatus(s: Status) {
  if (s === 'active') return 'Active';
  if (s === 'inactive') return 'Inactive';
  return s;  // Never (unreachable)
}

// ✓ CORRECT - Handle both cases or use exhaustive check
type Status = 'active' | 'inactive';
function getStatus(s: Status): string {
  switch(s) {
    case 'active': return 'Active';
    case 'inactive': return 'Inactive';
  }
}
```

#### 3. WebSocket Won't Connect

**Error**: `WebSocket is closed`

```
WebSocket is closed before the connection is established
```

**Solution**:
```typescript
// Include authentication token in URL
const token = localStorage.getItem('auth_token');
const socket = new WebSocket(
  `ws://localhost:8000/ws/campaigns/${id}?token=${token}`
);

// Or use custom headers (some browsers don't support Query params)
const socket = new WebSocket(`ws://localhost:8000/ws/campaigns/${id}`);
socket.addEventListener('open', () => {
  socket.send(JSON.stringify({ type: 'auth', token }));
});

// Check that backend is running
// Check CORS/origin is allowed
```

#### 4. Styling Issues with Tailwind

**Error**: Styles not applying or className not recognized

**Solution**:
```bash
# Rebuild Tailwind CSS
pnpm --filter @acm/web dev

# Clear Next.js cache
rm -rf .next
pnpm dev

# Check tailwind.config.ts includes correct paths
# Should include: './src/**/*.{js,ts,jsx,tsx}'
```

#### 5. API Calls Fail (CORS)

**Error**: `Access to XMLHttpRequest blocked by CORS policy`

```
Access to XMLHttpRequest at 'http://localhost:8000/api/campaigns' 
from origin 'http://localhost:3000' has been blocked by CORS policy
```

**Solution**:
```python
# Verify backend CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Database (Supabase)

#### 1. Migration Failed

**Error**: `migration error` or SQL syntax error

```
Error: migration file has syntax error
```

**Solution**:
```bash
# Test migration SQL locally
psql $DATABASE_URL < migration.sql

# Check migration file syntax
# Look for:
# - Missing semicolons
# - Unclosed quotes
# - Invalid table names
# - Type mismatches

# View current schema
psql $DATABASE_URL -c "\dt"  # List tables
psql $DATABASE_URL -c "\d campaigns"  # Describe table

# Rollback migration
supabase db reset

# Re-apply migrations
supabase db pull
```

#### 2. RLS Policy Blocks Access

**Error**: `row level security policy` or `insufficient privileges`

```
Error: new row violates row-level security policy
```

**Solution**:
```sql
-- Check which policies are defined
SELECT * FROM pg_policies WHERE tablename = 'campaigns';

-- Verify user ID in policy matches actual user
-- Policies should use auth.uid()
CREATE POLICY campaigns_select ON campaigns
FOR SELECT
USING (user_id = auth.uid());

-- Disable RLS temporarily for debugging (not production!)
ALTER TABLE campaigns DISABLE ROW LEVEL SECURITY;
```

#### 3. Connection Pool Exhausted

**Error**: `too many connections`

```
FATAL: sorry, too many clients already
```

**Solution**:
```bash
# Check active connections
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections
psql $DATABASE_URL -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE idle_in_transaction;
"

# For Supabase: check connection settings in dashboard
# Increase max connections if needed (costs more)
```

### Testing

#### 1. pytest Timeout

**Error**: `FAILED - Timeout`

```
FAILED tests/test_agent.py::test_agent - Timeout
```

**Solution**:
```python
# Increase timeout in pytest config
# pyproject.toml
[tool.pytest.ini_options]
timeout = 60  # seconds

# Or per test
@pytest.mark.timeout(120)
async def test_long_running_agent():
    # Test that takes up to 120 seconds
    pass

# Or manually with asyncio
import asyncio
await asyncio.wait_for(long_task(), timeout=30.0)
```

#### 2. Test Database Not Clean

**Error**: `IntegrityError` or duplicate key errors

```
IntegrityError: duplicate key value violates unique constraint
```

**Solution**:
```python
# Use fixture to clean up after each test
@pytest.fixture
async def clean_database():
    yield
    # Cleanup
    await db.table('campaigns').delete().neq('id', None).execute()

# Use in test
async def test_create_campaign(clean_database):
    # Test runs with clean database
    pass
```

#### 3. E2E Tests Timing Out

**Error**: `Timeout waiting for element` or `Target page, context or browser has been closed`

```
Timeout 30000ms exceeded
```

**Solution**:
```typescript
// Increase timeout for slow operations
await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

// Use explicit waits instead of implicit waits
await page.waitForSelector('.approval-card', { timeout: 60000 });

// Check selectors are correct
await page.pause();  // Debug mode - lets you inspect page
```

### Performance

#### 1. API Response Slow

**Error**: Endpoint takes 30+ seconds to respond

**Diagnosis**:
```bash
# Check API logs
docker logs <api-container>  # See if there are errors

# Profile the endpoint
import time
@router.get("/campaigns")
async def get_campaigns():
    start = time.time()
    campaigns = await db.get_campaigns()
    elapsed = time.time() - start
    print(f"Query took {elapsed}s")
    return campaigns
```

**Solution**:
```python
# Add database indexes
CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);

# Use pagination
@router.get("/campaigns")
async def get_campaigns(skip: int = 0, limit: int = 10):
    return await db.get_campaigns(skip, limit)

# Cache frequently accessed data
from functools import lru_cache
@lru_cache(maxsize=128)
def get_channel_list():
    return ['email', 'social', 'sms']
```

#### 2. WebSocket Lag

**Error**: Real-time events delayed > 3 seconds

**Solution**:
```python
# Optimize event broadcasting
async def broadcast_event(campaign_id: str, event: AgentEvent):
    # Use efficient serialization
    event_data = orjson.dumps(event.dict())
    
    # Broadcast to all connections in parallel
    tasks = [
        ws.send_bytes(event_data)
        for ws in active_connections[campaign_id]
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
```

### Configuration

#### 1. Environment Variable Not Loaded

**Error**: `KeyError: 'DATABASE_URL'` or `None` when accessing env var

```
KeyError: 'DATABASE_URL'
```

**Solution**:
```bash
# Verify .env file exists
ls -la .env

# Check variable is set
echo $DATABASE_URL  # Should print value, not empty

# Reload environment
source .env  # macOS/Linux
.\.env (in PowerShell doesn't work) - restart terminal

# Check code uses os.getenv() correctly
import os
db_url = os.getenv('DATABASE_URL')
# Not: db_url = os.environ['DATABASE_URL']  # Raises KeyError if not set
```

#### 2. Wrong API URL in Frontend

**Error**: Requests go to wrong backend

**Solution**:
```typescript
// frontend/apps/web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000

// Use in code
const API_URL = process.env.NEXT_PUBLIC_API_URL;
const response = await fetch(`${API_URL}/api/campaigns`);

// Verify in browser console
console.log(process.env.NEXT_PUBLIC_API_URL);
```

## Debugging Tools

### Python Debugging

```python
# Print debugging
print(f"Debug: {variable}")

# Python debugger
import pdb; pdb.set_trace()  # Sets breakpoint
# Commands: n (next), s (step), c (continue), p variable (print)

# Or use IDE breakpoints in VS Code/PyCharm
```

### TypeScript/React Debugging

```typescript
// Browser DevTools
console.log('Debug:', value);
debugger;  // Sets breakpoint

// React DevTools extension
// Check component state and props in real-time
```

### Database Debugging

```bash
# Connect to database and run queries
psql $DATABASE_URL

# Useful queries
\dt                    # List tables
\d campaigns           # Describe table
SELECT * FROM campaigns LIMIT 5;  # View data
```

## Getting Help

1. **Check this document** for your specific error
2. **Check GitHub Issues** for similar problems
3. **Check logs** for more context
4. **Ask in Slack** with:
   - Error message (full stack trace)
   - Steps to reproduce
   - What you already tried
5. **Open a GitHub Discussion** for questions

---

**Related Documentation**:
- [DEVELOPMENT.md](DEVELOPMENT.md) - Setup issues
- [TESTING.md](TESTING.md) - Test failures
- [SECURITY.md](SECURITY.md) - Security issues

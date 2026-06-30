# Testing Strategy & Guidelines

## Overview

The Autonomous Campaign Manager uses a multi-layered testing approach:

1. **Unit Tests**: Test individual functions and components in isolation
2. **Integration Tests**: Test modules working together (services + database)
3. **End-to-End (E2E) Tests**: Test complete user workflows through the UI
4. **Contract Tests**: Verify API and schema consistency

## Test Coverage Goals

| Layer | Coverage Target | Tools |
|-------|-----------------|-------|
| Backend API | 80%+ | pytest, pytest-cov |
| Agent Logic | 80%+ | pytest, pytest-asyncio |
| Frontend Components | 70%+ | Vitest, @testing-library/react |
| E2E Critical Paths | 100% | Playwright |

## Backend Testing

### Test Structure

```
backend/
├── apps/
│   └── api/
│       ├── app/
│       ├── tests/
│       │   ├── conftest.py          # Pytest fixtures
│       │   ├── test_api_endpoints.py
│       │   ├── test_auth_flow.py
│       │   ├── test_auth_service.py
│       │   ├── test_database_supabase.py
│       │   ├── test_websocket_connection.py
│       │   ├── test_websocket_contract.py
│       │   └── fixtures/             # Mock data
│       └── requirements-dev.txt      # Test dependencies
└── packages/
    └── agents/
        ├── src/
        ├── tests/
        │   ├── test_content_creator.py
        │   ├── test_demo_scenarios.py
        │   ├── test_media_buyer.py
        │   ├── test_orchestrator.py
        │   ├── test_performance_analyst.py
        │   ├── test_planner.py
        │   └── test_reporter.py
        └── requirements-dev.txt
```

### Running Backend Tests

```bash
# Run all tests
pnpm test:backend

# Run specific test file
cd backend/apps/api
python -m pytest tests/test_auth_flow.py -v

# Run with coverage
cd backend/apps/api
python -m pytest --cov=app --cov-report=html

# Run specific test by name
python -m pytest tests/test_auth_flow.py::test_login_success -v

# Run tests matching pattern
python -m pytest tests/ -k "auth" -v

# Run tests with markers
python -m pytest tests/ -m "integration" -v

# Run in watch mode (requires pytest-watch)
ptw
```

### Writing Backend Tests

#### Example: API Endpoint Test

```python
# backend/apps/api/tests/test_campaigns.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def sample_campaign():
    """Fixture providing a sample campaign object"""
    return {
        "campaign_name": "Test Campaign",
        "business_goal": "Test goal",
        "target_audience": "Test audience",
        "budget_total": 1000,
        "channels": ["email"],
        "start_date": "2026-07-01",
        "end_date": "2026-07-31"
    }

@pytest.fixture
def auth_headers(authenticated_user_token):
    """Fixture providing authorization headers"""
    return {"Authorization": f"Bearer {authenticated_user_token}"}

def test_create_campaign_success(sample_campaign, auth_headers):
    """Test successful campaign creation"""
    response = client.post(
        "/api/v1/campaigns",
        json=sample_campaign,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["campaign_name"] == sample_campaign["campaign_name"]
    assert data["status"] == "draft"
    assert "id" in data

def test_create_campaign_missing_auth():
    """Test campaign creation without authentication"""
    response = client.post("/api/v1/campaigns", json={})
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_create_campaign_validation_error(auth_headers):
    """Test campaign creation with invalid data"""
    invalid_campaign = {
        "campaign_name": "Test",
        # Missing required fields
    }
    
    response = client.post(
        "/api/v1/campaigns",
        json=invalid_campaign,
        headers=auth_headers
    )
    
    assert response.status_code == 422
    assert "validation_error" in response.json()["error"]["code"]
```

#### Example: Service Test

```python
# backend/apps/api/tests/test_campaign_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.campaign_service import CampaignService

@pytest.mark.asyncio
async def test_get_campaign_by_id():
    """Test retrieving a campaign"""
    service = CampaignService()
    
    with patch('app.services.database_client') as mock_db:
        mock_db.table('campaigns').select.return_value = AsyncMock(
            return_value={
                "data": [{
                    "id": "campaign-1",
                    "campaign_name": "Test Campaign",
                    "status": "draft"
                }]
            }
        )
        
        campaign = await service.get_campaign("campaign-1")
        
        assert campaign.id == "campaign-1"
        assert campaign.campaign_name == "Test Campaign"

@pytest.mark.asyncio
async def test_get_campaign_not_found():
    """Test handling of missing campaign"""
    service = CampaignService()
    
    with patch('app.services.database_client') as mock_db:
        mock_db.table('campaigns').select.return_value = AsyncMock(
            return_value={"data": []}
        )
        
        with pytest.raises(CampaignNotFoundError):
            await service.get_campaign("nonexistent")
```

#### Example: Agent Test

```python
# backend/packages/agents/tests/test_planner.py
import pytest
from src.planner import PlannerAgent

@pytest.mark.asyncio
async def test_planner_generates_strategy():
    """Test planner agent generates valid strategy"""
    planner = PlannerAgent()
    
    brief = {
        "campaign_name": "Test",
        "business_goal": "Increase sales",
        "budget_total": 5000,
        "channels": ["email"]
    }
    
    strategy = await planner.plan(brief)
    
    assert strategy.positioning is not None
    assert strategy.channel_plan is not None
    assert strategy.kpi_targets is not None
    assert len(strategy.channel_plan) > 0

@pytest.mark.asyncio
async def test_planner_validates_input():
    """Test planner handles invalid input"""
    planner = PlannerAgent()
    
    invalid_brief = {}  # Missing required fields
    
    with pytest.raises(ValueError, match="Invalid brief"):
        await planner.plan(invalid_brief)
```

### Pytest Configuration

```ini
# backend/apps/api/pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: tests requiring external services",
    "slow: slow running tests",
    "unit: unit tests"
]
addopts = "--cov=app --cov-report=term-missing --cov-report=xml"
```

## Frontend Testing

### Test Structure

```
frontend/apps/web/src/
├── components/
│   ├── CampaignCard.tsx
│   ├── CampaignCard.test.tsx    # Component test
│   └── CampaignCard.stories.tsx # Storybook (optional)
├── test/
│   ├── setup.ts                 # Test configuration
│   ├── mocks.ts                 # Mock data
│   └── fixtures.ts              # Test fixtures
└── app/
    └── campaigns/
        ├── page.tsx
        └── page.test.tsx        # Integration test
```

### Running Frontend Tests

```bash
# Run all tests
pnpm --filter @acm/web test

# Run with watch mode
pnpm --filter @acm/web test:watch

# Run with coverage
pnpm --filter @acm/web test:coverage

# Run specific test
pnpm --filter @acm/web test -- CampaignCard.test.tsx

# Run tests matching pattern
pnpm --filter @acm/web test -- --grep "Campaign"
```

### Writing Frontend Tests

#### Example: Component Test

```tsx
// frontend/apps/web/src/components/CampaignCard.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CampaignCard } from './CampaignCard';
import { Campaign } from '@acm/types';

describe('CampaignCard', () => {
  const mockCampaign: Campaign = {
    id: '1',
    campaign_name: 'Test Campaign',
    status: 'active',
    budget_total: 5000,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };

  it('renders campaign information', () => {
    render(<CampaignCard campaign={mockCampaign} />);
    
    expect(screen.getByText('Test Campaign')).toBeInTheDocument();
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it('displays edit button', () => {
    render(<CampaignCard campaign={mockCampaign} />);
    
    const editButton = screen.getByRole('button', { name: /edit/i });
    expect(editButton).toBeInTheDocument();
  });

  it('calls onEdit callback when button clicked', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    
    render(<CampaignCard campaign={mockCampaign} onEdit={onEdit} />);
    
    await user.click(screen.getByRole('button', { name: /edit/i }));
    
    expect(onEdit).toHaveBeenCalledWith(mockCampaign.id);
  });
});
```

#### Example: Hook Test

```tsx
// frontend/apps/web/src/hooks/useCampaigns.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { useCampaigns } from './useCampaigns';

describe('useCampaigns', () => {
  it('fetches campaigns on mount', async () => {
    const { result } = renderHook(() => useCampaigns());
    
    await waitFor(() => {
      expect(result.current.data).not.toBeUndefined();
    });
    
    expect(result.current.data).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ campaign_name: expect.any(String) })
      ])
    );
  });

  it('handles loading state', () => {
    const { result } = renderHook(() => useCampaigns());
    
    expect(result.current.isLoading).toBe(true);
  });
});
```

#### Example: Page Test

```tsx
// frontend/apps/web/src/app/campaigns/page.test.tsx
import { render, screen } from '@testing-library/react';
import CampaignsPage from './page';

// Mock API response
vi.mock('@/lib/api', () => ({
  getCampaigns: vi.fn(() => 
    Promise.resolve([
      { id: '1', campaign_name: 'Campaign 1', status: 'active' },
      { id: '2', campaign_name: 'Campaign 2', status: 'draft' }
    ])
  )
}));

describe('CampaignsPage', () => {
  it('renders campaign list', async () => {
    render(<CampaignsPage />);
    
    expect(screen.getByText('Campaign 1')).toBeInTheDocument();
    expect(screen.getByText('Campaign 2')).toBeInTheDocument();
  });
});
```

### Vitest Configuration

```ts
// frontend/apps/web/vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/']
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
});
```

## End-to-End Testing

### Test Structure

```
e2e/
├── auth-helpers.ts          # Auth utility functions
├── campaign-flow.spec.ts    # Campaign creation workflow
├── realtime.spec.ts         # WebSocket real-time events
└── approval-flow.spec.ts    # Approval gate workflow
```

### Running E2E Tests

```bash
# Run all E2E tests
pnpm test:e2e

# Run specific E2E test
pnpm exec playwright test e2e/campaign-flow.spec.ts

# Run in headed mode (see browser)
pnpm exec playwright test --headed

# Debug mode
pnpm exec playwright test --debug

# Run on specific browser
pnpm exec playwright test --project chromium
```

### Writing E2E Tests

```ts
// e2e/campaign-flow.spec.ts
import { test, expect } from '@playwright/test';
import { login } from './auth-helpers';

test.describe('Campaign Creation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
    await login(page, 'test@example.com', 'password');
  });

  test('user can create and launch campaign', async ({ page }) => {
    // Click create button
    await page.click('button:has-text("Create New Campaign")');
    
    // Fill in campaign form
    await page.fill('input[name="campaign_name"]', 'Test Campaign');
    await page.fill('textarea[name="business_goal"]', 'Increase sales');
    await page.fill('input[name="budget_total"]', '5000');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Verify campaign created
    await expect(page).toHaveURL(/\/campaigns\/\w+/);
    await expect(page.locator('h1')).toContainText('Test Campaign');
    
    // Start orchestration
    await page.click('button:has-text("Start Campaign")');
    
    // Wait for planner to complete
    await page.waitForSelector('text=Strategy Review Required', { timeout: 30000 });
    await expect(page.locator('.approval-card')).toBeVisible();
  });

  test('user can approve strategy', async ({ page }) => {
    // Navigate to existing campaign in review
    await page.goto('http://localhost:3000/campaigns/test-id');
    
    // Verify strategy approval pending
    await expect(page.locator('text=Strategy Review Required')).toBeVisible();
    
    // Approve strategy
    await page.click('button:has-text("Approve")');
    await page.fill('textarea[name="comments"]', 'Looks good');
    await page.click('button:has-text("Confirm")');
    
    // Verify workflow continues
    await expect(page.locator('text=Processing Content Creation')).toBeVisible({
      timeout: 15000
    });
  });
});
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install pnpm
        run: npm install -g pnpm
      
      - name: Install dependencies
        run: pnpm install
      
      - name: Backend tests
        run: pnpm test:backend
      
      - name: Frontend tests
        run: pnpm test:frontend
      
      - name: E2E tests
        run: pnpm test:e2e
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Testing Best Practices

### Do's

✅ Write tests as you write code  
✅ Test behavior, not implementation details  
✅ Use descriptive test names  
✅ Keep tests focused and independent  
✅ Mock external dependencies  
✅ Use fixtures for common setup  
✅ Test error cases, not just happy path  
✅ Aim for 80%+ coverage on critical paths  

### Don'ts

❌ Test framework implementation details  
❌ Create interdependent tests  
❌ Use `sleep()` in tests (use `waitFor`)  
❌ Make tests environment-specific  
❌ Mix unit and integration tests  
❌ Commit broken tests  
❌ Ignore flaky tests (fix them)  

## Test Data Management

### Mock Data Patterns

```python
# backend/tests/fixtures/campaigns.py
import pytest

@pytest.fixture
def mock_campaign_brief():
    return {
        "campaign_name": "Test Campaign",
        "business_goal": "Increase awareness",
        "target_audience": "18-34",
        "budget_total": 5000,
        "channels": ["email", "social"],
        "start_date": "2026-07-01",
        "end_date": "2026-07-31"
    }

@pytest.fixture
def mock_campaign_response(mock_campaign_brief):
    return {
        **mock_campaign_brief,
        "id": "campaign-uuid",
        "user_id": "user-uuid",
        "status": "draft",
        "created_at": "2026-06-29T10:00:00Z"
    }
```

```ts
// frontend/src/test/fixtures.ts
export const mockCampaign = {
  id: '1',
  campaign_name: 'Test Campaign',
  status: 'active' as const,
  budget_total: 5000,
  created_at: '2026-06-29T10:00:00Z',
  updated_at: '2026-06-29T10:00:00Z'
};
```

---

**Related**: See [REQUIREMENTS.md](REQUIREMENTS.md) for success criteria, [DEVELOPMENT.md](DEVELOPMENT.md) for setup

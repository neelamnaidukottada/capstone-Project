import type { Page } from '@playwright/test'

export async function seedAuthSession(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem(
      'acm-auth-session',
      JSON.stringify({
        access_token: 'e2e-access',
        refresh_token: 'e2e-refresh',
        token_type: 'bearer',
        expires_in: 900,
        expires_at: Date.now() + 15 * 60 * 1000,
        user: {
          id: 'user-e2e',
          email: 'e2e@example.com',
          full_name: 'E2E User',
          role: 'admin',
          organization_id: 'org-e2e',
          organization_name: 'E2E Org',
          email_verified: true,
        },
      })
    )
  })
}

export async function mockApi(page: Page): Promise<void> {
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-e2e',
        email: 'e2e@example.com',
        full_name: 'E2E User',
        role: 'admin',
        organization_id: 'org-e2e',
        organization_name: 'E2E Org',
        email_verified: true,
      }),
    })
  })

  await page.route('**/api/v1/campaigns', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ campaign_id: 'demo-001', status: 'running' }),
      })
      return
    }
    await route.continue()
  })

  await page.route('**/api/v1/campaigns/demo-001', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        campaign_id: 'demo-001',
        status: 'running',
        current_agent: 'planner',
        progress_percentage: 45,
        pending_approval: { type: 'strategy' },
        strategy: { objectives: ['Grow pipeline'] },
      }),
    })
  })

  await page.route('**/api/v1/campaigns/demo-001/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        campaign_id: 'demo-001',
        status: 'awaiting_strategy_approval',
        current_agent: 'planner',
        progress_percentage: 45,
        estimated_completion: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        error: null,
      }),
    })
  })

  await page.route('**/api/v1/campaigns/demo-001/approve', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Approval recorded and workflow resumed' }),
    })
  })

  await page.route('**/api/v1/campaigns/demo-001/report?format=json', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        campaign_id: 'demo-001',
        format: 'json',
        content: {
          executive_summary: 'Campaign completed with strong ROI',
        },
      }),
    })
  })
}

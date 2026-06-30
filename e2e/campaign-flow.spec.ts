import { expect, test } from '@playwright/test'
import { mockApi, seedAuthSession } from './auth-helpers'

test.beforeEach(async ({ page }) => {
  await seedAuthSession(page)
  await mockApi(page)
})

test('complete campaign creation flow', async ({ page }) => {
  await page.goto('/campaigns/new')

  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Submit Campaign' }).click()

  await expect(page).toHaveURL(/\/campaigns\/demo-001/)
})

test('human approval workflow', async ({ page }) => {
  await page.goto('/campaigns/demo-001')
  await page.getByRole('button', { name: 'Review Approval Request' }).click()
  await page.getByRole('button', { name: 'Approve' }).click()
  await expect(page.getByText('Workflow Progress')).toBeVisible()
})

test('report generation and download actions', async ({ page }) => {
  await page.goto('/campaigns/demo-001/report')
  await expect(page.getByText('Final Report')).toBeVisible()
  await expect(page.getByText('Campaign completed with strong ROI')).toBeVisible()

  await page.getByRole('button', { name: 'Download PDF' }).click()
  await page.getByRole('button', { name: 'Download Markdown' }).click()
  await page.getByRole('button', { name: 'Share Report' }).click()
  await expect(page.locator('div.font-semibold', { hasText: 'Report link copied' }).first()).toBeVisible()
})

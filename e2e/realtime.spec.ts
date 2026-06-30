import { expect, test } from '@playwright/test'
import { mockApi, seedAuthSession } from './auth-helpers'

test('real-time updates verification', async ({ page }) => {
  await seedAuthSession(page)
  await mockApi(page)

  await page.addInitScript(() => {
    const OriginalWebSocket = window.WebSocket

    class FakeWebSocket {
      onopen = null
      onmessage = null
      onclose = null
      onerror = null
      constructor() {
        setTimeout(() => {
          if (this.onopen) {
            this.onopen(new Event('open'))
          }
          if (this.onmessage) {
            this.onmessage({
              data: JSON.stringify({
                event: 'agent_completed',
                timestamp: new Date().toISOString(),
                agent_name: 'strategic_planner',
                output_summary: 'Strategy generated',
                latency: 120,
              }),
            })
          }
        }, 25)
      }
      send() {}
      close() {
        if (this.onclose) this.onclose(new CloseEvent('close'))
      }
    }

    // Only mock campaign sockets; preserve native WebSocket for Next/runtime internals.
    window.WebSocket = function (url: string | URL, protocols?: string | string[]) {
      const normalized = typeof url === 'string' ? url : url.toString()
      if (normalized.includes('/ws/campaigns/')) {
        return new FakeWebSocket() as unknown as WebSocket
      }
      return protocols !== undefined
        ? new OriginalWebSocket(normalized, protocols)
        : new OriginalWebSocket(normalized)
    } as unknown as typeof WebSocket

    window.WebSocket.prototype = OriginalWebSocket.prototype
    window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING
    window.WebSocket.OPEN = OriginalWebSocket.OPEN
    window.WebSocket.CLOSING = OriginalWebSocket.CLOSING
    window.WebSocket.CLOSED = OriginalWebSocket.CLOSED
  })

  await page.goto('/campaigns/demo-001')
  const wsStatus = page.locator('p', { hasText: 'WebSocket:' }).first()
  await expect(wsStatus).toBeVisible()
  await expect(wsStatus).toContainText(/connected|reconnecting/i)
  await expect(page.getByText('Strategy generated').first()).toBeVisible()
})

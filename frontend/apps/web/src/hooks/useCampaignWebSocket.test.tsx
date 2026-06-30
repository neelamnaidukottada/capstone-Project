import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { parseCampaignSocketEvent, useCampaignWebSocket } from '@/hooks/useCampaignWebSocket'

vi.mock('@/lib/auth-session', () => ({
  getValidAccessToken: vi.fn(async () => 'token-123'),
}))

vi.mock('@/components/toaster', () => ({
  useToast: () => ({ notify: vi.fn() }),
}))

class MockWebSocket {
  static instances: MockWebSocket[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((evt: { data: string }) => void) | null = null

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
    // Fire onopen on the next microtask so React state is updated before waitFor polls
    Promise.resolve().then(() => this.onopen?.())
  }

  send = vi.fn()
  close = vi.fn(() => {
    this.onclose?.()
  })
}

describe('useCampaignWebSocket', () => {
  it('parses valid contract event and rejects unknown payload', () => {
    const parsed = parseCampaignSocketEvent(
      JSON.stringify({
        event: 'agent_started',
        timestamp: '2026-01-01T00:00:00Z',
        agent_name: 'planner',
        input_summary: 'starting',
      })
    )
    expect(parsed?.event).toBe('agent_started')

    const invalid = parseCampaignSocketEvent(JSON.stringify({ event: 'agent_started' }))
    expect(invalid).toBeNull()
  })

  it('connects and updates status', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket)

    const queryClient = new QueryClient()
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useCampaignWebSocket('11111111-1111-4111-8111-111111111111'), { wrapper })

    await waitFor(() => {
      expect(result.current.status).toBe('connected')
    })

    const ws = MockWebSocket.instances[0]
    ws.onmessage?.({
      data: JSON.stringify({
        event: 'agent_completed',
        timestamp: '2026-01-01T00:00:00Z',
        agent_name: 'planner',
        output_summary: 'done',
        latency: 42,
      }),
    })

    await waitFor(() => {
      expect(result.current.lastEvent?.event).toBe('agent_completed')
    })
  })
})

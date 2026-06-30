import { describe, expect, it } from 'vitest'
import { useCampaignStore } from '@/stores/campaign-store'

describe('campaign store', () => {
  it('adds and trims realtime events', () => {
    useCampaignStore.getState().clearRealtimeEvents()
    for (let i = 0; i < 60; i += 1) {
      useCampaignStore.getState().addRealtimeEvent({
        id: String(i),
        agent: 'planner',
        status: 'running',
        message: `Event ${i}`,
        timestamp: '12:00:00',
      })
    }

    const events = useCampaignStore.getState().realtimeEvents
    expect(events).toHaveLength(50)
    expect(events[0].id).toBe('59')
  })

  it('sets websocket error', () => {
    useCampaignStore.getState().setWebsocketError('Socket down')
    expect(useCampaignStore.getState().websocketError).toBe('Socket down')
  })
})

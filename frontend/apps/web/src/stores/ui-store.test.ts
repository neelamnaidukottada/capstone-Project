import { describe, expect, it } from 'vitest'
import { useUIStore } from '@/stores/ui-store'

describe('ui store', () => {
  it('updates websocket status and derived wsConnected flag', () => {
    useUIStore.setState({ wsStatus: 'disconnected', wsConnected: false })
    useUIStore.getState().setWsStatus('connected')

    expect(useUIStore.getState().wsStatus).toBe('connected')
    expect(useUIStore.getState().wsConnected).toBe(true)

    useUIStore.getState().setWsStatus('reconnecting')
    expect(useUIStore.getState().wsConnected).toBe(false)
  })
})

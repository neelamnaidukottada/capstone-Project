import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { WebSocketReconnectState } from '@/components/websocket-reconnect-state'
import { useUIStore } from '@/stores/ui-store'

describe('WebSocketReconnectState', () => {
  it('hides when connected', () => {
    useUIStore.setState({ wsStatus: 'connected', wsConnected: true })
    const { container } = render(<WebSocketReconnectState />)
    expect(container.textContent).toBe('')
  })

  it('shows reconnecting message', () => {
    useUIStore.setState({ wsStatus: 'reconnecting', wsConnected: false })
    render(<WebSocketReconnectState />)
    expect(screen.getByText('Connection dropped. Reconnecting with backoff...')).toBeInTheDocument()
  })
})

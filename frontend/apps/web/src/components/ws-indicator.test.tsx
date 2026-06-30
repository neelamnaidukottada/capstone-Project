import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { WebSocketIndicator } from '@/components/ws-indicator'
import { useUIStore } from '@/stores/ui-store'

describe('WebSocketIndicator', () => {
  it('shows connected label', () => {
    useUIStore.setState({ wsStatus: 'connected', wsConnected: true })
    render(<WebSocketIndicator />)
    expect(screen.getByText('Realtime Connected')).toBeInTheDocument()
  })

  it('shows reconnecting label', () => {
    useUIStore.setState({ wsStatus: 'reconnecting', wsConnected: false })
    render(<WebSocketIndicator />)
    expect(screen.getByText('Realtime Reconnecting')).toBeInTheDocument()
  })
})

import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from '@/components/status-badge'

describe('StatusBadge', () => {
  it('renders formatted status text', () => {
    render(<StatusBadge status="awaiting_strategy_approval" />)
    expect(screen.getByText('awaiting strategy approval')).toBeInTheDocument()
  })

  it('renders completed state', () => {
    render(<StatusBadge status="completed" />)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })
})

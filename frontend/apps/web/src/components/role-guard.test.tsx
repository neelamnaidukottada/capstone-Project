import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RoleGuard } from '@/components/role-guard'

vi.mock('@/components/auth-provider', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/components/auth-provider'

describe('RoleGuard', () => {
  it('renders children when user meets role', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'u1',
        email: 'admin@example.com',
        full_name: 'Admin User',
        role: 'admin',
        organization_id: 'org-1',
        organization_name: 'Org',
        email_verified: true,
      },
    } as never)

    render(
      <RoleGuard minimumRole="manager">
        <div>Secret</div>
      </RoleGuard>
    )

    expect(screen.getByText('Secret')).toBeInTheDocument()
  })

  it('hides children when user does not meet role', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'u2',
        email: 'viewer@example.com',
        full_name: 'Viewer User',
        role: 'viewer',
        organization_id: 'org-1',
        organization_name: 'Org',
        email_verified: true,
      },
    } as never)

    render(
      <RoleGuard minimumRole="admin">
        <div>Admin Content</div>
      </RoleGuard>
    )

    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })
})

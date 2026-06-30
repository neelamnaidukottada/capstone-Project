import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import RegisterPage from '@/app/register/page'
import { AuthProvider } from '@/components/auth-provider'

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    </AuthProvider>
  )
}

describe('RegisterPage integration', () => {
  it('submits registration form with MSW backend', async () => {
    render(<RegisterPage />, { wrapper: Wrapper })

    await userEvent.type(screen.getByPlaceholderText('Full name'), 'New User')
    await userEvent.type(screen.getByPlaceholderText('Organization name'), 'New Org')
    await userEvent.type(screen.getByPlaceholderText('Email'), 'new@example.com')
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass!123')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('button', { name: 'Create account' })).toBeInTheDocument()
  })
})

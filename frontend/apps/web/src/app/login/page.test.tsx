import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import LoginPage from '@/app/login/page'
import { AuthProvider } from '@/components/auth-provider'

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    </AuthProvider>
  )
}

describe('LoginPage integration', () => {
  it('submits login form with MSW backend', async () => {
    render(<LoginPage />, { wrapper: Wrapper })

    await userEvent.type(screen.getByPlaceholderText('Email'), 'user@example.com')
    await userEvent.type(screen.getByPlaceholderText('Password'), 'StrongPass!123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('button', { name: 'Continue with Google' })).toBeInTheDocument()
  })
})

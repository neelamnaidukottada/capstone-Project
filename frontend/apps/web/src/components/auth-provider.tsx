'use client'

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { Route } from 'next'
import { useRouter } from 'next/navigation'
import {
  getMe,
  getOAuthStartUrl,
  login as loginRequest,
  logout as logoutRequest,
  refresh as refreshRequest,
  register as registerRequest,
} from '@/lib/auth-api'
import { clearSession, getStoredSession, saveSession } from '@/lib/auth-storage'
import type { AuthSession, AuthState, LoginInput, RegisterInput } from '@/types/auth'

type AuthContextValue = AuthState & {
  login: (input: LoginInput) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  loginWithOAuth: (provider: 'google' | 'github') => Promise<void>
  refreshSession: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [status, setStatus] = useState<AuthState['status']>('loading')
  const [session, setSession] = useState<AuthSession | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applySession = useCallback((nextSession: AuthSession | null) => {
    setSession(nextSession)
    if (nextSession) {
      saveSession(nextSession)
      setStatus('authenticated')
      setError(null)
      return
    }

    clearSession()
    setStatus('unauthenticated')
  }, [])

  const refreshSession = useCallback(async () => {
    const current = getStoredSession()
    if (!current) {
      applySession(null)
      return
    }

    try {
      const next = await refreshRequest(current.refresh_token)
      applySession(next)
    } catch (err) {
      applySession(null)
      setError(err instanceof Error ? err.message : 'Unable to refresh session')
    }
  }, [applySession])

  useEffect(() => {
    const initial = getStoredSession()
    if (!initial) {
      setStatus('unauthenticated')
      return
    }

    const remaining = initial.expires_at - Date.now()
    if (remaining <= 0) {
      void refreshSession()
      return
    }

    void getMe(initial.access_token)
      .then((user) => {
        applySession({ ...initial, user })
      })
      .catch(async () => {
        await refreshSession()
      })
  }, [applySession, refreshSession])

  useEffect(() => {
    if (status !== 'authenticated' || !session) return

    const interval = window.setInterval(() => {
      const remainingMs = session.expires_at - Date.now()
      if (remainingMs <= 60_000) {
        void refreshSession()
      }
    }, 30_000)

    return () => {
      window.clearInterval(interval)
    }
  }, [refreshSession, session, status])

  const login = useCallback(async (input: LoginInput) => {
    const next = await loginRequest(input)
    applySession(next)
    router.replace('/dashboard')
  }, [applySession, router])

  const register = useCallback(async (input: RegisterInput) => {
    const next = await registerRequest(input)
    applySession(next)
    router.replace('/dashboard')
  }, [applySession, router])

  const loginWithOAuth = useCallback(async (provider: 'google' | 'github') => {
    const url = await getOAuthStartUrl(provider)
    window.location.assign(url)
  }, [])

  const logout = useCallback(async () => {
    const current = getStoredSession()
    try {
      if (current) {
        await logoutRequest(current.refresh_token)
      }
    } finally {
      applySession(null)
      router.replace('/login' as Route)
      router.refresh()
    }
  }, [applySession, router])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      session,
      error,
      login,
      register,
      loginWithOAuth,
      refreshSession,
      logout,
    }),
    [error, login, loginWithOAuth, logout, refreshSession, register, session, status]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}

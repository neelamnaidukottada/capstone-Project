import type { AuthSession } from '@/types/auth'

const AUTH_STORAGE_KEY = 'acm-auth-session'

export function getStoredSession(): AuthSession | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) return null

  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

export function saveSession(session: AuthSession): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

export function clearSession(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(AUTH_STORAGE_KEY)
}

export function getAccessTokenFromStorage(): string | null {
  return getStoredSession()?.access_token ?? null
}

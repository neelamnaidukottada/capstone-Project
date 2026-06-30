import { refresh } from '@/lib/auth-api'
import { clearSession, getStoredSession, saveSession } from '@/lib/auth-storage'

let refreshPromise: Promise<string | null> | null = null

export async function getValidAccessToken(): Promise<string | null> {
  const session = getStoredSession()
  if (!session) return null

  const remainingMs = session.expires_at - Date.now()
  if (remainingMs > 60_000) {
    return session.access_token
  }

  if (!refreshPromise) {
    refreshPromise = refresh(session.refresh_token)
      .then((next) => {
        saveSession(next)
        return next.access_token
      })
      .catch(() => {
        clearSession()
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

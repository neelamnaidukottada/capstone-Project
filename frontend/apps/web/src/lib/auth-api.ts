import type { AuthSession, AuthUser, LoginInput, RegisterInput } from '@/types/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type AuthResponse = {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

function toSession(payload: AuthResponse): AuthSession {
  return {
    ...payload,
    expires_at: Date.now() + payload.expires_in * 1000,
  }
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })

  if (!res.ok) {
    let message = `Auth request failed (${res.status})`
    try {
      const body = await res.json()
      const detail = body?.error?.message ?? body?.detail ?? body?.message
      const fieldErrors: string[] = body?.error?.details
        ?.map((d: { loc?: string[]; msg?: string }) => {
          const field = d.loc?.slice(1).join('.') ?? 'field'
          return `${field}: ${d.msg}`
        })
        .filter(Boolean) ?? []
      if (fieldErrors.length > 0) {
        message = fieldErrors.join(' | ')
      } else if (detail) {
        message = typeof detail === 'string' ? detail : JSON.stringify(detail)
      }
    } catch {
      const text = await res.text()
      if (text) {
        message = text
      }
    }
    throw new Error(message)
  }

  return (await res.json()) as T
}

export async function register(input: RegisterInput): Promise<AuthSession> {
  const payload = await jsonRequest<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  return toSession(payload)
}

export async function login(input: LoginInput): Promise<AuthSession> {
  const payload = await jsonRequest<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  return toSession(payload)
}

export async function refresh(refreshToken: string): Promise<AuthSession> {
  const payload = await jsonRequest<AuthResponse>('/api/v1/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  return toSession(payload)
}

export async function logout(refreshToken: string): Promise<void> {
  await jsonRequest('/api/v1/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
}

export async function getMe(accessToken: string): Promise<AuthUser> {
  return jsonRequest<AuthUser>('/api/v1/auth/me', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
}

export async function requestPasswordReset(email: string): Promise<void> {
  await jsonRequest('/api/v1/auth/password/forgot', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function resetPassword(input: { access_token: string; refresh_token: string; new_password: string }): Promise<void> {
  await jsonRequest('/api/v1/auth/password/reset', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function resendVerification(email: string): Promise<void> {
  await jsonRequest('/api/v1/auth/verify-email/resend', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function getOAuthStartUrl(provider: 'google' | 'github'): Promise<string> {
  const payload = await jsonRequest<{ authorization_url: string }>(`/api/v1/auth/oauth/${provider}/start`)
  return payload.authorization_url
}

export async function exchangeOAuthSession(accessToken: string): Promise<AuthSession> {
  const payload = await jsonRequest<AuthResponse>('/api/v1/auth/oauth/session', {
    method: 'POST',
    body: JSON.stringify({ access_token: accessToken }),
  })
  return toSession(payload)
}

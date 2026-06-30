export type UserRole = 'admin' | 'manager' | 'viewer'

export type AuthUser = {
  id: string
  email: string
  full_name: string
  role: UserRole
  organization_id: string
  organization_name?: string | null
  email_verified: boolean
}

export type AuthTokens = {
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: 'bearer'
}

export type AuthSession = AuthTokens & {
  user: AuthUser
  expires_at: number
}

export type AuthState = {
  status: 'loading' | 'authenticated' | 'unauthenticated'
  user: AuthUser | null
  session: AuthSession | null
  error: string | null
}

export type LoginInput = {
  email: string
  password: string
}

export type RegisterInput = {
  email: string
  password: string
  full_name: string
  organization_name: string
}

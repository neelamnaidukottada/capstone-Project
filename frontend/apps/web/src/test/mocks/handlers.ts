import { http, HttpResponse } from 'msw'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const handlers = [
  http.post(`${API_URL}/api/v1/auth/login`, async () => {
    return HttpResponse.json({
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      token_type: 'bearer',
      expires_in: 900,
      user: {
        id: 'user-1',
        email: 'user@example.com',
        full_name: 'Test User',
        role: 'admin',
        organization_id: 'org-1',
        organization_name: 'Test Org',
        email_verified: true,
      },
    })
  }),
  http.post(`${API_URL}/api/v1/auth/register`, async () => {
    return HttpResponse.json({
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      token_type: 'bearer',
      expires_in: 900,
      user: {
        id: 'user-2',
        email: 'new@example.com',
        full_name: 'New User',
        role: 'admin',
        organization_id: 'org-2',
        organization_name: 'New Org',
        email_verified: false,
      },
    })
  }),
  http.get(`${API_URL}/api/v1/auth/me`, async () => {
    return HttpResponse.json({
      id: 'user-1',
      email: 'user@example.com',
      full_name: 'Test User',
      role: 'admin',
      organization_id: 'org-1',
      organization_name: 'Test Org',
      email_verified: true,
    })
  }),
]

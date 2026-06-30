import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from '@/test/mocks/server'

vi.mock('next/navigation', () => {
  const push = vi.fn()
  const replace = vi.fn()
  const refresh = vi.fn()

  return {
    useRouter: () => ({ push, replace, refresh }),
    usePathname: () => '/dashboard',
    useSearchParams: () => new URLSearchParams(''),
    useParams: () => ({ id: 'demo-001' }),
  }
})

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())

'use client'

import { useEffect } from 'react'
import type { Route } from 'next'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth-provider'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { status } = useAuth()

  useEffect(() => {
    if (status === 'unauthenticated') {
      const target = encodeURIComponent(pathname || '/dashboard')
      router.replace((`/login?next=${target}` as Route))
    }
  }, [pathname, router, status])

  if (status === 'loading') {
    return <div className="p-6 text-sm text-muted-foreground">Checking session...</div>
  }

  if (status !== 'authenticated') {
    return null
  }

  return <>{children}</>
}

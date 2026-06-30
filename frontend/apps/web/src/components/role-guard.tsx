'use client'

import React from 'react'
import { useAuth } from '@/components/auth-provider'
import type { UserRole } from '@/types/auth'

const ROLE_ORDER: Record<UserRole, number> = {
  viewer: 10,
  manager: 20,
  admin: 30,
}

export function RoleGuard({
  minimumRole,
  children,
}: {
  minimumRole: UserRole
  children: React.ReactNode
}) {
  const { user } = useAuth()

  if (!user) return null
  if (ROLE_ORDER[user.role] < ROLE_ORDER[minimumRole]) {
    return null
  }

  return <>{children}</>
}

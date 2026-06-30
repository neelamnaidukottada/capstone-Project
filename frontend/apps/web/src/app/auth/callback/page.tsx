'use client'

import { useEffect } from 'react'
import type { Route } from 'next'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { exchangeOAuthSession } from '@/lib/auth-api'
import { saveSession } from '@/lib/auth-storage'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    const run = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getSession()
      const session = data.session

      if (!session?.access_token) {
        router.replace('/login' as Route)
        return
      }

      const backendSession = await exchangeOAuthSession(session.access_token).catch(() => null)

      if (backendSession) {
        saveSession(backendSession)
      }
      router.replace('/dashboard' as Route)
    }

    void run()
  }, [router])

  return <div className="p-6 text-sm text-muted-foreground">Completing OAuth sign-in...</div>
}

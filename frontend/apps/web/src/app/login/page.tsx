'use client'

import Link from 'next/link'
import type { Route } from 'next'
import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { useAuth } from '@/components/auth-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

function LoginContent() {
  const params = useSearchParams()
  const next = params.get('next')
  const { login, loginWithOAuth, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Sign In</CardTitle>
          <CardDescription>Access your organization workspace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="space-y-3"
            onSubmit={async (e) => {
              e.preventDefault()
              setLoading(true)
              setLocalError(null)
              try {
                await login({ email, password })
                if (next) {
                  window.location.assign(decodeURIComponent(next))
                }
              } catch (err) {
                setLocalError(err instanceof Error ? err.message : 'Login failed')
              } finally {
                setLoading(false)
              }
            }}
          >
            <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            {(localError || error) ? <p className="text-sm text-destructive">{localError || error}</p> : null}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <div className="grid grid-cols-1 gap-2">
            <Button variant="outline" onClick={() => loginWithOAuth('google')}>Continue with Google</Button>
            <Button variant="outline" onClick={() => loginWithOAuth('github')}>Continue with GitHub</Button>
          </div>

          <p className="text-sm text-muted-foreground">
            No account? <Link href={'/register' as Route} className="underline">Create organization</Link>
          </p>
          <p className="text-sm text-muted-foreground">
            Forgot password? <Link href={'/auth/forgot' as Route} className="underline">Reset here</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading sign-in...</div>}>
      <LoginContent />
    </Suspense>
  )
}

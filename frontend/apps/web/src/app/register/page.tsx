'use client'

import Link from 'next/link'
import type { Route } from 'next'
import { useState } from 'react'
import { useAuth } from '@/components/auth-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

export default function RegisterPage() {
  const { register, error } = useAuth()
  const [fullName, setFullName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Create Organization Account</CardTitle>
          <CardDescription>Start as organization admin.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="space-y-3"
            onSubmit={async (e) => {
              e.preventDefault()
              setLoading(true)
              setLocalError(null)
              try {
                await register({
                  full_name: fullName,
                  organization_name: orgName,
                  email,
                  password,
                })
              } catch (err) {
                setLocalError(err instanceof Error ? err.message : 'Registration failed')
              } finally {
                setLoading(false)
              }
            }}
          >
            <Input placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            <Input placeholder="Organization name" value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
            <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            {(localError || error) ? <p className="text-sm text-destructive">{localError || error}</p> : null}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Creating account...' : 'Create account'}
            </Button>
          </form>

          <p className="text-sm text-muted-foreground">
            Already have an account? <Link href={'/login' as Route} className="underline">Sign in</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

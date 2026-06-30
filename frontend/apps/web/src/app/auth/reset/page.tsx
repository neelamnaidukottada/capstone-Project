'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { resetPassword } from '@/lib/auth-api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function ResetPasswordContent() {
  const params = useSearchParams()
  const accessToken = params.get('access_token') ?? ''
  const refreshToken = params.get('refresh_token') ?? ''
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setMessage('')
    try {
      await resetPassword({
        access_token: accessToken,
        refresh_token: refreshToken,
        new_password: password,
      })
      setMessage('Password updated successfully. You can now sign in.')
      setPassword('')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to reset password'
      setError(errorMessage)
      console.error('Password reset error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <div className="w-full rounded-lg border p-6">
        <h1 className="text-lg font-semibold">Reset password</h1>
        <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
          <Input type="password" placeholder="New password" value={password} onChange={(e) => setPassword(e.target.value)} required disabled={loading} minLength={8} />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Updating...' : 'Update password'}
          </Button>
        </form>
        {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
        {message ? <p className="mt-3 text-sm text-emerald-600">{message}</p> : null}
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading reset form...</div>}>
      <ResetPasswordContent />
    </Suspense>
  )
}

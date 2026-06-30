'use client'

import Link from 'next/link'
import type { Route } from 'next'

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <div className="rounded-lg border p-6">
        <h1 className="text-lg font-semibold">Check your email</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Verification link has been sent. Open the link to activate your account.
        </p>
        <Link className="mt-4 inline-block text-sm underline" href={'/login' as Route}>
          Return to sign in
        </Link>
      </div>
    </div>
  )
}

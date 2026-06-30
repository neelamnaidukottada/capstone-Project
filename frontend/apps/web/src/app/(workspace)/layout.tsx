import { AppShell } from '@/components/app-shell'
import { ProtectedRoute } from '@/components/protected-route'

export const dynamic = 'force-dynamic'

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

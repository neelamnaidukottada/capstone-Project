import { SidebarNav } from '@/components/sidebar-nav'
import { TopBar } from '@/components/top-bar'

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_right,_hsl(var(--primary)/0.12),_transparent_42%),radial-gradient(circle_at_bottom_left,_hsl(var(--accent)/0.12),_transparent_48%)]">
      <div className="mx-auto flex max-w-[1600px]">
        <SidebarNav />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          <main className="flex-1 p-4 md:p-8">{children}</main>
        </div>
      </div>
    </div>
  )
}

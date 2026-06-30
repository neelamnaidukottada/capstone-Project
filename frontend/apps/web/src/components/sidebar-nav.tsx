'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { Route } from 'next'
import { LayoutDashboard, Rocket, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '@/components/auth-provider'
import { useToast } from '@/components/toaster'
import { deleteCampaign, getCampaigns } from '@/lib/api'
import { cn } from '@/lib/utils'

const items = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/campaigns/new', label: 'New Campaign', icon: Rocket },
]

type Campaign = {
  campaign_id: string
  name: string | null
}

export function SidebarNav() {
  const pathname = usePathname()
  const { user, status } = useAuth()
  const { notify } = useToast()
  const isViewer = user?.role === 'viewer'
  const navItems = isViewer ? items.filter((item) => item.href !== '/campaigns/new') : items

  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (status === 'loading') {
      return
    }

    if (status !== 'authenticated' || !user) {
      setCampaigns([])
      setLoading(false)
      return
    }

    let active = true

    const fetchCampaigns = async () => {
      try {
        if (!active) return
        const data = await getCampaigns(50, 0)
        if (!active) return
        setCampaigns(data.campaigns.slice(0, 10) || [])
      } catch (_err) {
        if (!active) return
        // Silently fail - sidebar won't show campaign list if API fails
        setCampaigns([])
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    setLoading(true)
    fetchCampaigns()

    const interval = window.setInterval(fetchCampaigns, 5000)

    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [status, user])

  const handleDeleteCampaign = async (campaignId: string, campaignName: string | null) => {
    const label = campaignName || 'Untitled Campaign'
    const confirmed = window.confirm(`Delete "${label}"? This cannot be undone.`)
    if (!confirmed) return

    try {
      await deleteCampaign(campaignId)
      setCampaigns((prev) => prev.filter((c) => c.campaign_id !== campaignId))
      notify('Campaign deleted', label)
    } catch (err) {
      notify('Delete failed', err instanceof Error ? err.message : 'Unable to delete campaign')
    }
  }

  return (
    <aside className="hidden w-72 shrink-0 border-r bg-card/70 p-4 lg:block">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Workspace</p>
        <h2 className="text-xl font-semibold">Campaign OS</h2>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => {
          const active = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              href={item.href as Route}
              key={item.href}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="mt-8">
        <p className="mb-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">Campaigns</p>
        <div className="space-y-1">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading...
            </div>
          ) : campaigns.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No campaigns yet</p>
          ) : (
            campaigns.map((campaign) => (
              <div
                key={campaign.campaign_id}
                className={cn(
                  'group flex items-center gap-1 rounded-md px-2 py-1 transition-colors',
                  pathname === `/campaigns/${campaign.campaign_id}`
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Link
                  href={`/campaigns/${campaign.campaign_id}` as Route}
                  className="min-w-0 flex-1 truncate rounded-md px-1 py-1 text-sm"
                  title={campaign.name || 'Untitled Campaign'}
                >
                  {campaign.name || 'Untitled Campaign'}
                </Link>

                {!isViewer ? (
                  <button
                    type="button"
                    onClick={() => void handleDeleteCampaign(campaign.campaign_id, campaign.name)}
                    className={cn(
                      'rounded p-1 transition-colors',
                      pathname === `/campaigns/${campaign.campaign_id}`
                        ? 'text-primary-foreground/80 hover:bg-primary-foreground/20 hover:text-primary-foreground'
                        : 'opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive'
                    )}
                    aria-label={`Delete ${campaign.name || 'Untitled Campaign'}`}
                    title="Delete campaign"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  )
}

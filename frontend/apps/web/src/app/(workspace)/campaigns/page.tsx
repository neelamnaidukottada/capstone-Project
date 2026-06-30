'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { ArrowUpRight, ChevronLeft, Rocket, Trash2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/components/auth-provider'
import { StatusBadge } from '@/components/status-badge'
import { useToast } from '@/components/toaster'
import { deleteCampaign, getCampaigns } from '@/lib/api'

type Campaign = {
  campaign_id: string
  name: string | null
  status: string
  updated_at: string
  pending_approval?: boolean | { type?: string } | null
}

const statusLabels: Record<string, string> = {
  running: 'Active Campaigns',
  completed: 'Completed',
  pending_approval: 'Pending Approval',
}

const statusToFilter: Record<string, string> = {
  running: 'running',
  completed: 'completed',
  pending_approval: 'awaiting_strategy_approval',
}

export default function CampaignsPage() {
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const { notify } = useToast()
  const statusParam = searchParams.get('status') || 'running'
  const isViewer = user?.role === 'viewer'

  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const pageTitle = statusLabels[statusParam] || 'Campaigns'
  const filterValue = statusToFilter[statusParam] || statusParam

  useEffect(() => {
    const fetchCampaigns = async () => {
      try {
        setLoading(true)
        const data = await getCampaigns(500, 0)
        
        // Filter campaigns by status
        const filtered = data.campaigns.filter((c) => {
          if (statusParam === 'pending_approval') {
            // Check both pending_approval field AND all status values that indicate approval needed
            return (
              c.pending_approval !== null && c.pending_approval !== undefined
            ) || 
            (c.status && c.status.includes('awaiting')) ||
            c.status === 'awaiting_strategy_approval' || 
            c.status === 'awaiting_media_plan_approval' ||
            c.status === 'awaiting_budget_approval' ||
            c.status === 'awaiting_human_approval' ||
            c.status === 'awaiting_approval'
          }
          return c.status === filterValue
        })

        setCampaigns(
          filtered.map((c) => ({
            campaign_id: c.campaign_id,
            name: c.name || 'Untitled Campaign',
            status: c.status,
            updated_at: formatUpdatedTime(c.updated_at),
          }))
        )
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load campaigns')
        setCampaigns([])
      } finally {
        setLoading(false)
      }
    }

    fetchCampaigns()
  }, [statusParam, filterValue])

  const formatUpdatedTime = (isoString: string) => {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins} min ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    return date.toLocaleDateString()
  }

  const handleDeleteCampaign = async (campaign: Campaign) => {
    const label = campaign.name || 'Untitled Campaign'
    const confirmed = window.confirm(`Delete "${label}"? This cannot be undone.`)
    if (!confirmed) return

    try {
      setDeletingId(campaign.campaign_id)
      await deleteCampaign(campaign.campaign_id)
      setCampaigns((prev) => prev.filter((c) => c.campaign_id !== campaign.campaign_id))
      notify('Campaign deleted', label)
    } catch (err) {
      notify('Delete failed', err instanceof Error ? err.message : 'Unable to delete campaign')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="rounded-md p-2 hover:bg-muted">
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <div>
            <h2 className="text-3xl font-bold tracking-tight">{pageTitle}</h2>
            <p className="mt-1 text-sm text-muted-foreground">View all {pageTitle.toLowerCase()}</p>
          </div>
        </div>

        <Button asChild className="gap-2">
          <Link href="/campaigns/new">
            <Rocket className="h-4 w-4" />
            Create New Campaign
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Campaigns</CardTitle>
          <CardDescription>All campaigns in this category</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading campaigns...</p>
          ) : error ? (
            <p className="text-sm text-red-600">Error: {error}</p>
          ) : campaigns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No campaigns in this category yet.</p>
          ) : (
            <div className="space-y-2">
              {campaigns.map((campaign) => (
                <div
                  key={campaign.campaign_id}
                  className="flex items-center justify-between rounded-lg border p-4 transition-all hover:bg-muted/50 hover:border-primary/50"
                >
                  <Link href={`/campaigns/${campaign.campaign_id}`} className="min-w-0 flex-1">
                    <p className="font-medium">{campaign.name}</p>
                    <p className="text-sm text-muted-foreground">{campaign.updated_at}</p>
                  </Link>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={campaign.status} />
                    <Link href={`/campaigns/${campaign.campaign_id}`} className="rounded p-1 text-muted-foreground hover:bg-muted">
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>
                    {!isViewer ? (
                      <button
                        type="button"
                        onClick={() => void handleDeleteCampaign(campaign)}
                        disabled={deletingId === campaign.campaign_id}
                        className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-50"
                        aria-label={`Delete ${campaign.name || 'Untitled Campaign'}`}
                        title="Delete campaign"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

'use client'

import Link from 'next/link'
import { useEffect, useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { ArrowUpRight, Rocket, Wallet } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/status-badge'
import { getCampaigns } from '@/lib/api'

type Campaign = {
  campaign_id: string
  name: string | null
  status: string
  budget_total?: number | null
  roi?: number | null
  updated_at: string
  pending_approval?: boolean | { type?: string } | null
}

type OverviewItem = {
  label: string
  value: number
  status: string
  filterValue: string
}

const inProgressStatuses = new Set([
  'running',
  'strategy_ready',
  'content_ready',
  'media_plan_ready',
  'performance_ready',
  'awaiting_strategy_approval',
  'awaiting_media_plan_approval',
  'awaiting_budget_approval',
  'awaiting_human_approval',
  'awaiting_approval',
])

function isInProgressStatus(status: string | null | undefined): boolean {
  if (!status) return false
  return inProgressStatuses.has(status) || status.includes('awaiting')
}

export default function DashboardPage() {
  const [allCampaigns, setAllCampaigns] = useState<Campaign[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Calculate overview counts from all campaigns
  const overview = useMemo<OverviewItem[]>(() => {
    const active = allCampaigns.filter((c) => isInProgressStatus(c.status)).length
    const completed = allCampaigns.filter((c) => c.status === 'completed').length
    // Check both pending_approval field AND all status values that indicate approval needed
    const pending = allCampaigns.filter((c) => 
      c.pending_approval || 
      c.status?.includes('awaiting') ||
      c.status === 'awaiting_strategy_approval' || 
      c.status === 'awaiting_media_plan_approval' ||
      c.status === 'awaiting_budget_approval' ||
      c.status === 'awaiting_human_approval' ||
      c.status === 'awaiting_approval'
    ).length

    return [
      { label: 'Active Campaigns', value: active, status: 'running', filterValue: 'running' },
      { label: 'Completed', value: completed, status: 'completed', filterValue: 'completed' },
      { label: 'Pending Approval', value: pending, status: 'awaiting_strategy_approval', filterValue: 'pending_approval' },
    ]
  }, [allCampaigns])

  const quickStats = useMemo(() => {
    const totalCampaigns = allCampaigns.length
    const totalSpend = allCampaigns.reduce((sum, c) => sum + (Number(c.budget_total) || 0), 0)
    const roiValues = allCampaigns
      .map((c) => Number(c.roi))
      .filter((value) => Number.isFinite(value) && value > 0)
    const avgRoi = roiValues.length > 0 ? roiValues.reduce((sum, value) => sum + value, 0) / roiValues.length : null

    const compactSpend =
      totalSpend > 0
        ? new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(totalSpend)
        : '0'

    return {
      totalCampaigns,
      avgRoiLabel: avgRoi ? `${avgRoi.toFixed(2)}x` : 'N/A',
      totalSpendLabel: `$${compactSpend}`,
    }
  }, [allCampaigns])

  useEffect(() => {
    const fetchCampaigns = async () => {
      try {
        // Fetch all campaigns (limit: 500 is backend maximum)
        const data = await getCampaigns(500, 0)
        
        const campaignsWithPending = data.campaigns.map((c) => ({
          campaign_id: c.campaign_id,
          name: c.name || 'Untitled Campaign',
          status: c.status,
          budget_total: c.budget_total,
          roi: c.roi,
          updated_at: formatUpdatedTime(c.updated_at),
          pending_approval: c.pending_approval !== null && c.pending_approval !== undefined,
        }))

        // Store all campaigns for overview count calculation
        setAllCampaigns(campaignsWithPending)

        // Show first 10 recent campaigns
        setCampaigns(campaignsWithPending.slice(0, 10))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load campaigns')
        setAllCampaigns([])
        setCampaigns([])
      } finally {
        setLoading(false)
      }
    }

    // Initial fetch
    fetchCampaigns()

    // Auto-refresh every 5 seconds to catch workflow status updates
    const interval = setInterval(fetchCampaigns, 5000)
    
    return () => clearInterval(interval)
  }, [])

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

  return (
    <div className="space-y-8">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Monday Brief</p>
          <h2 className="text-3xl font-bold tracking-tight">Campaign Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground">Monitor autonomous workflows and intervene only when needed.</p>
        </div>

        <Button asChild className="gap-2">
          <Link href="/campaigns/new">
            <Rocket className="h-4 w-4" />
            Create New Campaign
          </Link>
        </Button>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {overview.map((item, i) => (
          <motion.div key={item.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <Link href={`/campaigns?status=${item.filterValue}`}>
              <Card className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50">
                <CardHeader className="pb-2">
                  <CardDescription>{item.label}</CardDescription>
                  <CardTitle className="text-3xl">{item.value}</CardTitle>
                </CardHeader>
                <CardContent>
                  <StatusBadge status={item.status} />
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Recent Campaigns</CardTitle>
            <CardDescription>Latest orchestrator runs and approval checkpoints.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading campaigns...</p>
            ) : error ? (
              <p className="text-sm text-red-600">Error: {error}</p>
            ) : campaigns.length === 0 ? (
              <p className="text-sm text-muted-foreground">No campaigns yet. Create one to get started!</p>
            ) : (
              campaigns.map((item) => (
                <Link key={item.campaign_id} href={`/campaigns/${item.campaign_id}`} className="flex items-center justify-between rounded-lg border p-4 hover:bg-muted/50">
                  <div>
                    <p className="font-medium">{item.name}</p>
                    <p className="text-sm text-muted-foreground">{item.updated_at}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={item.status} />
                    <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Stats</CardTitle>
            <CardDescription>Portfolio performance snapshot</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total campaigns</span>
              <span className="font-semibold">{quickStats.totalCampaigns}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Avg ROI</span>
              <span className="font-semibold text-emerald-600">{quickStats.avgRoiLabel}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total spend</span>
              <span className="inline-flex items-center gap-1 font-semibold">
                <Wallet className="h-4 w-4" />{quickStats.totalSpendLabel}
              </span>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

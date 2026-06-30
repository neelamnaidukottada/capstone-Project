'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { Copy, Grid2X2, ListFilter } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/toaster'
import { useCampaign, useCampaignContent } from '@/hooks/use-campaign-queries'

type ContentAsset = {
  asset_id: string
  platform?: string
  title?: string
  body?: string
  variant?: string
}

export default function CampaignContentPage() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Array.isArray(id) ? id[0] : id
  const isDebugEnabled = process.env.NEXT_PUBLIC_ENABLE_DEBUG === 'true'
  const { data } = useCampaignContent(campaignId)
  const { data: campaign } = useCampaign(campaignId)
  const [channelFilter, setChannelFilter] = useState('')
  const { notify } = useToast()

  const assets = (data?.assets as ContentAsset[] | undefined) ?? []
  const assumptions = ((campaign?.content as { assumptions?: string[] } | null | undefined)?.assumptions ?? [])
  const filtered = useMemo(
    () => assets.filter((a) => !channelFilter || String(a.platform || '').includes(channelFilter.toLowerCase())),
    [assets, channelFilter]
  )
  const comparison = filtered.slice(0, 2)
  const calendarBuckets = useMemo(() => {
    const dayCount = 7
    return Array.from({ length: dayCount }, (_, idx) => {
      const posts = filtered.reduce((count, _asset, assetIndex) => count + (assetIndex % dayCount === idx ? 1 : 0), 0)
      return { day: idx + 1, posts }
    })
  }, [filtered])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-bold">Content Assets</h2>
        <div className="flex items-center gap-2">
          <ListFilter className="h-4 w-4 text-muted-foreground" />
          <Input placeholder="Filter by channel" value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)} className="w-52" />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Gallery</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.length ? filtered.map((asset) => (
            <div key={asset.asset_id} className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <p className="font-medium">{asset.title || asset.asset_id}</p>
                <span className="text-xs text-muted-foreground">{asset.platform}</span>
              </div>
              <p className="text-sm text-muted-foreground">{asset.body}</p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => {
                    navigator.clipboard.writeText(String(asset.body || ''))
                    notify('Copied to clipboard')
                  }}
                >
                  <Copy className="h-3 w-3" />Copy
                </Button>
                <Button variant="outline" size="sm" className="gap-2">
                  <Grid2X2 className="h-3 w-3" />Compare A/B
                </Button>
              </div>
            </div>
          )) : (
            <div className="space-y-3 rounded-lg border p-4 text-sm md:col-span-2 xl:col-span-3">
              <p className="text-muted-foreground">No generated content assets yet.</p>
              <p className="text-muted-foreground">
                Run the campaign workflow from Overview, then return here to review generated assets.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link href={`/campaigns/${campaignId}`}>Open Campaign Overview</Link>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/campaigns/${campaignId}/strategy`}>Open Strategy</Link>
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {isDebugEnabled
                  ? 'Tip: Use the Dev QA Panel on Overview to run content and media testing scenarios instantly.'
                  : 'Tip: Set NEXT_PUBLIC_ENABLE_DEBUG=true to enable the Dev QA Panel for one-click test scenarios.'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Content Assumptions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {assumptions.length ? assumptions.map((item) => (
            <p key={item} className="rounded-md border p-3">{item}</p>
          )) : <p className="text-muted-foreground">No assumptions were required for this content package.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Content Calendar</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-2 md:grid-cols-7">
          {calendarBuckets.map((item) => (
            <div key={item.day} className="rounded-md border p-3 text-sm">
              <p className="font-medium">Day {item.day}</p>
              <p className="text-muted-foreground">{item.posts} planned {item.posts === 1 ? 'post' : 'posts'}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Variant Comparison</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {comparison.length ? comparison.map((asset) => (
            <div key={asset.asset_id} className="rounded-md border p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Variant {asset.variant || 'A'}</p>
              <p className="mt-2 font-medium">{asset.title || asset.asset_id}</p>
              <p className="mt-2 text-sm text-muted-foreground">{asset.body}</p>
            </div>
          )) : <p className="text-sm text-muted-foreground">At least two assets are needed for A/B comparison.</p>}
        </CardContent>
      </Card>
    </div>
  )
}

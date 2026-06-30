'use client'

import { useParams } from 'next/navigation'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AlertTriangle, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useCampaign, useCampaignPerformance } from '@/hooks/use-campaign-queries'

type TimeSeriesPoint = {
  date: string
  impressions: number
  clicks: number
  conversions: number
}

type Anomaly = {
  metric?: string
  description?: string
}

type Recommendation = {
  action?: string
  rationale?: string
}

export default function CampaignPerformancePage() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Array.isArray(id) ? id[0] : id
  const { data } = useCampaignPerformance(campaignId)
  const { data: campaign } = useCampaign(campaignId)

  const metrics = data?.metrics ?? {}
  const timeSeries = (data?.time_series as TimeSeriesPoint[] | undefined) ?? []
  const anomalies = (data?.anomalies as Anomaly[] | undefined) ?? []
  const recommendations =
    ((campaign?.performance as { recommendations?: Recommendation[] } | undefined)?.recommendations ?? []).filter(
      (item) => Boolean(item.action)
    )

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Performance</h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Kpi title="CTR" value={`${((metrics.ctr ?? 0) * 100).toFixed(2)}%`} trend="up" />
        <Kpi title="CPC" value={`$${(metrics.cpc ?? 0).toFixed(2)}`} trend="down" />
        <Kpi title="CPA" value={`$${(metrics.cpa ?? 0).toFixed(2)}`} trend="down" />
        <Kpi title="ROAS" value={`${(metrics.roas ?? 0).toFixed(2)}x`} trend="up" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Real-time Trend</CardTitle>
          <CardDescription>Impressions, clicks, and conversions over time</CardDescription>
        </CardHeader>
        <CardContent className="h-[360px]">
          {timeSeries.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="impressions" stroke="#0ea5e9" strokeWidth={2} />
                <Line type="monotone" dataKey="clicks" stroke="#22c55e" strokeWidth={2} />
                <Line type="monotone" dataKey="conversions" stroke="#f59e0b" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Trend data will appear after performance snapshots are generated.</p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />Anomaly Alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {anomalies.length ? (
              anomalies.map((a, idx) => (
                <div key={idx} className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
                  <p className="font-medium">{a.metric}</p>
                  <p className="text-muted-foreground">{a.description ?? 'Unexpected shift detected'}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No critical anomalies detected.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><TrendingUp className="h-4 w-4" />Optimization Recommendations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {recommendations.length ? (
              recommendations.map((item, idx) => (
                <div key={`${String(item.action)}-${idx}`} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{item.action}</p>
                  {item.rationale ? <p className="text-muted-foreground">{item.rationale}</p> : null}
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No optimization recommendations yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Kpi({ title, value, trend }: { title: string; value: string; trend: 'up' | 'down' }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className={`text-xs ${trend === 'up' ? 'text-emerald-600' : 'text-amber-600'}`}>
          {trend === 'up' ? 'Trending up' : 'Monitoring decline'}
        </p>
      </CardContent>
    </Card>
  )
}

/**
 * Typed repository functions for each table.
 * Each function accepts a pre-built Supabase client so callers control
 * whether they use the admin or anon client.
 */
import type { SupabaseClient, SupabaseAnonClient } from './client'
import { findMany, findOne, insertOne } from './client'
import type {
  Campaign,
  CampaignInsert,
  CampaignUpdate,
  CampaignSummary,
  ContentAsset,
  ContentAssetInsert,
  ContentAssetUpdate,
  PerformanceMetric,
  PerformanceMetricInsert,
  AgentLog,
  AgentLogInsert,
  UserProfile,
  UserProfileUpdate,
  Organization,
  OrganizationUpdate,
  ContentChannel,
  AssetStatus,
  AgentAction,
} from './database.types'

type AnyClient = SupabaseClient | SupabaseAnonClient

// ---------------------------------------------------------------------------
// Organizations
// ---------------------------------------------------------------------------

export const organizations = {
  getById: (db: AnyClient, id: string) =>
    findOne<Organization>(db.from('organizations').select('*').eq('id', id).single()),

  update: (db: AnyClient, id: string, data: OrganizationUpdate) =>
    findOne<Organization>(
      db.from('organizations').update(data).eq('id', id).select().single()
    ),
}

// ---------------------------------------------------------------------------
// User profiles
// ---------------------------------------------------------------------------

export const userProfiles = {
  getById: (db: AnyClient, id: string) =>
    findOne<UserProfile>(db.from('user_profiles').select('*').eq('id', id).single()),

  getByEmail: (db: AnyClient, email: string) =>
    findOne<UserProfile>(db.from('user_profiles').select('*').eq('email', email).single()),

  listByOrg: (db: AnyClient, organizationId: string) =>
    findMany<UserProfile>(
      db.from('user_profiles').select('*').eq('organization_id', organizationId)
    ),

  update: (db: AnyClient, id: string, data: UserProfileUpdate) =>
    findOne<UserProfile>(
      db.from('user_profiles').update(data).eq('id', id).select().single()
    ),
}

// ---------------------------------------------------------------------------
// Campaigns
// ---------------------------------------------------------------------------

export const campaigns = {
  listByOrg: (
    db: AnyClient,
    organizationId: string,
    opts: { page?: number; pageSize?: number } = {}
  ) => {
    const { page = 1, pageSize = 20 } = opts
    const from = (page - 1) * pageSize
    return findMany<Campaign>(
      db
        .from('campaigns')
        .select('*')
        .eq('organization_id', organizationId)
        .order('created_at', { ascending: false })
        .range(from, from + pageSize - 1)
    )
  },

  summaries: (db: AnyClient, organizationId: string) =>
    findMany<CampaignSummary>(
      db
        .from('campaign_summary')
        .select('*')
        .eq('organization_id', organizationId)
        .order('updated_at', { ascending: false })
    ),

  getById: (db: AnyClient, id: string) =>
    findOne<Campaign>(db.from('campaigns').select('*').eq('id', id).single()),

  create: (db: AnyClient, data: CampaignInsert) =>
    insertOne<Campaign>(db.from('campaigns').insert(data).select().single()),

  update: (db: AnyClient, id: string, data: CampaignUpdate) =>
    findOne<Campaign>(db.from('campaigns').update(data).eq('id', id).select().single()),

  delete: async (db: AnyClient, id: string): Promise<void> => {
    const { error } = await db.from('campaigns').delete().eq('id', id)
    if (error) throw new Error(`[acm/database] Delete campaign error: ${error.message}`)
  },
}

// ---------------------------------------------------------------------------
// Content assets
// ---------------------------------------------------------------------------

export const contentAssets = {
  listByCampaign: (
    db: AnyClient,
    campaignId: string,
    opts: { channel?: ContentChannel; status?: AssetStatus } = {}
  ) => {
    let query = db
      .from('content_assets')
      .select('*')
      .eq('campaign_id', campaignId)
      .order('created_at', { ascending: false })

    if (opts.channel) query = query.eq('channel', opts.channel)
    if (opts.status) query = query.eq('status', opts.status)

    return findMany<ContentAsset>(query)
  },

  getById: (db: AnyClient, id: string) =>
    findOne<ContentAsset>(db.from('content_assets').select('*').eq('id', id).single()),

  create: (db: AnyClient, data: ContentAssetInsert) =>
    insertOne<ContentAsset>(db.from('content_assets').insert(data).select().single()),

  update: (db: AnyClient, id: string, data: ContentAssetUpdate) =>
    findOne<ContentAsset>(db.from('content_assets').update(data).eq('id', id).select().single()),

  updateStatus: (db: AnyClient, id: string, status: AssetStatus) =>
    findOne<ContentAsset>(
      db.from('content_assets').update({ status }).eq('id', id).select().single()
    ),
}

// ---------------------------------------------------------------------------
// Performance metrics
// ---------------------------------------------------------------------------

export const performanceMetrics = {
  listByCampaign: (
    db: AnyClient,
    campaignId: string,
    opts: { channel?: ContentChannel; metricName?: string; limit?: number } = {}
  ) => {
    let query = db
      .from('performance_metrics')
      .select('*')
      .eq('campaign_id', campaignId)
      .order('recorded_at', { ascending: false })

    if (opts.channel) query = query.eq('channel', opts.channel)
    if (opts.metricName) query = query.eq('metric_name', opts.metricName)
    if (opts.limit) query = query.limit(opts.limit)

    return findMany<PerformanceMetric>(query)
  },

  insert: (db: AnyClient, data: PerformanceMetricInsert) =>
    insertOne<PerformanceMetric>(db.from('performance_metrics').insert(data).select().single()),

  bulkInsert: async (db: AnyClient, rows: PerformanceMetricInsert[]): Promise<void> => {
    const { error } = await db.from('performance_metrics').insert(rows)
    if (error) throw new Error(`[acm/database] Bulk insert metrics error: ${error.message}`)
  },
}

// ---------------------------------------------------------------------------
// Agent logs
// ---------------------------------------------------------------------------

export const agentLogs = {
  listByCampaign: (
    db: AnyClient,
    campaignId: string,
    opts: { agentName?: string; action?: AgentAction; limit?: number } = {}
  ) => {
    let query = db
      .from('agent_logs')
      .select('*')
      .eq('campaign_id', campaignId)
      .order('timestamp', { ascending: false })

    if (opts.agentName) query = query.eq('agent_name', opts.agentName)
    if (opts.action) query = query.eq('action', opts.action)
    if (opts.limit) query = query.limit(opts.limit)

    return findMany<AgentLog>(query)
  },

  insert: (db: AnyClient, data: AgentLogInsert) =>
    insertOne<AgentLog>(db.from('agent_logs').insert(data).select().single()),
}

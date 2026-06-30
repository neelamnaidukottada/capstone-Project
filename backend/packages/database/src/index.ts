// Client factories & helpers
export {
  createClient,
  createAnonClient,
  createAdminClient,
  findOne,
  findMany,
  insertOne,
} from './client'
export type { SupabaseClient, SupabaseAnonClient } from './client'

// Database types & enums
export type {
  Database,
  Json,
  // Enums
  UserRole,
  CampaignStatus,
  CampaignGoal,
  ContentChannel,
  ContentType,
  AssetStatus,
  AgentAction,
  // JSON shape helpers
  OrganizationSettings,
  CampaignTimeline,
  CampaignPhase,
  CampaignStrategy,
  CampaignTargeting,
  CampaignMessaging,
  ContentAssetMetadata,
  TokenUsage,
  // Table row types
  Organization,
  OrganizationInsert,
  OrganizationUpdate,
  UserProfile,
  UserProfileInsert,
  UserProfileUpdate,
  Campaign,
  CampaignInsert,
  CampaignUpdate,
  ContentAsset,
  ContentAssetInsert,
  ContentAssetUpdate,
  PerformanceMetric,
  PerformanceMetricInsert,
  AgentLog,
  AgentLogInsert,
  AgentRun,
  AgentRunInsert,
  AgentRunUpdate,
  AgentEvent,
  AgentEventInsert,
  CampaignSummary,
} from './database.types'

// Typed repository helpers
export { campaigns, contentAssets, performanceMetrics, agentLogs, userProfiles, organizations } from './repositories'

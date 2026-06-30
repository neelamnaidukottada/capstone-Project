/**
 * Supabase database types for Autonomous Campaign Manager.
 *
 * To regenerate from a live project:
 *   npx supabase gen types typescript --project-id <ref> --schema public \
 *     > packages/database/src/database.types.ts
 */

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

// ---------------------------------------------------------------------------
// Enums  (mirror the PostgreSQL enum types in migrations/002_full_schema.sql)
// ---------------------------------------------------------------------------

export type UserRole = 'owner' | 'admin' | 'editor' | 'viewer'

export type CampaignStatus = 'draft' | 'active' | 'paused' | 'completed' | 'failed'

export type CampaignGoal =
  | 'brand_awareness'
  | 'lead_generation'
  | 'conversion'
  | 'retention'
  | 'upsell'
  | 'engagement'
  | 'traffic'

export type ContentChannel =
  | 'email'
  | 'social_instagram'
  | 'social_linkedin'
  | 'social_twitter'
  | 'paid_search'
  | 'paid_social'
  | 'seo'
  | 'blog'
  | 'push_notification'
  | 'sms'

export type ContentType =
  | 'headline'
  | 'body_copy'
  | 'subject_line'
  | 'cta'
  | 'image_brief'
  | 'video_script'
  | 'landing_page'
  | 'ad_creative'
  | 'blog_post'
  | 'push_message'

export type AssetStatus = 'draft' | 'review' | 'approved' | 'rejected' | 'published'

export type AgentAction =
  | 'research'
  | 'generate_content'
  | 'review_content'
  | 'schedule'
  | 'analyse_performance'
  | 'optimise'
  | 'report'
  | 'plan'

// ---------------------------------------------------------------------------
// JSON shape helpers  (strongly-typed jsonb columns)
// ---------------------------------------------------------------------------

export interface OrganizationSettings {
  defaultModel: string
  maxBudgetPerCampaign: number
  allowedChannels: ContentChannel[]
  brandVoice: string
  timezone: string
  [key: string]: Json | undefined
}

export interface CampaignTimeline {
  startDate: string | null
  endDate: string | null
  phases: CampaignPhase[]
}

export interface CampaignPhase {
  name: string
  startDate: string
  endDate: string
  budgetPct: number
}

export interface CampaignStrategy {
  summary: string
  targeting: CampaignTargeting
  messaging: CampaignMessaging
  budget_allocation: Record<string, number>
  [key: string]: Json | undefined
}

export interface CampaignTargeting {
  industries?: string[]
  jobTitles?: string[]
  companySizes?: string[]
  geographies?: string[]
  segments?: string[]
  excludes?: string[]
  ageRange?: { min: number; max: number }
  interests?: string[]
  [key: string]: Json | undefined
}

export interface CampaignMessaging {
  primaryPain?: string
  primaryValue?: string
  differentiator?: string
  [key: string]: Json | undefined
}

export interface ContentAssetMetadata {
  wordCount: number
  tone: string | null
  keywords: string[]
  reviewNotes: string | null
  generatedBy: string | null
  promptVersion: string | null
  [key: string]: Json | undefined
}

export interface TokenUsage {
  prompt: number
  completion: number
  total: number
}

// ---------------------------------------------------------------------------
// Database interface
// ---------------------------------------------------------------------------

export interface Database {
  public: {
    Tables: {
      // ── organizations ──────────────────────────────────────────────────────
      organizations: {
        Row: {
          id: string
          name: string
          slug: string          // generated column — always present on Row
          settings: OrganizationSettings
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          name: string
          // slug is a GENERATED ALWAYS column — do NOT insert/update it
          settings?: OrganizationSettings
          created_at?: string
          updated_at?: string
        }
        Update: {
          name?: string
          settings?: Partial<OrganizationSettings>
          updated_at?: string
        }
        Relationships: []
      }

      // ── user_profiles ──────────────────────────────────────────────────────
      user_profiles: {
        Row: {
          id: string
          email: string
          full_name: string
          avatar_url: string | null
          role: UserRole
          organization_id: string | null
          preferences: Json
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string          // must match auth.users.id
          email: string
          full_name?: string
          avatar_url?: string | null
          role?: UserRole
          organization_id?: string | null
          preferences?: Json
          created_at?: string
          updated_at?: string
        }
        Update: {
          email?: string
          full_name?: string
          avatar_url?: string | null
          role?: UserRole
          organization_id?: string | null
          preferences?: Json
          updated_at?: string
        }
        Relationships: []
      }

      // ── campaigns ──────────────────────────────────────────────────────────
      campaigns: {
        Row: {
          id: string
          organization_id: string | null
          user_id: string
          name: string
          description: string
          goal: CampaignGoal
          status: CampaignStatus
          channels: ContentChannel[]
          budget: number
          timeline: CampaignTimeline
          strategy_json: CampaignStrategy
          target_audience: CampaignTargeting
          goals: string[]
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id?: string | null
          user_id: string
          name: string
          description?: string
          goal?: CampaignGoal
          status?: CampaignStatus
          channels?: ContentChannel[]
          budget?: number
          timeline?: CampaignTimeline
          strategy_json?: CampaignStrategy
          target_audience?: CampaignTargeting
          goals?: string[]
          created_at?: string
          updated_at?: string
        }
        Update: {
          organization_id?: string | null
          name?: string
          description?: string
          goal?: CampaignGoal
          status?: CampaignStatus
          channels?: ContentChannel[]
          budget?: number
          timeline?: Partial<CampaignTimeline>
          strategy_json?: Partial<CampaignStrategy>
          target_audience?: Partial<CampaignTargeting>
          goals?: string[]
          updated_at?: string
        }
        Relationships: []
      }

      // ── content_assets ─────────────────────────────────────────────────────
      content_assets: {
        Row: {
          id: string
          campaign_id: string
          channel: ContentChannel
          content_type: ContentType
          content: string
          variant: string
          status: AssetStatus
          metadata: ContentAssetMetadata
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          campaign_id: string
          channel: ContentChannel
          content_type: ContentType
          content?: string
          variant?: string
          status?: AssetStatus
          metadata?: Partial<ContentAssetMetadata>
          created_at?: string
          updated_at?: string
        }
        Update: {
          channel?: ContentChannel
          content_type?: ContentType
          content?: string
          variant?: string
          status?: AssetStatus
          metadata?: Partial<ContentAssetMetadata>
          updated_at?: string
        }
        Relationships: []
      }

      // ── performance_metrics ────────────────────────────────────────────────
      performance_metrics: {
        Row: {
          id: string
          campaign_id: string
          channel: ContentChannel
          metric_name: string
          metric_value: number
          dimension: string | null
          recorded_at: string
        }
        Insert: {
          id?: string
          campaign_id: string
          channel: ContentChannel
          metric_name: string
          metric_value: number
          dimension?: string | null
          recorded_at?: string
        }
        // Append-only table — updates are not permitted
        Update: Record<string, never>
        Relationships: []
      }

      // ── agent_logs ─────────────────────────────────────────────────────────
      agent_logs: {
        Row: {
          id: string
          campaign_id: string
          agent_name: string
          action: AgentAction
          input_payload: Json
          output_payload: Json
          latency_ms: number | null
          model: string | null
          token_usage: TokenUsage | null
          error: string | null
          timestamp: string
        }
        Insert: {
          id?: string
          campaign_id: string
          agent_name: string
          action: AgentAction
          input_payload?: Json
          output_payload?: Json
          latency_ms?: number | null
          model?: string | null
          token_usage?: TokenUsage | null
          error?: string | null
          timestamp?: string
        }
        // Append-only table — updates are not permitted
        Update: Record<string, never>
        Relationships: []
      }

      // ── agent_runs  (from migration 001, kept for LangGraph checkpointing) ─
      agent_runs: {
        Row: {
          id: string
          campaign_id: string
          status: 'idle' | 'running' | 'waiting' | 'completed' | 'failed'
          thread_id: string
          model: string
          created_at: string
          completed_at: string | null
          error: string | null
        }
        Insert: {
          id?: string
          campaign_id: string
          status?: 'idle' | 'running' | 'waiting' | 'completed' | 'failed'
          thread_id: string
          model?: string
          created_at?: string
          completed_at?: string | null
          error?: string | null
        }
        Update: {
          status?: 'idle' | 'running' | 'waiting' | 'completed' | 'failed'
          completed_at?: string | null
          error?: string | null
        }
        Relationships: []
      }

      // ── agent_events  (from migration 001) ────────────────────────────────
      agent_events: {
        Row: {
          id: string
          run_id: string
          event_type: string
          payload: Json
          created_at: string
        }
        Insert: {
          id?: string
          run_id: string
          event_type: string
          payload?: Json
          created_at?: string
        }
        Update: Record<string, never>
        Relationships: []
      }
    }

    Views: {
      campaign_summary: {
        Row: {
          id: string
          organization_id: string | null
          name: string
          goal: CampaignGoal
          status: CampaignStatus
          budget: number
          timeline: CampaignTimeline
          channels: ContentChannel[]
          created_at: string
          updated_at: string
          published_assets: number
          draft_assets: number
          total_agent_actions: number
          last_agent_activity: string | null
        }
        Relationships: []
      }
    }

    Functions: {
      auth_org_id: {
        Args: Record<string, never>
        Returns: string
      }
      auth_has_role: {
        Args: { minimum_role: UserRole }
        Returns: boolean
      }
    }

    Enums: {
      user_role: UserRole
      campaign_status: CampaignStatus
      campaign_goal: CampaignGoal
      content_channel: ContentChannel
      content_type: ContentType
      asset_status: AssetStatus
      agent_action: AgentAction
    }

    CompositeTypes: {
      [_ in never]: never
    }
  }
}

// ---------------------------------------------------------------------------
// Table row convenience types  (use instead of Database['public']['Tables'][T]['Row'])
// ---------------------------------------------------------------------------

export type Organization = Database['public']['Tables']['organizations']['Row']
export type OrganizationInsert = Database['public']['Tables']['organizations']['Insert']
export type OrganizationUpdate = Database['public']['Tables']['organizations']['Update']

export type UserProfile = Database['public']['Tables']['user_profiles']['Row']
export type UserProfileInsert = Database['public']['Tables']['user_profiles']['Insert']
export type UserProfileUpdate = Database['public']['Tables']['user_profiles']['Update']

export type Campaign = Database['public']['Tables']['campaigns']['Row']
export type CampaignInsert = Database['public']['Tables']['campaigns']['Insert']
export type CampaignUpdate = Database['public']['Tables']['campaigns']['Update']

export type ContentAsset = Database['public']['Tables']['content_assets']['Row']
export type ContentAssetInsert = Database['public']['Tables']['content_assets']['Insert']
export type ContentAssetUpdate = Database['public']['Tables']['content_assets']['Update']

export type PerformanceMetric = Database['public']['Tables']['performance_metrics']['Row']
export type PerformanceMetricInsert = Database['public']['Tables']['performance_metrics']['Insert']

export type AgentLog = Database['public']['Tables']['agent_logs']['Row']
export type AgentLogInsert = Database['public']['Tables']['agent_logs']['Insert']

export type AgentRun = Database['public']['Tables']['agent_runs']['Row']
export type AgentRunInsert = Database['public']['Tables']['agent_runs']['Insert']
export type AgentRunUpdate = Database['public']['Tables']['agent_runs']['Update']

export type AgentEvent = Database['public']['Tables']['agent_events']['Row']
export type AgentEventInsert = Database['public']['Tables']['agent_events']['Insert']

export type CampaignSummary = Database['public']['Views']['campaign_summary']['Row']

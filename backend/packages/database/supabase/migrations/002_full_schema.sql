-- =============================================================================
-- 002_full_schema.sql
-- Autonomous Campaign Manager — complete schema v2
--
-- Adds:  organizations, user_profiles, content_assets,
--        performance_metrics, agent_logs
-- Alters: campaigns (adds goal, timeline, strategy_json, organization_id)
-- Updates: RLS policies for multi-tenancy via organization_id
--
-- Apply:
--   supabase db push
--   OR  psql $DATABASE_URL -f 002_full_schema.sql
-- =============================================================================

-- ── Extra extensions ──────────────────────────────────────────────────────────
create extension if not exists "pg_trgm";          -- fast ILIKE / text search
create extension if not exists "btree_gist";       -- range index support

-- ─────────────────────────────────────────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────────────────────────────────────────

create type user_role           as enum ('owner', 'admin', 'editor', 'viewer');
create type content_channel     as enum ('email', 'social_instagram', 'social_linkedin',
                                          'social_twitter', 'paid_search', 'paid_social',
                                          'seo', 'blog', 'push_notification', 'sms');
create type content_type        as enum ('headline', 'body_copy', 'subject_line', 'cta',
                                          'image_brief', 'video_script', 'landing_page',
                                          'ad_creative', 'blog_post', 'push_message');
create type asset_status        as enum ('draft', 'review', 'approved', 'rejected', 'published');
create type campaign_goal       as enum ('brand_awareness', 'lead_generation', 'conversion',
                                          'retention', 'upsell', 'engagement', 'traffic');
create type agent_action        as enum ('research', 'generate_content', 'review_content',
                                          'schedule', 'analyse_performance', 'optimise',
                                          'report', 'plan');

-- ─────────────────────────────────────────────────────────────────────────────
-- HELPER: generic updated_at trigger function (idempotent)
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. ORGANIZATIONS
-- ─────────────────────────────────────────────────────────────────────────────
create table organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (char_length(name) between 1 and 255),
  slug        text not null unique
                   generated always as (lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))) stored,
  settings    jsonb not null default '{
    "defaultModel": "gpt-4o",
    "maxBudgetPerCampaign": 100000,
    "allowedChannels": [],
    "brandVoice": "professional",
    "timezone": "UTC"
  }'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index organizations_slug_idx on organizations(slug);

create trigger organizations_updated_at
  before update on organizations
  for each row execute procedure set_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. USER PROFILES  (mirrors auth.users, extends with role + org)
-- ─────────────────────────────────────────────────────────────────────────────
create table user_profiles (
  id               uuid primary key references auth.users(id) on delete cascade,
  email            text not null unique,
  full_name        text not null default '',
  avatar_url       text,
  role             user_role not null default 'viewer',
  organization_id  uuid references organizations(id) on delete set null,
  preferences      jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index user_profiles_org_idx     on user_profiles(organization_id);
create index user_profiles_email_idx   on user_profiles(email);
create index user_profiles_role_idx    on user_profiles(role);

create trigger user_profiles_updated_at
  before update on user_profiles
  for each row execute procedure set_updated_at();

-- Auto-create profile row when a new auth user signs up
create or replace function handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.user_profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_auth_user();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. CAMPAIGNS  (alter existing + add new columns)
-- ─────────────────────────────────────────────────────────────────────────────
alter table campaigns
  add column if not exists organization_id  uuid references organizations(id) on delete cascade,
  add column if not exists goal             campaign_goal not null default 'brand_awareness',
  add column if not exists timeline         jsonb not null default '{
    "startDate": null,
    "endDate": null,
    "phases": []
  }'::jsonb,
  add column if not exists strategy_json   jsonb not null default '{
    "summary": "",
    "targeting": {},
    "messaging": {},
    "budget_allocation": {}
  }'::jsonb;

-- Back-fill org from user_profiles for existing rows (best-effort)
update campaigns c
set organization_id = up.organization_id
from user_profiles up
where up.id = c.user_id
  and c.organization_id is null;

create index if not exists campaigns_org_idx      on campaigns(organization_id);
create index if not exists campaigns_goal_idx     on campaigns(goal);
-- Composite for dashboard queries: org + status
create index if not exists campaigns_org_status_idx on campaigns(organization_id, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. CONTENT ASSETS
-- ─────────────────────────────────────────────────────────────────────────────
create table content_assets (
  id           uuid primary key default gen_random_uuid(),
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  channel      content_channel not null,
  content_type content_type not null,
  -- The actual content string (copy, script, brief, etc.)
  content      text not null default '',
  -- A/B variant label: 'control', 'variant_a', 'variant_b', etc.
  variant      text not null default 'control'
                    check (char_length(variant) between 1 and 64),
  status       asset_status not null default 'draft',
  metadata     jsonb not null default '{
    "wordCount": 0,
    "tone": null,
    "keywords": [],
    "reviewNotes": null,
    "generatedBy": null,
    "promptVersion": null
  }'::jsonb,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index content_assets_campaign_idx     on content_assets(campaign_id);
create index content_assets_channel_idx      on content_assets(channel);
create index content_assets_status_idx       on content_assets(status);
-- Composite for per-campaign channel queries
create index content_assets_campaign_channel_idx on content_assets(campaign_id, channel);
-- Full-text search on content
create index content_assets_content_fts_idx  on content_assets using gin(to_tsvector('english', content));

create trigger content_assets_updated_at
  before update on content_assets
  for each row execute procedure set_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. PERFORMANCE METRICS
-- ─────────────────────────────────────────────────────────────────────────────
create table performance_metrics (
  id            uuid primary key default gen_random_uuid(),
  campaign_id   uuid not null references campaigns(id) on delete cascade,
  channel       content_channel not null,
  metric_name   text not null check (char_length(metric_name) between 1 and 128),
  metric_value  numeric(18, 6) not null,
  -- Optional dimension for grouping (ad_group, audience_segment, etc.)
  dimension     text,
  recorded_at   timestamptz not null default now()
);

-- Time-series queries: campaign + time range
create index performance_metrics_campaign_time_idx
  on performance_metrics(campaign_id, recorded_at desc);
-- Per-channel rollup
create index performance_metrics_channel_idx
  on performance_metrics(channel, recorded_at desc);
-- Specific metric lookup
create index performance_metrics_name_idx
  on performance_metrics(campaign_id, metric_name, recorded_at desc);
-- Partial index: only last 90 days (hot path)
create index performance_metrics_recent_idx
  on performance_metrics(campaign_id, recorded_at desc)
  where recorded_at >= now() - interval '90 days';

-- NOTE: performance_metrics is append-only; no updated_at needed.

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. AGENT LOGS
-- ─────────────────────────────────────────────────────────────────────────────
create table agent_logs (
  id              uuid primary key default gen_random_uuid(),
  campaign_id     uuid not null references campaigns(id) on delete cascade,
  agent_name      text not null check (char_length(agent_name) between 1 and 128),
  action          agent_action not null,
  input_payload   jsonb not null default '{}',
  output_payload  jsonb not null default '{}',
  latency_ms      integer check (latency_ms >= 0),
  model           text,
  token_usage     jsonb default null,   -- {"prompt":0,"completion":0,"total":0}
  error           text,
  -- timestamp instead of created_at — matches the requirement
  "timestamp"     timestamptz not null default now()
);

create index agent_logs_campaign_idx      on agent_logs(campaign_id);
create index agent_logs_agent_name_idx    on agent_logs(agent_name);
create index agent_logs_action_idx        on agent_logs(action);
create index agent_logs_timestamp_idx     on agent_logs("timestamp" desc);
-- Composite for per-agent timeline
create index agent_logs_campaign_agent_time_idx
  on agent_logs(campaign_id, agent_name, "timestamp" desc);

-- NOTE: agent_logs is append-only.

-- ─────────────────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- Strategy: users access data that belongs to their organization.
--           Org membership is determined via user_profiles.organization_id.
-- ─────────────────────────────────────────────────────────────────────────────

-- Helper: get the calling user's organization_id
create or replace function auth_org_id()
returns uuid language sql stable security definer set search_path = public as $$
  select organization_id from user_profiles where id = auth.uid()
$$;

-- Helper: check if calling user has at least a given role within their org
create or replace function auth_has_role(minimum_role user_role)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from user_profiles
    where id = auth.uid()
      and organization_id is not null
      and case role
            when 'owner'  then true
            when 'admin'  then minimum_role in ('admin','editor','viewer')
            when 'editor' then minimum_role in ('editor','viewer')
            when 'viewer' then minimum_role = 'viewer'
            else false
          end
  )
$$;

-- ── organizations ─────────────────────────────────────────────────────────────
alter table organizations enable row level security;

create policy "organizations: members can read"
  on organizations for select
  using (id = auth_org_id());

create policy "organizations: owners can update"
  on organizations for update
  using (id = auth_org_id() and auth_has_role('owner'))
  with check (id = auth_org_id() and auth_has_role('owner'));

-- ── user_profiles ─────────────────────────────────────────────────────────────
alter table user_profiles enable row level security;

-- Users can read all profiles in their org
create policy "user_profiles: org members can read"
  on user_profiles for select
  using (organization_id = auth_org_id() or id = auth.uid());

-- Users can only update their own profile
create policy "user_profiles: own record update"
  on user_profiles for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- ── campaigns ────────────────────────────────────────────────────────────────
-- (existing policy "campaigns: owner access" is user-scoped; replace with org-scoped)
drop policy if exists "campaigns: owner access" on campaigns;

create policy "campaigns: org members can read"
  on campaigns for select
  using (organization_id = auth_org_id());

create policy "campaigns: editors+ can insert"
  on campaigns for insert
  with check (organization_id = auth_org_id() and auth_has_role('editor'));

create policy "campaigns: editors+ can update"
  on campaigns for update
  using (organization_id = auth_org_id() and auth_has_role('editor'))
  with check (organization_id = auth_org_id());

create policy "campaigns: admins+ can delete"
  on campaigns for delete
  using (organization_id = auth_org_id() and auth_has_role('admin'));

-- ── content_assets ────────────────────────────────────────────────────────────
alter table content_assets enable row level security;

create policy "content_assets: org members can read"
  on content_assets for select
  using (
    exists (
      select 1 from campaigns c
      where c.id = content_assets.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

create policy "content_assets: editors+ can write"
  on content_assets for insert
  with check (
    auth_has_role('editor') and
    exists (
      select 1 from campaigns c
      where c.id = content_assets.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

create policy "content_assets: editors+ can update"
  on content_assets for update
  using (
    auth_has_role('editor') and
    exists (
      select 1 from campaigns c
      where c.id = content_assets.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

create policy "content_assets: admins+ can delete"
  on content_assets for delete
  using (
    auth_has_role('admin') and
    exists (
      select 1 from campaigns c
      where c.id = content_assets.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

-- ── performance_metrics ───────────────────────────────────────────────────────
alter table performance_metrics enable row level security;

create policy "performance_metrics: org members can read"
  on performance_metrics for select
  using (
    exists (
      select 1 from campaigns c
      where c.id = performance_metrics.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

create policy "performance_metrics: editors+ can insert"
  on performance_metrics for insert
  with check (
    auth_has_role('editor') and
    exists (
      select 1 from campaigns c
      where c.id = performance_metrics.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

-- ── agent_logs ────────────────────────────────────────────────────────────────
alter table agent_logs enable row level security;

create policy "agent_logs: org members can read"
  on agent_logs for select
  using (
    exists (
      select 1 from campaigns c
      where c.id = agent_logs.campaign_id
        and c.organization_id = auth_org_id()
    )
  );

-- Service role writes logs; no end-user insert policy needed.
-- If writing from edge functions, use service role key.

-- ─────────────────────────────────────────────────────────────────────────────
-- VIEWS  (convenience — not security boundaries)
-- ─────────────────────────────────────────────────────────────────────────────

-- Campaign summary with latest metrics
create or replace view campaign_summary as
select
  c.id,
  c.organization_id,
  c.name,
  c.goal,
  c.status,
  c.budget,
  c.timeline,
  c.channels,
  c.created_at,
  c.updated_at,
  count(distinct ca.id)  filter (where ca.status = 'published') as published_assets,
  count(distinct ca.id)  filter (where ca.status = 'draft')     as draft_assets,
  count(distinct al.id)                                          as total_agent_actions,
  max(al."timestamp")                                            as last_agent_activity
from campaigns c
left join content_assets ca on ca.campaign_id = c.id
left join agent_logs     al on al.campaign_id = c.id
group by c.id;

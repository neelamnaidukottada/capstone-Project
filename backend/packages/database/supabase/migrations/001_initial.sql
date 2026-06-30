-- =============================================================================
-- 001_initial.sql — Autonomous Campaign Manager baseline schema
-- Apply via: supabase db push  OR  psql $DATABASE_URL -f this_file.sql
-- =============================================================================

-- Enable required extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- ── Enums ─────────────────────────────────────────────────────────────────────

create type campaign_status as enum ('draft', 'active', 'paused', 'completed', 'failed');
create type campaign_channel as enum ('email', 'social', 'paid_ads', 'seo', 'content');
create type agent_status as enum ('idle', 'running', 'waiting', 'completed', 'failed');

-- ── Campaigns ─────────────────────────────────────────────────────────────────

create table campaigns (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  name             text not null check (char_length(name) between 1 and 255),
  description      text not null default '',
  status           campaign_status not null default 'draft',
  channels         campaign_channel[] not null default '{}',
  budget           numeric(14, 2) not null default 0 check (budget >= 0),
  target_audience  jsonb not null default '{}',
  goals            text[] not null default '{}',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index campaigns_user_id_idx on campaigns(user_id);
create index campaigns_status_idx on campaigns(status);

-- Auto-update updated_at
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger campaigns_updated_at
  before update on campaigns
  for each row execute procedure set_updated_at();

-- ── Agent runs ────────────────────────────────────────────────────────────────

create table agent_runs (
  id            uuid primary key default gen_random_uuid(),
  campaign_id   uuid not null references campaigns(id) on delete cascade,
  status        agent_status not null default 'idle',
  thread_id     text not null,
  model         text not null default 'gpt-4o',
  created_at    timestamptz not null default now(),
  completed_at  timestamptz,
  error         text
);

create index agent_runs_campaign_id_idx on agent_runs(campaign_id);
create index agent_runs_thread_id_idx on agent_runs(thread_id);

-- ── Agent events ──────────────────────────────────────────────────────────────

create table agent_events (
  id          uuid primary key default gen_random_uuid(),
  run_id      uuid not null references agent_runs(id) on delete cascade,
  event_type  text not null,
  payload     jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index agent_events_run_id_idx on agent_events(run_id);

-- ── Row Level Security ────────────────────────────────────────────────────────

alter table campaigns enable row level security;
alter table agent_runs enable row level security;
alter table agent_events enable row level security;

-- Users can only see their own campaigns
create policy "campaigns: owner access"
  on campaigns for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Users can see agent_runs belonging to their campaigns
create policy "agent_runs: owner access"
  on agent_runs for all
  using (
    exists (
      select 1 from campaigns c
      where c.id = agent_runs.campaign_id
        and c.user_id = auth.uid()
    )
  );

-- Users can see agent_events belonging to their runs
create policy "agent_events: owner access"
  on agent_events for all
  using (
    exists (
      select 1
      from agent_runs ar
      join campaigns c on c.id = ar.campaign_id
      where ar.id = agent_events.run_id
        and c.user_id = auth.uid()
    )
  );

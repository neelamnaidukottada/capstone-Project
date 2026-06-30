-- =============================================================================
-- 004_campaigns_schema_reconcile.sql
-- Reconciles legacy campaigns schema with current API expectations.
-- Safe to run multiple times.
-- =============================================================================

-- 1) Ensure required columns exist.
alter table if exists campaigns
  add column if not exists organization_id uuid,
  add column if not exists name text,
  add column if not exists description text not null default '',
  add column if not exists target_audience jsonb not null default '{}'::jsonb,
  add column if not exists goals text[] not null default '{}'::text[],
  add column if not exists timeline jsonb not null default '{
    "startDate": null,
    "endDate": null,
    "phases": []
  }'::jsonb,
  add column if not exists strategy_json jsonb not null default '{
    "summary": "",
    "targeting": {},
    "messaging": {},
    "budget_allocation": {},
    "runtime": {}
  }'::jsonb;

-- 2) Backfill organization_id from app_users where possible.
update campaigns c
set organization_id = u.organization_id
from app_users u
where c.user_id = u.id
  and c.organization_id is null;

-- 3) Backfill campaign name for legacy rows.
update campaigns
set name = left(coalesce(nullif(goal, ''), 'Untitled Campaign'), 120)
where name is null or btrim(name) = '';

-- 4) Re-point legacy FK from users -> app_users.
do $$
begin
  if exists (
    select 1
    from information_schema.table_constraints
    where table_schema = 'public'
      and table_name = 'campaigns'
      and constraint_name = 'campaigns_user_id_fkey'
  ) then
    alter table campaigns drop constraint campaigns_user_id_fkey;
  end if;
end $$;

-- New writes are validated against app_users; legacy bad rows are tolerated until cleaned.
alter table campaigns
  add constraint campaigns_user_id_fkey
  foreign key (user_id)
  references app_users(id)
  on delete cascade
  not valid;

-- 5) Add organization FK (optional on legacy rows).
do $$
begin
  if not exists (
    select 1
    from information_schema.table_constraints
    where table_schema = 'public'
      and table_name = 'campaigns'
      and constraint_name = 'campaigns_organization_id_fkey'
  ) then
    alter table campaigns
      add constraint campaigns_organization_id_fkey
      foreign key (organization_id)
      references app_organizations(id)
      on delete cascade
      not valid;
  end if;
end $$;

-- 6) Helpful indexes for list endpoints.
create index if not exists campaigns_org_idx on campaigns(organization_id);
create index if not exists campaigns_org_status_idx on campaigns(organization_id, status);
create index if not exists campaigns_user_id_idx on campaigns(user_id);

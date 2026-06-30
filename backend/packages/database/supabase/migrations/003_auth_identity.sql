-- =============================================================================
-- 003_auth_identity.sql
-- App-level auth identity, org membership, refresh token, and recovery tables.
-- =============================================================================

create extension if not exists "pgcrypto";

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists app_organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text generated always as (lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))) stored,
  owner_user_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(slug)
);

create table if not exists app_users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  full_name text not null default '',
  organization_id uuid references app_organizations(id) on delete set null,
  email_verified boolean not null default false,
  auth_provider text not null default 'email',
  password_hash text,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists organization_memberships (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references app_organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('admin', 'manager', 'viewer')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(organization_id, user_id)
);

create table if not exists refresh_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  organization_id uuid not null references app_organizations(id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  revoked boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists email_verification_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists app_users_org_idx on app_users(organization_id);
create index if not exists org_memberships_user_idx on organization_memberships(user_id);
create index if not exists refresh_tokens_user_idx on refresh_tokens(user_id, created_at desc);

create trigger app_organizations_updated_at
  before update on app_organizations
  for each row execute procedure set_updated_at();

create trigger app_users_updated_at
  before update on app_users
  for each row execute procedure set_updated_at();

create trigger organization_memberships_updated_at
  before update on organization_memberships
  for each row execute procedure set_updated_at();

alter table app_organizations enable row level security;
alter table app_users enable row level security;
alter table organization_memberships enable row level security;
alter table refresh_tokens enable row level security;
alter table email_verification_tokens enable row level security;
alter table password_reset_tokens enable row level security;

create policy "app_users own read"
  on app_users for select
  using (id = auth.uid());

create policy "app_users own update"
  on app_users for update
  using (id = auth.uid())
  with check (id = auth.uid());

create policy "org memberships own read"
  on organization_memberships for select
  using (user_id = auth.uid());

create policy "organizations membership read"
  on app_organizations for select
  using (
    exists (
      select 1 from organization_memberships m
      where m.organization_id = app_organizations.id
        and m.user_id = auth.uid()
        and m.is_active = true
    )
  );

create policy "refresh tokens own read"
  on refresh_tokens for select
  using (user_id = auth.uid());

create policy "email verification own read"
  on email_verification_tokens for select
  using (user_id = auth.uid());

create policy "password reset own read"
  on password_reset_tokens for select
  using (user_id = auth.uid());

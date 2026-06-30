-- =============================================================================
-- seed.sql — Sample data for local development
-- Run AFTER all migrations:
--   psql $DATABASE_URL -f seed.sql
--   OR via Supabase dashboard → SQL Editor
--
-- Creates:
--   • 1 organization
--   • 2 users  (owner + editor)
--   • 2 campaigns  (SaaS launch  &  Q3 retention)
--   • content_assets, performance_metrics, agent_logs for each campaign
-- =============================================================================

begin;

-- ─────────────────────────────────────────────────────────────────────────────
-- Fixed UUIDs for deterministic re-seeds
-- ─────────────────────────────────────────────────────────────────────────────
do $$
declare
  -- Organization
  v_org_id        uuid := 'aaaaaaaa-0000-4000-a000-000000000001';

  -- Users  (must exist in auth.users first — insert manually or via Supabase Auth)
  v_user_owner    uuid := 'bbbbbbbb-0000-4000-a000-000000000001';
  v_user_editor   uuid := 'bbbbbbbb-0000-4000-a000-000000000002';

  -- Campaigns
  v_camp_saas     uuid := 'cccccccc-0000-4000-a000-000000000001';
  v_camp_retain   uuid := 'cccccccc-0000-4000-a000-000000000002';

  -- Content assets
  v_asset_1       uuid := 'dddddddd-0000-4000-a000-000000000001';
  v_asset_2       uuid := 'dddddddd-0000-4000-a000-000000000002';
  v_asset_3       uuid := 'dddddddd-0000-4000-a000-000000000003';
  v_asset_4       uuid := 'dddddddd-0000-4000-a000-000000000004';
  v_asset_5       uuid := 'dddddddd-0000-4000-a000-000000000005';
  v_asset_6       uuid := 'dddddddd-0000-4000-a000-000000000006';

begin

  -- ── 1. Organization ─────────────────────────────────────────────────────────
  insert into organizations (id, name, settings)
  values (
    v_org_id,
    'Acme Marketing Co.',
    jsonb_build_object(
      'defaultModel',          'gpt-4o',
      'maxBudgetPerCampaign',  250000,
      'allowedChannels',       array['email','social_linkedin','paid_search','seo','blog'],
      'brandVoice',            'innovative yet approachable',
      'timezone',              'America/New_York'
    )
  )
  on conflict (id) do nothing;

  -- ── 2. Auth users (stubs — real rows created by Supabase Auth signup) ────────
  -- These inserts are for local dev with Supabase CLI only.
  -- In a hosted project, create users via the Auth admin API then run this seed.
  insert into auth.users (
    id, email, encrypted_password, email_confirmed_at,
    raw_user_meta_data, created_at, updated_at, aud, role
  )
  values
    (v_user_owner,  'owner@acme.example',  crypt('Seed@1234!', gen_salt('bf')), now(),
     '{"full_name":"Alex Owner"}'::jsonb,   now(), now(), 'authenticated', 'authenticated'),
    (v_user_editor, 'editor@acme.example', crypt('Seed@1234!', gen_salt('bf')), now(),
     '{"full_name":"Jordan Editor"}'::jsonb, now(), now(), 'authenticated', 'authenticated')
  on conflict (id) do nothing;

  -- ── 3. User profiles ─────────────────────────────────────────────────────────
  insert into user_profiles (id, email, full_name, role, organization_id)
  values
    (v_user_owner,  'owner@acme.example',  'Alex Owner',    'owner',  v_org_id),
    (v_user_editor, 'editor@acme.example', 'Jordan Editor', 'editor', v_org_id)
  on conflict (id) do update set
    organization_id = excluded.organization_id,
    role            = excluded.role;

  -- ── 4. Campaign 1: SaaS Product Launch ───────────────────────────────────────
  insert into campaigns (
    id, organization_id, user_id, name, goal, status,
    channels, budget, timeline, strategy_json, goals, target_audience
  )
  values (
    v_camp_saas,
    v_org_id,
    v_user_owner,
    'SaaS Product Launch — Q3 2026',
    'lead_generation',
    'active',
    array['email','social_linkedin','paid_search','seo']::campaign_channel[],
    85000.00,
    jsonb_build_object(
      'startDate', '2026-07-01',
      'endDate',   '2026-09-30',
      'phases', jsonb_build_array(
        jsonb_build_object('name','Awareness',   'startDate','2026-07-01','endDate','2026-07-31','budgetPct',30),
        jsonb_build_object('name','Demand Gen',  'startDate','2026-08-01','endDate','2026-08-31','budgetPct',45),
        jsonb_build_object('name','Conversion',  'startDate','2026-09-01','endDate','2026-09-30','budgetPct',25)
      )
    ),
    jsonb_build_object(
      'summary',    'Multi-channel launch targeting mid-market SaaS buyers with pain-point led messaging.',
      'targeting',  jsonb_build_object(
        'industries',   array['Software','FinTech','HealthTech'],
        'jobTitles',    array['VP Marketing','Head of Growth','CMO','Director of Demand Gen'],
        'companySizes', array['51-200','201-500'],
        'geographies',  array['US','CA','GB']
      ),
      'messaging',  jsonb_build_object(
        'primaryPain',   'Manual campaign workflows slowing go-to-market velocity',
        'primaryValue',  '10× faster campaign execution with autonomous AI agents',
        'differentiator','Only platform with real-time agent state checkpointing'
      ),
      'budget_allocation', jsonb_build_object(
        'email',        15000,
        'social_linkedin', 20000,
        'paid_search',  40000,
        'seo',          10000
      )
    ),
    array['500 MQLs', '50 SQLs', '10 Closed Won'],
    jsonb_build_object(
      'ageRange',    jsonb_build_object('min',28,'max',50),
      'interests',   array['MarTech','AI tools','Growth hacking'],
      'geographies', array['US','CA','GB']
    )
  )
  on conflict (id) do nothing;

  -- ── 5. Campaign 2: Q3 Retention ──────────────────────────────────────────────
  insert into campaigns (
    id, organization_id, user_id, name, goal, status,
    channels, budget, timeline, strategy_json, goals, target_audience
  )
  values (
    v_camp_retain,
    v_org_id,
    v_user_editor,
    'Q3 Customer Retention Drive',
    'retention',
    'draft',
    array['email','push_notification','sms']::campaign_channel[],
    22000.00,
    jsonb_build_object(
      'startDate', '2026-07-15',
      'endDate',   '2026-09-15',
      'phases', jsonb_build_array(
        jsonb_build_object('name','Re-engagement', 'startDate','2026-07-15','endDate','2026-08-15','budgetPct',60),
        jsonb_build_object('name','Loyalty',        'startDate','2026-08-16','endDate','2026-09-15','budgetPct',40)
      )
    ),
    jsonb_build_object(
      'summary',    'Win-back lapsed users and reward high-LTV customers with personalised outreach.',
      'targeting',  jsonb_build_object(
        'segments', array['lapsed_30d','lapsed_60d','high_ltv'],
        'excludes', array['churned_gt_90d','enterprise_csm_owned']
      ),
      'messaging', jsonb_build_object(
        'primaryPain',   'Customers drifting due to lack of personalised touchpoints',
        'primaryValue',  'We have made improvements you asked for — come back!',
        'differentiator','Hyper-personalised, AI-generated copy per segment'
      ),
      'budget_allocation', jsonb_build_object(
        'email',             12000,
        'push_notification',  6000,
        'sms',                4000
      )
    ),
    array['Reduce churn by 15%', 'Reactivate 2000 lapsed users', 'NPS +5'],
    jsonb_build_object(
      'segments',    array['lapsed_30d','lapsed_60d','high_ltv'],
      'geographies', array['US','CA']
    )
  )
  on conflict (id) do nothing;

  -- ── 6. Content Assets ─────────────────────────────────────────────────────────

  -- Campaign 1 assets
  insert into content_assets (id, campaign_id, channel, content_type, content, variant, status, metadata)
  values
  (
    v_asset_1, v_camp_saas,
    'email', 'subject_line',
    'Stop running campaigns manually. Meet your new AI co-pilot.',
    'control', 'approved',
    jsonb_build_object(
      'wordCount', 9, 'tone', 'provocative',
      'keywords', array['AI campaign manager','automation'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  ),
  (
    v_asset_2, v_camp_saas,
    'email', 'subject_line',
    'Your competitors launched 3 campaigns while you were in Slack.',
    'variant_a', 'review',
    jsonb_build_object(
      'wordCount', 10, 'tone', 'competitive',
      'keywords', array['campaign velocity','automation'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  ),
  (
    v_asset_3, v_camp_saas,
    'social_linkedin', 'body_copy',
    E'🚀 Introducing Autonomous Campaign Manager\n\nMost marketing teams spend 60% of their time on execution — not strategy.\n\nWe built ACM to flip that ratio.\n\n→ AI agents that research, write, and optimise in parallel\n→ LangGraph state checkpointing so nothing is lost mid-run\n→ Real-time performance feedback loops\n\nClosed beta opens July 1. Link in comments. 👇',
    'control', 'published',
    jsonb_build_object(
      'wordCount', 65, 'tone', 'thought-leadership',
      'keywords', array['AI marketing','LangGraph','campaign automation'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  ),

  -- Campaign 2 assets
  (
    v_asset_4, v_camp_retain,
    'email', 'subject_line',
    'We listened. Here''s what changed since you left.',
    'control', 'draft',
    jsonb_build_object(
      'wordCount', 8, 'tone', 'empathetic',
      'keywords', array['re-engagement','product updates'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  ),
  (
    v_asset_5, v_camp_retain,
    'push_notification', 'push_message',
    'Hey {{first_name}} — your data is waiting 👋 Log back in for a personalised recap.',
    'control', 'draft',
    jsonb_build_object(
      'wordCount', 15, 'tone', 'friendly',
      'keywords', array['reactivation','push'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  ),
  (
    v_asset_6, v_camp_retain,
    'sms', 'cta',
    'ACM: You have unused credits expiring soon. Activate now → acm.io/comeback',
    'control', 'draft',
    jsonb_build_object(
      'wordCount', 12, 'tone', 'urgent',
      'keywords', array['retention','sms','credits'],
      'generatedBy', 'campaign_agent_v1', 'promptVersion', '2026-06-01'
    )
  )
  on conflict (id) do nothing;

  -- ── 7. Performance Metrics ────────────────────────────────────────────────────

  insert into performance_metrics (campaign_id, channel, metric_name, metric_value, recorded_at)
  values
  -- Campaign 1 — email
  (v_camp_saas, 'email',          'impressions',      12450,   now() - interval '20 days'),
  (v_camp_saas, 'email',          'open_rate',        0.3820,  now() - interval '20 days'),
  (v_camp_saas, 'email',          'click_rate',       0.0640,  now() - interval '20 days'),
  (v_camp_saas, 'email',          'conversions',      48,      now() - interval '20 days'),
  (v_camp_saas, 'email',          'cost_per_lead',    14.58,   now() - interval '20 days'),
  -- Campaign 1 — LinkedIn
  (v_camp_saas, 'social_linkedin','impressions',      58320,   now() - interval '18 days'),
  (v_camp_saas, 'social_linkedin','engagement_rate',  0.0430,  now() - interval '18 days'),
  (v_camp_saas, 'social_linkedin','clicks',           2107,    now() - interval '18 days'),
  (v_camp_saas, 'social_linkedin','cost_per_click',   4.12,    now() - interval '18 days'),
  -- Campaign 1 — Paid Search
  (v_camp_saas, 'paid_search',    'impressions',      142000,  now() - interval '15 days'),
  (v_camp_saas, 'paid_search',    'clicks',           8540,    now() - interval '15 days'),
  (v_camp_saas, 'paid_search',    'ctr',              0.0601,  now() - interval '15 days'),
  (v_camp_saas, 'paid_search',    'conversions',      214,     now() - interval '15 days'),
  (v_camp_saas, 'paid_search',    'cost_per_conversion', 28.50, now() - interval '15 days'),
  (v_camp_saas, 'paid_search',    'roas',             3.20,    now() - interval '15 days');

  -- ── 8. Agent Logs ─────────────────────────────────────────────────────────────

  insert into agent_logs (
    campaign_id, agent_name, action, input_payload, output_payload, latency_ms, model, token_usage, "timestamp"
  )
  values
  (
    v_camp_saas, 'campaign_planner', 'plan',
    jsonb_build_object('campaign_id', v_camp_saas, 'instruction', 'Create full Q3 launch plan'),
    jsonb_build_object('phases', 3, 'channels', 4, 'estimated_budget', 85000),
    1240, 'gpt-4o',
    jsonb_build_object('prompt', 3420, 'completion', 812, 'total', 4232),
    now() - interval '25 days'
  ),
  (
    v_camp_saas, 'audience_researcher', 'research',
    jsonb_build_object('query', 'mid-market SaaS buyer persona 2026', 'channels', array['email','social_linkedin']),
    jsonb_build_object('insights', 12, 'keywords', 47, 'personas', 3),
    3850, 'gpt-4o',
    jsonb_build_object('prompt', 5100, 'completion', 1940, 'total', 7040),
    now() - interval '24 days'
  ),
  (
    v_camp_saas, 'content_writer', 'generate_content',
    jsonb_build_object('channel', 'email', 'content_type', 'subject_line', 'variants', 2),
    jsonb_build_object('assets_created', 2, 'asset_ids', array[v_asset_1, v_asset_2]),
    2310, 'gpt-4o',
    jsonb_build_object('prompt', 2880, 'completion', 620, 'total', 3500),
    now() - interval '23 days'
  ),
  (
    v_camp_saas, 'content_writer', 'generate_content',
    jsonb_build_object('channel', 'social_linkedin', 'content_type', 'body_copy', 'variants', 1),
    jsonb_build_object('assets_created', 1, 'asset_ids', array[v_asset_3]),
    1890, 'gpt-4o',
    jsonb_build_object('prompt', 2100, 'completion', 480, 'total', 2580),
    now() - interval '23 days'
  ),
  (
    v_camp_saas, 'performance_analyser', 'analyse_performance',
    jsonb_build_object('campaign_id', v_camp_saas, 'window_days', 7),
    jsonb_build_object('top_channel', 'paid_search', 'roas', 3.20, 'recommendations', 3),
    980, 'gpt-4o',
    jsonb_build_object('prompt', 1800, 'completion', 540, 'total', 2340),
    now() - interval '14 days'
  ),
  (
    v_camp_retain, 'campaign_planner', 'plan',
    jsonb_build_object('campaign_id', v_camp_retain, 'instruction', 'Build retention playbook for lapsed segments'),
    jsonb_build_object('phases', 2, 'channels', 3, 'estimated_budget', 22000),
    1150, 'gpt-4o',
    jsonb_build_object('prompt', 2900, 'completion', 710, 'total', 3610),
    now() - interval '10 days'
  ),
  (
    v_camp_retain, 'content_writer', 'generate_content',
    jsonb_build_object('channel', 'email', 'content_type', 'subject_line', 'segments', array['lapsed_30d','lapsed_60d']),
    jsonb_build_object('assets_created', 1, 'asset_ids', array[v_asset_4]),
    1640, 'gpt-4o',
    jsonb_build_object('prompt', 2200, 'completion', 390, 'total', 2590),
    now() - interval '9 days'
  );

end $$;

commit;

# Database Schema & Design

## Overview

The Autonomous Campaign Manager uses **Supabase PostgreSQL** for persistent storage. The database is designed for:
- Multi-user campaign isolation
- Campaign execution state tracking
- Approval gate management
- Event sourcing and audit trails
- Efficient querying of campaign timelines

## Schema

### Users Table

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT DEFAULT 'user', -- 'user', 'admin'
  name TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);
```

**Purpose**: User account management and authentication

### Campaigns Table

```sql
CREATE TABLE campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  campaign_name TEXT NOT NULL,
  business_goal TEXT NOT NULL,
  target_audience TEXT NOT NULL,
  budget_total DECIMAL(10,2) NOT NULL,
  channels TEXT[] NOT NULL, -- ['social_media', 'email', 'influencer']
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status TEXT DEFAULT 'draft', -- 'draft', 'active', 'completed', 'archived'
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  CONSTRAINT positive_budget CHECK (budget_total > 0),
  CONSTRAINT valid_dates CHECK (start_date < end_date)
);

CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_created_at ON campaigns(created_at DESC);
```

**Purpose**: Campaign definitions and metadata

### Campaign Runs Table

```sql
CREATE TABLE campaign_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  state_json JSONB NOT NULL, -- LangGraph state snapshot
  status TEXT DEFAULT 'pending', 
  -- 'pending', 'planner_running', 'strategy_review', 'content_running', 
  -- 'media_running', 'budget_review', 'analysis_running', 
  -- 'completed', 'failed', 'cancelled'
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  CONSTRAINT single_active_run_per_campaign CHECK (
    status IN ('pending', 'planner_running', 'strategy_review', 
               'content_running', 'media_running', 'budget_review', 
               'analysis_running') 
    OR completed_at IS NOT NULL
  )
);

CREATE INDEX idx_campaign_runs_campaign_id ON campaign_runs(campaign_id);
CREATE INDEX idx_campaign_runs_status ON campaign_runs(status);
CREATE INDEX idx_campaign_runs_created_at ON campaign_runs(created_at DESC);
```

**Purpose**: Track execution state for each campaign run

### Approvals Table

```sql
CREATE TABLE approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_run_id UUID NOT NULL REFERENCES campaign_runs(id) ON DELETE CASCADE,
  campaign_id UUID NOT NULL REFERENCES campaigns(id),
  gate TEXT NOT NULL, -- 'strategy', 'budget'
  payload_json JSONB NOT NULL, -- Content for user review
  approved BOOLEAN,
  reviewer_id UUID NOT NULL REFERENCES users(id),
  comments TEXT,
  decided_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT now(),
  
  CONSTRAINT decision_requires_timestamp CHECK (
    (approved IS NULL AND decided_at IS NULL) OR
    (approved IS NOT NULL AND decided_at IS NOT NULL)
  )
);

CREATE INDEX idx_approvals_campaign_run_id ON approvals(campaign_run_id);
CREATE INDEX idx_approvals_gate ON approvals(gate);
CREATE INDEX idx_approvals_decided_at ON approvals(decided_at DESC);
```

**Purpose**: Track approval gate decisions and audit trail

### Reports Table

```sql
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_run_id UUID NOT NULL REFERENCES campaign_runs(id) ON DELETE CASCADE,
  campaign_id UUID NOT NULL REFERENCES campaigns(id),
  report_json JSONB NOT NULL, -- Structured report data
  report_markdown TEXT, -- Markdown export
  report_pdf BYTEA, -- PDF export (if generated)
  summary TEXT, -- Executive summary
  sections JSONB NOT NULL, -- Array of report sections
  recommendations TEXT[], -- Key recommendations
  export_formats TEXT[] DEFAULT ARRAY['json', 'markdown'],
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_reports_campaign_run_id ON reports(campaign_run_id);
CREATE INDEX idx_reports_campaign_id ON reports(campaign_id);
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);
```

**Purpose**: Store generated campaign reports and outputs

### Events Table (Audit Trail)

```sql
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id),
  campaign_run_id UUID REFERENCES campaign_runs(id),
  event_type TEXT NOT NULL, 
  -- 'agent_started', 'agent_completed', 'approval_required',
  -- 'approval_received', 'workflow_completed', 'workflow_failed'
  agent_name TEXT, -- 'planner', 'content_creator', 'media_buyer', etc.
  payload_json JSONB, -- Event details
  created_at TIMESTAMP DEFAULT now(),
  
  INDEX idx_events_campaign_id (campaign_id),
  INDEX idx_events_campaign_run_id (campaign_run_id),
  INDEX idx_events_event_type (event_type),
  INDEX idx_events_created_at (created_at DESC)
);
```

**Purpose**: Complete audit trail of all campaign execution events

## Migrations

### Directory Structure
```
backend/packages/database/supabase/migrations/
├── 001_initial.sql          -- Initial table creation
├── 002_full_schema.sql      -- Complete schema with all tables
└── 003_auth_identity.sql    -- Authentication and RLS policies
```

### Running Migrations

**Local Development**:
```bash
cd backend/packages/database
npx supabase db pull  # Fetch current schema
```

**Production**:
```bash
npx supabase db push --db-url $PRODUCTION_DB_URL
```

## Data Model Relationships

```
users (1) ──────── (N) campaigns
  │
  └──── (1) ─────── (N) approvals (via campaign_run)
  
campaigns (1) ──────---- (N) campaign_runs
  │
  ├─ (1) ───── (N) approvals
  ├─ (1) ───── (N) reports
  └─ (1) ───── (N) events

campaign_runs (1) ──-- (N) approvals
             (1) ──-- (1) reports
             (1) ──-- (N) events
```

## Query Patterns

### Get Active Campaign with Latest Run

```sql
SELECT c.*, cr.id as run_id, cr.status as run_status
FROM campaigns c
LEFT JOIN campaign_runs cr ON c.id = cr.campaign_id
WHERE c.id = $1 AND c.user_id = $2
ORDER BY cr.created_at DESC LIMIT 1;
```

### Get Pending Approvals for User

```sql
SELECT a.*, c.campaign_name, cr.status as run_status
FROM approvals a
JOIN campaign_runs cr ON a.campaign_run_id = cr.id
JOIN campaigns c ON a.campaign_id = c.id
WHERE a.approved IS NULL
  AND c.user_id = $1
ORDER BY a.created_at DESC;
```

### Get Campaign Event Timeline

```sql
SELECT * FROM events
WHERE campaign_id = $1
ORDER BY created_at DESC
LIMIT 100;
```

### Get Report for Campaign

```sql
SELECT r.* FROM reports r
JOIN campaign_runs cr ON r.campaign_run_id = cr.id
WHERE cr.campaign_id = $1
ORDER BY r.created_at DESC LIMIT 1;
```

## Performance Considerations

### Indexing Strategy

**Frequently Queried Columns**:
- `campaigns.user_id`: Filter campaigns by owner
- `campaign_runs.campaign_id`: Get execution history
- `approvals.gate`: Filter by approval type
- `events.created_at`: Fetch recent events

**Composite Indexes** (future optimization):
```sql
CREATE INDEX idx_campaign_runs_campaign_status 
ON campaign_runs(campaign_id, status);

CREATE INDEX idx_events_campaign_time 
ON events(campaign_id, created_at DESC);
```

### Partitioning (for scale)

**Option**: Partition `events` table by created_at (monthly or quarterly)

```sql
CREATE TABLE events_2026_06 PARTITION OF events
FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

## Backup Strategy

### Automated Backups (Supabase)
- Daily snapshots with 7-day retention
- Point-in-time recovery available

### Manual Backups
```bash
# Export full database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Export specific table
pg_dump $DATABASE_URL -t campaigns > campaigns_backup.sql
```

## Security

### Row-Level Security (RLS)

```sql
-- Enable RLS on all tables
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

-- Users see only their campaigns
CREATE POLICY campaigns_rls ON campaigns
FOR SELECT USING (user_id = current_user_id());

CREATE POLICY campaigns_insert ON campaigns
FOR INSERT WITH CHECK (user_id = current_user_id());

-- Similar policies for other tables
```

### Sensitive Data

**Never store**:
- API keys or secrets (use environment variables)
- Password hashes (use Supabase Auth)
- Credit card numbers (external payment processor)

## Maintenance

### Regular Tasks

**Weekly**:
- Monitor query performance (slow query logs)
- Check disk usage and connection count

**Monthly**:
- Analyze table statistics
- Review and optimize hot queries

**Quarterly**:
- Full schema review
- Backup integrity check

### Troubleshooting

**Issue**: Slow campaign list queries
- **Solution**: Add missing indexes, check `campaigns.user_id` selectivity

**Issue**: Event table growing too large
- **Solution**: Archive old events, implement partitioning

**Issue**: Approval decision delays
- **Solution**: Check FK constraint performance, add index on `campaign_run_id`

## Future Enhancements

1. **Temporal Tables**: Track campaign metadata changes over time
2. **Full-Text Search**: Enable search on campaign names and goals
3. **Materialized Views**: Pre-aggregate campaign metrics
4. **Archive Strategy**: Archive completed campaigns to separate schema
5. **Encryption**: Encrypt sensitive fields at rest

---

**Schema Diagram**: See `docs/database.mmd` (to be created)

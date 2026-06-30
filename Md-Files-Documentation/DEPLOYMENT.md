# Deployment Guide

## Overview

This guide covers deploying the Autonomous Campaign Manager to production environments. The system uses a multi-service architecture with Frontend, Backend, and Agent services.

## Pre-Deployment Checklist

- [ ] All tests passing (`pnpm test`)
- [ ] Code reviewed and approved (2+ reviewers)
- [ ] No breaking changes documented
- [ ] Security audit completed
- [ ] Load testing completed (if applicable)
- [ ] Backup strategy validated
- [ ] Rollback plan documented
- [ ] Team notified of deployment window

## Deployment Architecture

```
┌─────────────────────────────────┐
│  Frontend (Vercel/Firebase)     │
│  - Next.js App                  │
│  - Auto-deploys from main       │
└────────────────┬────────────────┘
                 │
    ┌────────────┴───────────┐
    │                        │
    │   CDN (CloudFlare)     │
    │                        │
    └────────────┬───────────┘
                 │
┌────────────────▼──────────────────┐
│  API Gateway / Load Balancer      │
│  - SSL/TLS termination            │
│  - Rate limiting                  │
│  - Request routing                │
└────────────────┬──────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼────────────────┐  ┌────▼───────────┐
│  FastAPI Servers   │  │  Task Workers   │
│  (x3 instances)    │  │  (x2 instances) │
│  - Port 8000       │  │                 │
│  - Auto-scaling    │  │ LangGraph       │
│  - Health checks   │  │ Orchestration   │
└────────────────────┘  └────────────────┘
         │                      │
    ┌────▼──────────────────────┘
    │
┌───▼──────────────────────────────┐
│  Supabase Cloud / RDS Database   │
│  - PostgreSQL 15+                │
│  - Automated backups (daily)     │
│  - Read replicas for scale       │
└──────────────────────────────────┘
```

## Frontend Deployment

### Option 1: Vercel (Recommended)

**Advantages**: Zero-config, auto-scaling, global CDN, free tier available

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd frontend/apps/web
vercel --prod

# Or connect GitHub for auto-deploy
# - Push to main → Auto-deploy to production
# - Push to feature branch → Deploy preview
```

**Environment Variables in Vercel**:
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

### Option 2: Self-Hosted (Docker)

**Dockerfile** (`frontend/Dockerfile.prod`):
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install

COPY . .
RUN pnpm --filter @acm/web build

# Runtime stage
FROM node:20-alpine
WORKDIR /app

RUN npm install -g pnpm
COPY --from=builder /app/frontend/apps/web/.next ./frontend/apps/web/.next
COPY --from=builder /app/frontend/apps/web/public ./frontend/apps/web/public
COPY --from=builder /app/frontend/apps/web/package.json ./frontend/apps/web/

WORKDIR /app/frontend/apps/web
RUN pnpm install --prod

EXPOSE 3000
CMD ["pnpm", "start"]
```

**Deploy**:
```bash
docker build -f frontend/Dockerfile.prod -t acm-web:latest .
docker push your-registry/acm-web:latest

# Kubernetes deployment
kubectl set image deployment/web web=your-registry/acm-web:latest
kubectl rollout status deployment/web
```

## Backend API Deployment

### Option 1: AWS ECS / App Runner

**Dockerfile** (`backend/Dockerfile.api`):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install agents package
COPY backend/packages/agents ./packages/agents
RUN pip install -e ./packages/agents

# Copy API code
COPY backend/apps/api/app ./app
COPY backend/apps/api/main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**AWS App Runner**:
```bash
aws apprunner create-service \
  --service-name acm-api \
  --source-configuration \
    RepositoryType=GITHUB,RepositoryUrl=https://github.com/your-org/repo \
  --instance-configuration Cpu=2,Memory=4096 \
  --environment SUPABASE_URL=$SUPABASE_URL \
    SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY \
    OPENAI_API_KEY=$OPENAI_API_KEY
```

### Option 2: Google Cloud Run

```bash
gcloud run deploy acm-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --set-env-vars \
    SUPABASE_URL=$SUPABASE_URL,\
    SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY,\
    OPENAI_API_KEY=$OPENAI_API_KEY
```

### Option 3: Kubernetes (Advanced)

**Deployment YAML** (`k8s/api-deployment.yaml`):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: acm-api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: acm-api
  template:
    metadata:
      labels:
        app: acm-api
    spec:
      containers:
      - name: api
        image: your-registry/acm-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: SUPABASE_URL
          valueFrom:
            secretKeyRef:
              name: supabase-secrets
              key: url
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: acm-api-service
  namespace: production
spec:
  selector:
    app: acm-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

**Deploy**:
```bash
kubectl apply -f k8s/api-deployment.yaml
kubectl rollout status deployment/acm-api -n production
```

## Database Deployment

### Supabase Cloud (Recommended)

1. **Create Project** on supabase.com
2. **Run Migrations**:
   ```bash
   psql $DATABASE_URL < migrations/001_initial.sql
   psql $DATABASE_URL < migrations/002_full_schema.sql
   psql $DATABASE_URL < migrations/003_auth_identity.sql
   ```
3. **Verify Schema**:
   ```bash
   psql $DATABASE_URL -c "\dt"
   ```
4. **Set Up Backups**: Supabase handles automatic daily backups

### Self-Hosted PostgreSQL

**Docker Compose** (`docker-compose.prod.yml`):
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: campaign_manager
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - acm-network

  pgbackups:
    image: onecessity/docker-pg-backup
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_DB: campaign_manager
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      BACKUP_DIR: /backups
    volumes:
      - pg_backups:/backups
    depends_on:
      - postgres
    networks:
      - acm-network

volumes:
  postgres_data:
  pg_backups:

networks:
  acm-network:
```

**Deploy**:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Environment Configuration

### Production Environment Variables

**Backend (`.env.production`)**:
```env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=prod-anon-key
SUPABASE_SERVICE_ROLE_KEY=prod-service-role-key

# API
API_SECRET_KEY=$(openssl rand -hex 32)  # Generate secure key
FRONTEND_URL=https://app.your-domain.com

# LLM
OPENAI_API_KEY=prod-openai-key
# OR
ANTHROPIC_API_KEY=prod-anthropic-key

# Logging & Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-project

# Security
SECURE_COOKIES=true
HTTPS_ONLY=true
ALLOWED_ORIGINS=https://app.your-domain.com
```

**Frontend (`.env.production`)**:
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=prod-anon-key
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_ENABLE_DEBUG=false
NEXT_PUBLIC_ENABLE_API_MOCKS=false
```

### Secrets Management

**Store secrets in**:
- GitHub Secrets (for CI/CD)
- Cloud provider secrets (AWS Secrets Manager, GCP Secret Manager, etc.)
- Encrypted .env files (locally only)

**Never**:
- Commit .env files
- Log sensitive values
- Pass secrets in URLs
- Share secrets via chat/email

## Deployment Process

### 1. Pre-Deployment

```bash
# Pull latest code
git pull origin main

# Run all tests
pnpm test
pnpm test:e2e

# Build frontend
cd frontend/apps/web && pnpm build

# Verify no errors
pnpm type-check
pnpm lint
```

### 2. Database Migrations

```bash
# Test migrations locally first
psql $LOCAL_DB_URL < new_migration.sql

# Apply to production (with backup)
supabase db push

# Verify
psql $PROD_DB_URL -c "\dt"
```

### 3. Deploy Backend

```bash
# Build and push image
docker build -f backend/Dockerfile.api -t acm-api:v1.0.0 .
docker push your-registry/acm-api:v1.0.0

# Deploy with blue-green strategy
# Keep old version running while rolling out new version
kubectl set image deployment/acm-api \
  acm-api=your-registry/acm-api:v1.0.0 \
  --record=true

# Monitor rollout
kubectl rollout status deployment/acm-api
```

### 4. Deploy Frontend

```bash
# For Vercel: Auto-deploys on push to main
git push origin main

# For self-hosted:
docker build -f frontend/Dockerfile.prod -t acm-web:v1.0.0 .
docker push your-registry/acm-web:v1.0.0

kubectl set image deployment/web \
  web=your-registry/acm-web:v1.0.0 \
  --record=true
```

### 5. Smoke Tests

```bash
# Check health endpoints
curl https://api.your-domain.com/health

# Verify frontend loads
curl https://app.your-domain.com

# Test critical flow (automated or manual)
pnpm test:smoke
```

## Monitoring & Alerting

### Health Checks

```python
# Implement comprehensive health checks
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_database(),
        "redis": await check_redis(),
        "orchestrator": await check_orchestrator(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Logging

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "campaign_started",
    campaign_id=campaign_id,
    user_id=user_id,
    timestamp=datetime.utcnow()
)
```

### Metrics

- API response time
- Campaign success rate
- Agent execution time
- Database query performance
- WebSocket connection count

### Alerts

Set up alerts for:
- API error rate > 1%
- Agent orchestration failures > 5%
- Database connections > 80%
- Memory usage > 85%
- API response time > 5s

## Rollback Process

If deployment fails:

```bash
# Check rollout status
kubectl rollout history deployment/acm-api

# Rollback to previous version
kubectl rollout undo deployment/acm-api

# Verify rollback
kubectl get pods
kubectl logs -l app=acm-api
```

**For database**:
```bash
# Point back to previous backup
psql $PROD_DB_URL < backups/backup-before-migration.sql

# Verify data integrity
psql $PROD_DB_URL -c "SELECT COUNT(*) FROM campaigns;"
```

## Post-Deployment

- [ ] Monitor error logs for 30 minutes
- [ ] Verify key metrics are healthy
- [ ] Test critical user flows manually
- [ ] Document any issues encountered
- [ ] Notify team of successful deployment
- [ ] Update status page if applicable

## Disaster Recovery

### Data Loss

```bash
# Restore from backup
pg_restore -d campaign_manager latest_backup.dump

# Verify restore
psql -d campaign_manager -c "SELECT COUNT(*) FROM campaigns;"
```

### Service Failure

```bash
# For containerized services
docker restart acm-api

# For Kubernetes
kubectl restart deployment acm-api

# For AWS AppRunner
aws apprunner restart-service --service-arn <arn>
```

## Scaling

### Horizontal Scaling

```bash
# Increase API replicas
kubectl scale deployment acm-api --replicas=5

# Kubernetes auto-scaling
kubectl autoscale deployment acm-api --min=3 --max=10 --cpu-percent=70
```

### Database Scaling

```bash
# For Supabase: Scale compute in dashboard
# For self-hosted PostgreSQL:
# - Add read replicas
# - Enable connection pooling (PgBouncer)
# - Partition large tables
```

## Cost Optimization

- Use reserved instances for predictable workloads
- Enable auto-scaling to handle spikes
- Use CDN for static assets
- Archive old campaign data to cold storage
- Monitor and optimize database queries

---

**Related Documentation**:
- [SYSTEM_SETUP.md](SYSTEM_SETUP.md) - Local setup
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development environment
- [SECURITY.md](SECURITY.md) - Security best practices
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

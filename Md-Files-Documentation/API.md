# API Documentation

## Overview

The Autonomous Campaign Manager API is built with FastAPI and provides RESTful endpoints for authentication, campaign management, approvals, and reporting. All endpoints require authentication except for `/auth/register` and `/auth/login`.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://api.autonomous-campaign-manager.com` (placeholder)

## Authentication

### Endpoints

#### Register User
```
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response: 201 Created
{
  "id": "user-uuid",
  "email": "user@example.com",
  "created_at": "2026-06-29T10:00:00Z"
}
```

#### Login
```
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response: 200 OK
{
  "access_token": "jwt-token-here",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com"
  }
}
```

#### Get Current User
```
GET /auth/me
Authorization: Bearer <access_token>

Response: 200 OK
{
  "id": "user-uuid",
  "email": "user@example.com",
  "role": "user",
  "created_at": "2026-06-29T10:00:00Z"
}
```

## Campaign Management

### Endpoints

#### Create Campaign
```
POST /api/v1/campaigns
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "campaign_name": "Summer Product Launch",
  "business_goal": "Increase brand awareness among 18-34 demographic",
  "target_audience": "Tech-savvy millennials interested in innovative products",
  "budget_total": 5000,
  "channels": ["social_media", "email", "influencer"],
  "start_date": "2026-07-01",
  "end_date": "2026-07-31"
}

Response: 201 Created
{
  "id": "campaign-uuid",
  "user_id": "user-uuid",
  "campaign_name": "Summer Product Launch",
  "business_goal": "Increase brand awareness among 18-34 demographic",
  "target_audience": "Tech-savvy millennials interested in innovative products",
  "budget_total": 5000,
  "channels": ["social_media", "email", "influencer"],
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "status": "draft",
  "created_at": "2026-06-29T10:00:00Z",
  "updated_at": "2026-06-29T10:00:00Z"
}
```

#### List Campaigns
```
GET /api/v1/campaigns
Authorization: Bearer <access_token>
Query parameters:
  - status: draft|active|completed|archived (optional)
  - skip: 0 (default)
  - limit: 10 (default)

Response: 200 OK
{
  "items": [
    {
      "id": "campaign-uuid",
      "campaign_name": "Summer Product Launch",
      "status": "draft",
      "budget_total": 5000,
      "created_at": "2026-06-29T10:00:00Z"
    }
  ],
  "total": 15,
  "skip": 0,
  "limit": 10
}
```

#### Get Campaign Details
```
GET /api/v1/campaigns/{campaign_id}
Authorization: Bearer <access_token>

Response: 200 OK
{
  "id": "campaign-uuid",
  "user_id": "user-uuid",
  "campaign_name": "Summer Product Launch",
  "business_goal": "Increase brand awareness",
  "status": "active",
  "budget_total": 5000,
  "created_at": "2026-06-29T10:00:00Z",
  "updated_at": "2026-06-29T10:30:00Z"
}
```

#### Start Campaign Orchestration
```
POST /api/v1/campaigns/{campaign_id}/start
Authorization: Bearer <access_token>
Content-Type: application/json

{}

Response: 202 Accepted
{
  "campaign_id": "campaign-uuid",
  "run_id": "run-uuid",
  "status": "orchestration_started",
  "message": "Campaign orchestration initiated. Agents are processing the request.",
  "started_at": "2026-06-29T10:30:00Z"
}
```

## Approvals

### Endpoints

#### Get Approval Request
```
GET /api/v1/campaigns/{campaign_id}/approvals/pending
Authorization: Bearer <access_token>

Response: 200 OK
{
  "id": "approval-uuid",
  "campaign_id": "campaign-uuid",
  "run_id": "run-uuid",
  "gate": "strategy",
  "payload": {
    "strategy_summary": "Focus on social media channels...",
    "estimated_reach": 50000,
    "timeline": "4 weeks"
  },
  "created_at": "2026-06-29T10:30:00Z"
}
```

#### Approve/Reject Campaign
```
POST /api/v1/campaigns/{campaign_id}/approve
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "gate": "strategy",
  "approved": true,
  "comments": "Strategy looks solid, proceeding to budget review"
}

Response: 200 OK
{
  "id": "approval-uuid",
  "campaign_id": "campaign-uuid",
  "gate": "strategy",
  "approved": true,
  "reviewer_id": "user-uuid",
  "comments": "Strategy looks solid, proceeding to budget review",
  "decided_at": "2026-06-29T10:45:00Z"
}
```

## Reporting

### Endpoints

#### Get Campaign Report
```
GET /api/v1/campaigns/{campaign_id}/report
Authorization: Bearer <access_token>
Query parameters:
  - format: json|markdown (optional, default: json)

Response: 200 OK
{
  "campaign_id": "campaign-uuid",
  "run_id": "run-uuid",
  "summary": "Campaign execution completed successfully...",
  "sections": [
    {
      "title": "Executive Summary",
      "content": "..."
    },
    {
      "title": "Strategy Recommendations",
      "content": "..."
    }
  ],
  "metrics": {
    "estimated_reach": 50000,
    "engagement_rate": 0.08,
    "cost_per_engagement": 10
  },
  "export_formats": ["json", "markdown"],
  "created_at": "2026-06-29T12:00:00Z"
}
```

#### Export Report
```
GET /api/v1/campaigns/{campaign_id}/report/export
Authorization: Bearer <access_token>
Query parameters:
  - format: json|markdown|pdf

Response: 200 OK
Content-Type: application/json (or text/markdown, application/pdf)
[Report content in requested format]
```

## Health & Status

### Endpoints

#### Health Check
```
GET /health

Response: 200 OK
{
  "status": "healthy",
  "timestamp": "2026-06-29T10:00:00Z",
  "services": {
    "database": "connected",
    "queue": "active",
    "orchestrator": "ready"
  }
}
```

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "CAMPAIGN_NOT_FOUND",
    "message": "Campaign with ID campaign-uuid not found",
    "status": 404,
    "timestamp": "2026-06-29T10:00:00Z"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| UNAUTHORIZED | 401 | Missing or invalid authentication token |
| FORBIDDEN | 403 | Insufficient permissions for this resource |
| CAMPAIGN_NOT_FOUND | 404 | Campaign does not exist |
| VALIDATION_ERROR | 422 | Request body validation failed |
| RATE_LIMIT_EXCEEDED | 429 | API rate limit exceeded |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error |

## Rate Limiting

- **Default limit**: 100 requests per minute per user
- **Header**: `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Exceeded**: Returns `429 Too Many Requests`

## Pagination

List endpoints support cursor-based pagination:

```json
{
  "items": [...],
  "total": 100,
  "skip": 0,
  "limit": 10,
  "has_more": true
}
```

## Best Practices

1. **Caching**: Cache `GET /auth/me` responses (5-minute TTL)
2. **Polling**: For campaign status, use WebSocket instead of polling API
3. **Error Handling**: Implement exponential backoff for retries
4. **Security**: Never expose `access_token` in URLs; use Authorization headers
5. **Rate Limiting**: Implement client-side rate limiting before hitting server limits

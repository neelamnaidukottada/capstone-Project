# Security Guidelines & Best Practices

## Overview

This document outlines the security architecture, practices, and guidelines for the Autonomous Campaign Manager. All contributors must adhere to these standards.

## Authentication & Authorization

### Authentication Flow

```mermaid
sequenceDiagram
    User->>Frontend: Enter credentials
    Frontend->>Supabase Auth: POST /auth/register or /auth/login
    Supabase Auth->>Frontend: JWT token
    Frontend->>API: Request with JWT in Authorization header
    API->>Supabase Auth: Verify JWT
    Supabase Auth->>API: User claims
    API->>Database: Check user permissions
    Database->>API: User record
    API->>Frontend: Authenticated response
```

### JWT Token Handling

**Frontend**:
```typescript
// Store token securely
const token = localStorage.getItem('auth_token'); // Browser storage (consider httpOnly for production)

// Always include in Authorization header
const headers = {
  'Authorization': `Bearer ${token}`
};

// Never log or expose token
console.log(token); // ❌ NEVER
```

**Backend**:
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthenticationCredentials

security = HTTPBearer()

def verify_jwt_token(credentials: HTTPAuthenticationCredentials = Depends(security)):
    """Verify JWT token from request"""
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/campaigns")
async def get_campaigns(current_user = Depends(verify_jwt_token)):
    # current_user is now authenticated and verified
    return db.get_user_campaigns(current_user.id)
```

### Authorization

**Row-Level Security (RLS) Policy**:
```sql
-- Users can only see their own campaigns
CREATE POLICY campaigns_rls ON campaigns
FOR SELECT USING (user_id = auth.uid());

CREATE POLICY campaigns_insert ON campaigns
FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY campaigns_update ON campaigns
FOR UPDATE USING (user_id = auth.uid());
```

**API Authorization Check**:
```python
@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, current_user = Depends(verify_jwt_token)):
    campaign = await db.get_campaign(campaign_id)
    
    if campaign.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return campaign
```

## Data Protection

### Encryption at Rest

- **Database**: Supabase PostgreSQL encrypts all data at rest with AES-256
- **Backups**: All backups are encrypted automatically
- **Sensitive Fields**: Manually encrypt additional sensitive data if needed

```python
from cryptography.fernet import Fernet

def encrypt_field(data: str, encryption_key: str):
    cipher = Fernet(encryption_key)
    return cipher.encrypt(data.encode())

def decrypt_field(encrypted_data: bytes, encryption_key: str):
    cipher = Fernet(encryption_key)
    return cipher.decrypt(encrypted_data).decode()
```

### Encryption in Transit

- **HTTPS**: All production connections use TLS 1.2+
- **WebSocket**: WSS (WebSocket Secure) for real-time connections
- **API Keys**: Never transmitted in URLs; use Authorization headers

**Local Development**:
```python
# Use HTTP locally with self-signed certs
# In production, TLS is enforced
ENVIRONMENT = "development"
SECURE_COOKIES = False  # Local only
```

**Production Configuration**:
```python
ENVIRONMENT = "production"
SECURE_COOKIES = True
HTTPS_ONLY = True
TLS_VERSION = "1.2"
```

## Secrets Management

### Environment Variables

**Never commit secrets**:

```bash
# ❌ WRONG - Don't commit!
OPENAI_API_KEY=sk-abc123xyz789
DATABASE_PASSWORD=mysecretpassword123

# ✅ RIGHT - Use .env files (add to .gitignore)
# .env (never commit)
OPENAI_API_KEY=sk-abc123xyz789

# ✅ RIGHT - Use deployment secrets
# GitHub Secrets, Vercel Secrets, etc.
```

**`.gitignore` Configuration**:
```
# Secrets
.env
.env.local
.env.*.local
*.pem
*.key
```

### Secrets Rotation

When secrets are compromised:

```bash
# 1. Generate new secret
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Update in all environments
# - Update .env.example (without actual secret)
# - Update deployment platform secrets
# - Notify team

# 3. Document rotation
# Add entry to SECURITY_LOG.md with:
# - Date of rotation
# - Which secret was rotated
# - Reason (if compromised)
# - Who performed rotation
```

## API Security

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(credentials: LoginRequest, request: Request):
    """Max 5 login attempts per minute per IP"""
    # Implementation
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Specific in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)
```

### Input Validation

```python
from pydantic import BaseModel, EmailStr, Field

class CreateCampaignRequest(BaseModel):
    campaign_name: str = Field(..., min_length=1, max_length=255)
    business_goal: str = Field(..., min_length=10, max_length=1000)
    budget_total: float = Field(..., gt=0, le=1000000)
    email: EmailStr  # Validates email format
    
    class Config:
        # Prevent arbitrary field injection
        extra = "forbid"

@router.post("/campaigns")
async def create_campaign(data: CreateCampaignRequest):
    # Pydantic validates automatically
    return await campaign_service.create(data)
```

### SQL Injection Prevention

```python
# ✅ SAFE - Use parameterized queries
result = await db.raw_query(
    "SELECT * FROM campaigns WHERE id = ? AND user_id = ?",
    [campaign_id, user_id]
)

# ❌ DANGEROUS - String interpolation
query = f"SELECT * FROM campaigns WHERE id = '{campaign_id}'"
result = await db.raw_query(query)  # Vulnerable!
```

### XSS Prevention

```typescript
// ✅ SAFE - React escapes by default
<div>{userInput}</div>

// ✅ SAFE - DOMPurify for HTML content
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(userInput)}} />

// ❌ DANGEROUS - Unescaped content
<div dangerouslySetInnerHTML={{__html: userInput}} />
```

## Logging & Monitoring

### Sensitive Data in Logs

```python
import logging
import json

logger = logging.getLogger(__name__)

def log_request(request_data):
    """Log request without exposing secrets"""
    safe_data = request_data.copy()
    
    # Remove sensitive fields
    sensitive_fields = ['password', 'token', 'api_key', 'secret']
    for field in sensitive_fields:
        if field in safe_data:
            safe_data[field] = '***REDACTED***'
    
    logger.info(f"Request: {json.dumps(safe_data)}")
```

### Error Messages

```python
# ✅ User-safe error message
raise HTTPException(
    status_code=401,
    detail="Invalid credentials"
)

# ❌ Expose too much information
raise HTTPException(
    status_code=401,
    detail="User not found in database - Query failed on table users"
)
```

## WebSocket Security

### Connection Authentication

```python
@router.websocket("/ws/campaigns/{campaign_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...)
):
    # Authenticate before accepting connection
    try:
        user = verify_jwt_token(token)
    except InvalidTokenError:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # Verify campaign ownership
    campaign = await db.get_campaign(campaign_id)
    if campaign.user_id != user.id:
        await websocket.close(code=4003, reason="Forbidden")
        return
    
    await websocket.accept()
```

## Database Security

### Connection String

```python
# ✅ USE environment variable
DATABASE_URL = os.getenv("DATABASE_URL")
db = create_connection(DATABASE_URL)

# ❌ Never hardcode
DATABASE_URL = "postgresql://user:password@localhost/db"
```

### Backup Security

```bash
# ✅ Encrypted backup
pg_dump $DATABASE_URL | gpg --encrypt > backup.sql.gpg

# Restore from encrypted backup
gpg --decrypt backup.sql.gpg | psql $DATABASE_URL
```

## Dependency Management

### Vulnerability Scanning

```bash
# Check Python dependencies for vulnerabilities
pip install safety
safety check

# Check npm dependencies
npm audit
npm audit fix  # Auto-fix available issues

# Check lock file integrity
pnpm audit
```

### Dependency Pinning

```toml
# ✅ Pin exact versions in production
[project]
dependencies = [
    "fastapi==0.111.0",
    "pydantic==2.7.1",
]

# ⚠️ Be more flexible in development
# But test before deploying updates
```

## Access Control

### Environment Access

| Environment | Access Level | Who | MFA Required |
|------------|--------------|-----|--------------|
| Development | Full | All devs | No |
| Staging | Full | Core team | Yes |
| Production | Limited | DevOps/Ops | **Yes** |

### Code Review Requirements

- **All PRs** require 2 approvals before merging
- **Security changes** (auth, secrets, encryption) require security team review
- **Production changes** require deployment approval

## Incident Response

### Security Incident Process

1. **Detect**: Monitor logs and alerts for suspicious activity
2. **Assess**: Determine severity and scope of incident
3. **Contain**: Limit damage (revoke tokens, block IPs, etc.)
4. **Remediate**: Fix root cause
5. **Communicate**: Notify affected users if needed
6. **Document**: Post-incident review and improvements

### Security Contact

For reporting security issues:
- **Email**: security@company.com
- **GitHub**: [Security advisories](https://github.com/your-org/repo/security/advisories)
- **Do NOT** open public GitHub issues for security vulnerabilities

## Compliance

### Data Retention

- **User data**: Retained for account lifetime
- **Campaign data**: Retained for 7 years for audit purposes
- **Logs**: Retained for 90 days
- **Backups**: Retained for 30 days

### GDPR Compliance

```python
# Data export (right to be forgotten)
async def export_user_data(user_id: str):
    """Export all user data in standard format"""
    user = await db.get_user(user_id)
    campaigns = await db.get_user_campaigns(user_id)
    return {
        "user": user.dict(),
        "campaigns": [c.dict() for c in campaigns]
    }

async def delete_user_data(user_id: str):
    """Delete all user data (anonymization)"""
    await db.delete_user_campaigns(user_id)
    await db.delete_user(user_id)
```

## Security Checklist for Contributors

Before submitting a PR:

- [ ] No secrets committed (.env, API keys, etc.)
- [ ] All inputs validated with Pydantic/TypeScript
- [ ] Authentication checks on all protected endpoints
- [ ] Authorization verified (user can only access their data)
- [ ] Sensitive data not logged
- [ ] Error messages don't expose system details
- [ ] SQL queries use parameterized statements
- [ ] XSS prevention for dynamic content
- [ ] CSRF tokens used for state-changing operations
- [ ] Rate limiting appropriate for endpoint
- [ ] Dependencies scanned for vulnerabilities
- [ ] Security tests included in test suite

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Pydantic Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

**Related Documentation**:
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow
- [TESTING.md](TESTING.md) - Security testing

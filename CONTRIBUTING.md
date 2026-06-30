# Contributing Guide

## Getting Started

1. **Read the docs**: Start with [REQUIREMENTS.md](REQUIREMENTS.md) to understand in-scope features
2. **Setup environment**: Follow [DEVELOPMENT.md](DEVELOPMENT.md) step-by-step
3. **Verify setup**: Run `pnpm test` to ensure everything works

## Workflow

### 1. Create a Feature Branch

```bash
# Update main first
git checkout main
git pull origin main

# Create feature branch with descriptive name
git checkout -b feature/campaign-approval-gates
# or
git checkout -b fix/websocket-reconnection
```

### 2. Implementation

**Scope**: Keep changes focused on one feature or fix
```bash
# ✓ Good: Single responsibility
git checkout -b feature/add-campaign-filters

# ✗ Too broad: Multiple unrelated changes
git checkout -b feature/refactor-everything
```

**Follow the checklist**:
- [ ] Read relevant documentation (SPEC.md, API.md, AGENTS.md)
- [ ] Check DEPENDENCIES.md before starting
- [ ] Implement schema/contracts first (in SPEC.md style)
- [ ] Write tests as you go (TDD preferred)
- [ ] Update documentation if behavior changes

### 3. Testing

**Run all tests before opening PR**:
```bash
pnpm lint         # Check code style
pnpm type-check   # Verify types
pnpm test         # Run all tests
pnpm test:e2e     # Run end-to-end tests
```

**Test coverage**:
- New code should have 80%+ coverage
- Critical paths should have dedicated tests
- Include both happy path and error cases

### 4. Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Scope**: `api`, `web`, `agents`, `database`, `websocket`, etc.

**Examples**:
```
feat(campaigns): add campaign filtering by status

Added support for filtering campaigns by status on dashboard.
Implements GET /campaigns?status=active|completed|draft

Fixes #123
```

```
fix(websocket): improve reconnection backoff

Implement exponential backoff for WebSocket reconnection
to prevent connection storms. Caps retry attempts at 5.

Closes #456
```

### 5. Pull Request Process

**Before opening PR, ensure**:
- ✅ All tests pass: `pnpm test`
- ✅ No type errors: `pnpm type-check`
- ✅ Code formatted: `pnpm format`
- ✅ Branch updated: `git pull origin main`
- ✅ Related tests added/updated
- ✅ Documentation updated

**PR Description Template**:
```markdown
## Problem
What issue does this PR solve?

## Solution
What approach did you take?

## Changes
- Implementation detail 1
- Implementation detail 2
- Implementation detail 3

## Testing
How did you test this?

```bash
pnpm test -- --grep "specific test"
```

Output:
```
✓ test passed
```

## Checklist
- [ ] Tests pass (`pnpm test`)
- [ ] Types check (`pnpm type-check`)
- [ ] Code formatted (`pnpm format`)
- [ ] Documentation updated
- [ ] Follows SPEC.md contracts
- [ ] No breaking changes (or documented)
```

**Request reviewers**:
- For backend changes: Request one backend team member
- For frontend changes: Request one frontend team member
- For cross-cutting changes: Request both

**Merging**:
- Requires 2 approvals for all PRs
- All CI checks must pass
- Squash commits before merging (use GitHub's option)
- Delete branch after merging

## Development Standards

### Code Style

**Backend (Python)**:
- Black formatter (via Ruff)
- 100 character line length
- Type hints required
- Docstrings for public functions

```python
async def get_campaign(campaign_id: str, user_id: str) -> Optional[Campaign]:
    """
    Retrieve a campaign by ID, verifying user ownership.
    
    Args:
        campaign_id: UUID of the campaign
        user_id: UUID of requesting user
    
    Returns:
        Campaign object if found and user owns it, None otherwise
    
    Raises:
        PermissionError: If user doesn't own campaign
    """
    campaign = await db.get_campaign(campaign_id)
    if campaign.user_id != user_id:
        raise PermissionError("User does not own this campaign")
    return campaign
```

**Frontend (TypeScript)**:
- ESLint + Prettier
- TypeScript strict mode
- Consistent naming conventions

```typescript
// ✓ Good: Clear naming, types, JSDoc
export interface CampaignFilters {
  status?: 'active' | 'draft' | 'completed';
  createdAfter?: Date;
  limit?: number;
}

/**
 * Fetch campaigns with optional filters
 * @param filters - Campaign filter options
 * @returns Array of campaigns matching filters
 */
export async function getCampaigns(
  filters?: CampaignFilters
): Promise<Campaign[]> {
  // Implementation
}
```

### API Error Handling

All API errors must use consistent envelope:

```python
# ✓ Correct format
{
  "error": {
    "code": "CAMPAIGN_NOT_FOUND",
    "message": "Campaign with ID xyz not found",
    "status": 404,
    "timestamp": "2026-06-29T10:00:00Z"
  }
}

# ✓ Validation errors
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {"field": "budget_total", "message": "Must be greater than 0"}
    ]
  }
}
```

### Database Changes

**Always create migrations**:
```bash
# Create new migration
touch backend/packages/database/supabase/migrations/NNN_description.sql

# Fill with SQL changes
# Test locally
psql $DATABASE_URL < migration.sql

# Document in migration
-- Migration: Add budget_approved column to campaigns
-- Date: 2026-06-29
-- Risk: Low - additive change, backward compatible
```

### Agent Node Implementation

Correct pattern:
```python
# ✓ Async function directly
async def planner_node(state: OrchestrationState) -> OrchestrationState:
    agent = PlannerAgent()
    result = await agent.plan(state.brief)
    state.strategy = result
    return state

# ✗ WRONG: Lambda wrapping async
async def planner_node_wrong(state):
    return lambda: await agent.plan(...)
```

## Code Review Guidelines

**When reviewing PRs**:

**Check for**:
- ✅ Follows code style
- ✅ Tests are adequate
- ✅ No security issues
- ✅ Doesn't break existing APIs
- ✅ Documentation is updated
- ✅ Changes are scoped properly

**Comment constructively**:
```
# ✓ Good
"Consider using `filter()` instead of looping here for clarity"

# ✗ Not helpful
"This is wrong"
```

**Approve when ready**:
- Click "Approve" if PR meets all criteria
- Click "Request changes" if issues must be fixed
- Use "Comment" for non-blocking suggestions

## Security Requirements

**Before submitting any PR**:
- [ ] No secrets in code (.env, API keys)
- [ ] No credentials in git history
- [ ] Input validation on all endpoints
- [ ] Authorization checks present
- [ ] Error messages don't expose internals
- [ ] Dependencies scanned for vulnerabilities

See [SECURITY.md](SECURITY.md) for full checklist.

## Documentation Requirements

**Update docs if you change**:
- API endpoints → Update [API.md](API.md)
- Database schema → Update [DATABASE.md](DATABASE.md)
- Agent behavior → Update [AGENTS.md](AGENTS.md)
- WebSocket events → Update [WEBSOCKET.md](WEBSOCKET.md)
- Setup process → Update [DEVELOPMENT.md](DEVELOPMENT.md)

**Format**:
- Use Markdown
- Include code examples
- Add before/after comparisons for behavioral changes
- Keep line length under 100 characters

## Release Process

**Before release**:
1. Update version in `package.json`
2. Update [CHANGELOG.md](CHANGELOG.md) (create if needed)
3. Tag commit: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. Create GitHub release with release notes

## Questions?

- **Setup issues**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Common problems**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Architecture questions**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Security concerns**: See [SECURITY.md](SECURITY.md)
- **How things work**: Check relevant documentation or ask in GitHub Discussions

## Code of Conduct

- Be respectful and professional
- Assume good intent
- Help others learn
- Report issues to maintainers privately
- Celebrate wins and help each other grow

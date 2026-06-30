# System Setup & Running Guide

## Prerequisites Installation

### 1. Agents Package (REQUIRED for backend)

The backend API needs the agents package installed to import the LangGraph orchestrator.

```powershell
cd d:\P2-K\autonomous-campaign-manager\backend\packages\agents
pip install -e .
```

**Why `-e` flag?**
- `-e` = "editable mode"
- Changes to code take effect immediately without reinstalling
- Required for local development

---

## Running the Full System

### Terminal 1: Backend API

```powershell
cd d:\P2-K\autonomous-campaign-manager\backend\apps\api
.\.venv\Scripts\Activate.ps1
python main.py
```

Runs on: **http://localhost:8000**

OpenAPI docs: **http://localhost:8000/docs**

### Terminal 2: Frontend

```powershell
cd d:\P2-K\autonomous-campaign-manager\frontend\apps\web
pnpm dev
```

Runs on: **http://localhost:3000**

---

## Features & Workflows

### Campaigns Dashboard

**URL:** http://localhost:3000/campaigns/dashboard

1. **View Campaigns:**
   - Click any campaign row to view details
   - Dashboard shows: Active, Completed, and Pending Approval

2. **Create New Campaign:**
   - Click "Create New Campaign" button
   - Follow the workflow setup wizard

3. **Approve Campaign:**
   - Campaigns waiting for approval show "Human Approval Required" card
   - Click "Review Approval Request"
   - Approve or reject with feedback

---

## Environment Variables

### Backend (`backend/apps/api/.env`)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
API_SECRET_KEY=your-secret-key
AMZUR_API_KEY=your-api-key
FRONTEND_URL=http://localhost:3000
```

### Frontend (`frontend/apps/web/.env.local`)

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## API Endpoints Reference

### Campaigns

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/campaigns` | Create new campaign |
| GET | `/api/v1/campaigns` | List all campaigns |
| GET | `/api/v1/campaigns/{id}` | Get campaign details |
| GET | `/api/v1/campaigns/{id}/status` | Get real-time status |
| POST | `/api/v1/campaigns/{id}/approve` | Approve/reject campaign |
| GET | `/api/v1/campaigns/{id}/report` | Get final report |

### Authentication

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login user |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/password/forgot` | Request password reset |
| POST | `/api/v1/auth/password/reset` | Reset password |

---

## Troubleshooting

### Campaigns not appearing in dashboard

1. Check backend is running: http://localhost:8000/health
2. Check authentication token is valid
3. Check browser console for errors
4. Verify Supabase connection in backend logs

### Approval button is grayed out

1. Campaign must have `status: awaiting_strategy_approval` or `awaiting_budget_approval`
2. Create a test campaign and trigger approval workflow
3. Check backend logs for approval state updates

### WebSocket disconnection

1. Ensure both frontend and backend are running
2. Check browser console network tab
3. Verify `NEXT_PUBLIC_API_URL` is correct

---

## Development Tips

- Backend auto-reloads on code changes (watch mode enabled)
- Frontend auto-reloads on code changes (Next.js dev server)
- Use `http://localhost:8000/docs` for API testing
- Check browser DevTools > Network for API calls
- Check backend logs for detailed error messages

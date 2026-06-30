# WebSocket Events & Real-Time Streaming

## Overview

The Autonomous Campaign Manager uses WebSocket for real-time campaign event streaming. Connected clients receive live updates as campaigns progress through orchestration stages, approval gates, and completion.

## Connection

### Establishing Connection

```typescript
// Client-side connection
const socket = new WebSocket(
  `ws://localhost:8000/ws/campaigns/${campaignId}`,
  ['Authorization', `Bearer ${token}`]
);

socket.onopen = () => {
  console.log('Connected to campaign stream');
};

socket.onmessage = (event) => {
  const agentEvent = JSON.parse(event.data);
  handleCampaignEvent(agentEvent);
};

socket.onerror = (error) => {
  console.error('WebSocket error:', error);
};

socket.onclose = () => {
  console.log('Disconnected from campaign stream');
};
```

### Backend Endpoint

```python
# backend/apps/api/app/routers/ws_campaigns.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

@router.websocket("/ws/campaigns/{campaign_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...)
):
    """WebSocket endpoint for campaign event streaming"""
    
    # Authenticate user
    try:
        user = verify_jwt_token(token)
    except InvalidTokenError:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    # Verify campaign ownership
    campaign = await get_campaign(campaign_id, user.id)
    if not campaign:
        await websocket.close(code=1008, reason="Campaign not found")
        return
    
    # Accept connection
    await websocket.accept()
    
    try:
        # Subscribe to campaign events
        async for event in subscribe_to_campaign_events(campaign_id):
            await websocket.send_json(event)
    
    except WebSocketDisconnect:
        print(f"Client disconnected from {campaign_id}")
```

## Event Types

### Core Event Structure

```typescript
interface AgentEvent {
  // Unique identifiers
  event_id: string;            // UUID
  campaign_id: string;         // Campaign UUID
  campaign_run_id: string;     // Run UUID
  
  // Event classification
  event_type: string;
  agent_name?: string;        // e.g., "planner", "content_creator"
  
  // Timing
  timestamp: string;          // ISO-8601
  duration_ms?: number;       // Processing time
  
  // Payload
  payload: Record<string, any>;
  error?: {
    code: string;
    message: string;
  };
  
  // Metadata
  retry_count?: number;
  source: "orchestrator" | "api";
}
```

### Event Types & Payloads

#### 1. Workflow Started

```json
{
  "event_type": "workflow_started",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T10:30:00Z",
  "payload": {
    "campaign_name": "Summer Sale 2026",
    "total_stages": 5
  }
}
```

#### 2. Agent Started

```json
{
  "event_type": "agent_started",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "agent_name": "planner",
  "timestamp": "2026-06-29T10:30:05Z",
  "payload": {
    "stage": 1,
    "agent_id": "planner-instance-1"
  }
}
```

#### 3. Agent Completed

```json
{
  "event_type": "agent_completed",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "agent_name": "planner",
  "timestamp": "2026-06-29T10:35:00Z",
  "duration_ms": 295000,
  "payload": {
    "stage": 1,
    "output_summary": {
      "strategy_positioning": "Premium brand targeting urban professionals",
      "channels_recommended": 3,
      "kpi_targets": {
        "impressions": 250000,
        "ctr": 0.08,
        "conversions": 1500
      }
    }
  }
}
```

#### 4. Approval Required

```json
{
  "event_type": "approval_required",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T10:35:01Z",
  "payload": {
    "gate": "strategy",
    "approval_id": "approval-uuid",
    "expires_in_minutes": 1440,
    "content_for_review": {
      "strategy_summary": "Proposed strategy focuses on 3 channels...",
      "estimated_reach": 500000,
      "proposed_timeline": "4 weeks",
      "key_messages": [...]
    }
  }
}
```

#### 5. Approval Received

```json
{
  "event_type": "approval_received",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T11:00:00Z",
  "payload": {
    "gate": "strategy",
    "approval_id": "approval-uuid",
    "approved": true,
    "reviewer_id": "user-uuid",
    "reviewer_name": "Jane Smith",
    "comments": "Strategy looks solid, proceeding to content creation",
    "next_stage": "content_creator"
  }
}
```

#### 6. Approval Rejected

```json
{
  "event_type": "approval_received",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T11:30:00Z",
  "payload": {
    "gate": "strategy",
    "approval_id": "approval-uuid",
    "approved": false,
    "reviewer_id": "user-uuid",
    "reviewer_name": "John Doe",
    "comments": "Budget needs adjustment. Please revisit strategy.",
    "action": "rollback_to_planner"
  }
}
```

#### 7. Stage Transition

```json
{
  "event_type": "stage_transition",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T11:00:05Z",
  "payload": {
    "from_stage": "planner",
    "to_stage": "content_creator",
    "reason": "Strategy approved",
    "state_checkpoint": "..."
  }
}
```

#### 8. Workflow Completed

```json
{
  "event_type": "workflow_completed",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T13:45:00Z",
  "duration_ms": 12600000,
  "payload": {
    "total_stages_executed": 5,
    "report_id": "report-uuid",
    "summary": "Campaign orchestration completed successfully",
    "status": "success",
    "metrics": {
      "execution_time": "3.5 hours",
      "approvals_required": 2,
      "approvals_received": 2
    }
  }
}
```

#### 9. Workflow Failed

```json
{
  "event_type": "workflow_failed",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T10:45:00Z",
  "payload": {
    "failed_stage": "content_creator",
    "error_code": "CONTENT_GENERATION_FAILED",
    "error_message": "Failed to generate creative assets after 3 retries",
    "retry_count": 3,
    "action": "manual_intervention_required"
  }
}
```

#### 10. Status Update

```json
{
  "event_type": "status_update",
  "campaign_id": "campaign-uuid",
  "campaign_run_id": "run-uuid",
  "timestamp": "2026-06-29T10:40:00Z",
  "payload": {
    "current_stage": "content_creator",
    "progress_percent": 40,
    "status_message": "Generating 12 creative asset variants...",
    "estimated_time_remaining_seconds": 120
  }
}
```

## Client-Side Handling

### React Hook Pattern

```typescript
// frontend/apps/web/src/hooks/useCampaignEvents.ts
import { useEffect, useState, useCallback } from 'react';
import { AgentEvent } from '@acm/types';

export function useCampaignEvents(campaignId: string, authToken: string) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(
      `ws://localhost:8000/ws/campaigns/${campaignId}?token=${authToken}`
    );

    socket.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    socket.onmessage = (event) => {
      try {
        const agentEvent = JSON.parse(event.data) as AgentEvent;
        setEvents(prev => [agentEvent, ...prev]);
      } catch (err) {
        setError('Failed to parse event');
      }
    };

    socket.onerror = () => {
      setError('WebSocket connection error');
      setIsConnected(false);
    };

    socket.onclose = () => {
      setIsConnected(false);
    };

    socketRef.current = socket;

    return () => {
      socket.close();
    };
  }, [campaignId, authToken]);

  return { events, isConnected, error };
}
```

### Event Timeline Component

```typescript
// frontend/apps/web/src/components/EventTimeline.tsx
import { AgentEvent } from '@acm/types';
import { format } from 'date-fns';

interface EventTimelineProps {
  events: AgentEvent[];
  isLive: boolean;
}

export function EventTimeline({ events, isLive }: EventTimelineProps) {
  const getEventIcon = (eventType: string, agentName?: string) => {
    switch (eventType) {
      case 'workflow_started':
        return '🚀';
      case 'agent_started':
        return '⚙️';
      case 'agent_completed':
        return '✅';
      case 'approval_required':
        return '👤';
      case 'approval_received':
        return '👍';
      case 'workflow_completed':
        return '🎉';
      case 'workflow_failed':
        return '❌';
      default:
        return '📍';
    }
  };

  return (
    <div className="event-timeline">
      {events.map((event) => (
        <div key={event.event_id} className="event-item">
          <div className="event-icon">
            {getEventIcon(event.event_type, event.agent_name)}
          </div>
          
          <div className="event-content">
            <h4>{event.event_type}</h4>
            {event.agent_name && <p className="agent">Agent: {event.agent_name}</p>}
            
            <p className="timestamp">
              {format(new Date(event.timestamp), 'HH:mm:ss')}
            </p>
            
            {event.duration_ms && (
              <p className="duration">
                Duration: {(event.duration_ms / 1000).toFixed(1)}s
              </p>
            )}
            
            {event.error && (
              <div className="error">
                <strong>{event.error.code}:</strong> {event.error.message}
              </div>
            )}
          </div>
        </div>
      ))}
      
      {isLive && <div className="live-indicator">🔴 Live</div>}
    </div>
  );
}
```

### Handling Specific Events

```typescript
// frontend/apps/web/src/hooks/useCampaignOrchestration.ts
import { AgentEvent } from '@acm/types';
import { useState, useCallback } from 'react';

export function useCampaignOrchestration(campaignId: string) {
  const [approvalGate, setApprovalGate] = useState<AgentEvent | null>(null);
  const [completionData, setCompletionData] = useState<AgentEvent | null>(null);

  const handleEvent = useCallback((event: AgentEvent) => {
    if (event.event_type === 'approval_required') {
      // Show approval interface
      setApprovalGate(event);
    } else if (event.event_type === 'workflow_completed') {
      // Show completion summary
      setCompletionData(event);
    } else if (event.event_type === 'workflow_failed') {
      // Show error and recovery options
      showErrorNotification(event.payload.error_message);
    }
  }, []);

  return { approvalGate, completionData, handleEvent };
}
```

## Server-Side Broadcasting

### Event Publisher

```python
# backend/apps/api/app/services/event_service.py
from typing import Set, Dict, List
import json

class EventBroadcaster:
    """Manages WebSocket connections and broadcasts events"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set] = {}  # campaign_id -> set of websockets
    
    async def connect(self, campaign_id: str, websocket: WebSocket):
        """Register a new WebSocket connection"""
        await websocket.accept()
        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = set()
        self.active_connections[campaign_id].add(websocket)
    
    async def disconnect(self, campaign_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        self.active_connections[campaign_id].discard(websocket)
    
    async def broadcast_event(self, campaign_id: str, event: AgentEvent):
        """Send event to all connected clients for a campaign"""
        if campaign_id not in self.active_connections:
            return
        
        event_json = json.dumps(event.dict(), default=str)
        dead_connections = set()
        
        for websocket in self.active_connections[campaign_id]:
            try:
                await websocket.send_text(event_json)
            except ConnectionClosedError:
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect(campaign_id, ws)

# Global broadcaster instance
broadcaster = EventBroadcaster()

# Usage in orchestrator
async def emit_orchestrator_event(campaign_id: str, event: AgentEvent):
    """Emit event from orchestrator"""
    await broadcaster.broadcast_event(campaign_id, event)
```

## Reconnection & Resilience

### Client-Side Reconnection

```typescript
// frontend/apps/web/src/hooks/useReconnectingWebSocket.ts
export function useReconnectingWebSocket(
  url: string,
  onMessage: (data: any) => void
) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const attemptsRef = useRef(0);
  const maxAttemptsRef = useRef(5);
  const socketRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const socket = new WebSocket(url);

    socket.onopen = () => {
      setStatus('connected');
      attemptsRef.current = 0; // Reset on successful connection
    };

    socket.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };

    socket.onclose = () => {
      setStatus('disconnected');
      
      // Attempt to reconnect with exponential backoff
      if (attemptsRef.current < maxAttemptsRef.current) {
        const delay = Math.pow(2, attemptsRef.current) * 1000;
        attemptsRef.current++;
        
        setTimeout(() => {
          setStatus('connecting');
          connect();
        }, delay);
      }
    };

    socketRef.current = socket;
  }, [url, onMessage]);

  useEffect(() => {
    connect();
    return () => socketRef.current?.close();
  }, [connect]);

  return { status, socket: socketRef.current };
}
```

### Server-Side Heartbeat

```python
# backend/apps/api/app/routers/ws_campaigns.py
import asyncio

@router.websocket("/ws/campaigns/{campaign_id}")
async def websocket_endpoint(websocket: WebSocket, campaign_id: str):
    await broadcaster.connect(campaign_id, websocket)
    
    heartbeat_task = asyncio.create_task(
        send_heartbeat(websocket, interval=30)
    )
    
    try:
        while True:
            # Listen for client messages (pings)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await broadcaster.disconnect(campaign_id, websocket)
    finally:
        heartbeat_task.cancel()

async def send_heartbeat(websocket: WebSocket, interval: int):
    """Send periodic heartbeat to keep connection alive"""
    while True:
        try:
            await asyncio.sleep(interval)
            await websocket.send_json({
                "event_type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            })
        except ConnectionClosedError:
            break
```

## Performance Considerations

### Message Throttling

```typescript
// Throttle events to prevent UI thrashing
function throttleEvents(events: AgentEvent[], interval: number = 1000) {
  let lastBatchTime = 0;
  let pending: AgentEvent[] = [];

  return (event: AgentEvent) => {
    pending.push(event);
    const now = Date.now();

    if (now - lastBatchTime >= interval) {
      setEvents(prev => [...pending, ...prev]);
      pending = [];
      lastBatchTime = now;
    }
  };
}
```

### Event Persistence

```python
# Persist events for replay/debugging
async def persist_event(event: AgentEvent):
    """Store event in database for audit trail"""
    await db.table('events').insert({
        'campaign_id': event.campaign_id,
        'event_type': event.event_type,
        'agent_name': event.agent_name,
        'payload_json': event.payload,
        'created_at': datetime.utcnow()
    })
```

---

**Related Documentation**:
- [API.md](API.md) - REST API documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [DATABASE.md](DATABASE.md) - Event table schema

# TrafficCopilot — Frontend API Reference

**Base URL:** `http://localhost:8000`
**WebSocket:** `ws://localhost:8000/ws/{incident_id}`
**All requests/responses:** `application/json` unless noted
**Auth:** None (officer_id is passed in body)

---

## Table of Contents

1. [Health](#1-health)
2. [Incidents](#2-incidents)
3. [Recommendations](#3-recommendations)
4. [Alerts](#4-alerts)
5. [Chat (AI Copilot)](#5-chat-ai-copilot)
6. [Vision / Image Upload](#6-vision--image-upload)
7. [Map Data (GeoJSON)](#7-map-data-geojson)
8. [WebSocket — Live Updates](#8-websocket--live-updates)
9. [Complete Flow: Incident → SMS](#9-complete-flow-incident--sms)
10. [Map Rendering Guide (Leaflet / Mapbox)](#10-map-rendering-guide-leaflet--mapbox)
11. [WebSocket Integration Guide](#11-websocket-integration-guide)
12. [Severity & Status Reference](#12-severity--status-reference)
13. [Error Handling](#13-error-handling)

---

## 1. Health

### `GET /health`
Basic liveness check.

**Response `200`**
```json
{ "status": "ok", "environment": "development" }
```

### `GET /health/ready`
Readiness — confirms DB, Redis, Kafka, OSM graph are all up.

**Response `200`**
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "kafka": "ok",
    "osm_graph": "ok"
  }
}
```

---

## 2. Incidents

### `POST /incidents/`
Manually create an incident (officer report).

**Request Body**
```json
{
  "severity": "critical",
  "description": "Multi-vehicle pile-up on SP Ring Road near Bopal Circle",
  "lat": 23.0607,
  "lon": 72.5169,
  "corridor_id": "AMD-SPRR-01",
  "detection_confidence": 0.9,
  "reporter_id": "officer_badge_42"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `severity` | `"low"` \| `"medium"` \| `"high"` \| `"critical"` | ✅ | |
| `description` | string (1–2000 chars) | ✅ | |
| `lat` | float (-90 to 90) | ❌ | WGS-84 |
| `lon` | float (-180 to 180) | ❌ | WGS-84 |
| `corridor_id` | string | ❌ | e.g. `"AMD-CGR-01"` |
| `detection_confidence` | float (0–1) | ❌ | Default `0.9` |
| `reporter_id` | string | ❌ | Default `"manual"` |

**Response `201` — `IncidentOut`**
```json
{
  "id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "status": "active",
  "severity": "critical",
  "description": "Pedestrian fatality at CG Road / Swastik Cross Roads",
  "location_lat": 23.0269,
  "location_lon": 72.5855,
  "corridor_id": "AMD-CGR-01",
  "reporter_id": "officer_badge_42",
  "created_at": "2026-03-21T20:05:28.900584Z",
  "updated_at": "2026-03-21T20:05:28.900584Z",
  "detection_confidence": 0.92
}
```

> Creating an incident also publishes a `ManualIncidentEvent` to Kafka, which triggers the AI copilot to generate a recommendation asynchronously (~5–30 seconds depending on Groq rate limits).

---

### `GET /incidents/?limit=20&status=active&severity=critical`
List incidents with optional filters.

**Query Params**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Pagination |
| `status` | string | — | Filter by status |
| `severity` | string | — | Filter by severity |
| `corridor_id` | string | — | Filter by corridor |

**Response `200` — `IncidentOut[]`**
```json
[
  {
    "id": "d97b950c-4da5-4f18-95f9-65da1d411778",
    "status": "active",
    "severity": "critical",
    "description": "Pedestrian fatality at CG Road...",
    "location_lat": 23.0269,
    "location_lon": 72.5855,
    "corridor_id": "AMD-CGR-01",
    "reporter_id": "seed_demo",
    "created_at": "2026-03-21T20:05:28.900584Z",
    "updated_at": "2026-03-21T20:08:18.235447Z",
    "detection_confidence": 0.92
  }
]
```

---

### `GET /incidents/{incident_id}`
Get full incident snapshot — includes affected road segments.

**Response `200` — `IncidentSnapshot`**
```json
{
  "incident": {
    "id": "d97b950c-4da5-4f18-95f9-65da1d411778",
    "status": "active",
    "severity": "critical",
    "description": "Pedestrian fatality at CG Road / Swastik Cross Roads...",
    "location_lat": 23.0269,
    "location_lon": 72.5855,
    "corridor_id": "AMD-CGR-01",
    "reporter_id": "seed_demo",
    "created_at": "2026-03-21T20:05:28.900584Z",
    "updated_at": "2026-03-21T20:08:18.235447Z",
    "detection_confidence": 0.92
  },
  "affected_segments": [
    {
      "osm_way_id": 172932072,
      "delay_seconds": 55,
      "congestion_pct": 75.0
    },
    {
      "osm_way_id": 186029622,
      "delay_seconds": 32,
      "congestion_pct": 48.75
    }
  ],
  "event_count": 4,
  "last_updated": "2026-03-21T20:08:18.235447Z"
}
```

> Use `affected_segments[].osm_way_id` with the OSM tiles API to highlight congested road segments on the map.

---

### `POST /incidents/{incident_id}/events`
Inject a raw sensor/radio event into an existing incident.

**Request Body** — freeform JSON matching any `TrafficEvent` shape:
```json
{
  "event_type": "sensor",
  "source": "speed_sensor",
  "corridor_id": "AMD-CGR-01",
  "speed_kmh": 12.0,
  "free_flow_speed_kmh": 60.0,
  "occupancy_pct": 89.0,
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778"
}
```

**Response `202`**
```json
{ "status": "accepted", "incident_id": "d97b950c-..." }
```

---

## 3. Recommendations

### `GET /recommendations/{incident_id}`
Get all AI recommendations for an incident (newest first).

**Response `200` — `RecommendationOut[]`**
```json
[
  {
    "id": "7b6ad84d-1142-4615-83ac-9ac557e0a8d0",
    "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
    "rec_type": "composite",
    "action": "Critical incident on AMD-CGR-01 at Swastik Cross Roads...",
    "location": null,
    "expected_impact": "Both directions: divert via Navrangpura → C.U. Shah College Road...",
    "evidence_refs": ["SOP-2", "SOP-4", "osm_way=AMD-CGR-01"],
    "confidence": 0.88,
    "blocked_reason": null,
    "review_required": true,
    "status": "pending",
    "created_at": "2026-03-21T20:05:29.000000Z",
    "copilot_response": {
      "incident_summary": "Active critical incident on AMD-CGR-01...",
      "signal_actions": [
        {
          "intersection_id": "AMD-CGR-01-SWASTIK",
          "action": "Extend pedestrian phase by 15s; add leading pedestrian interval (LPI) of 7s",
          "expected_impact": "Reduces pedestrian-vehicle conflicts by ~50%",
          "confidence": 0.90
        },
        {
          "intersection_id": "AMD-CGR-01-NAVRANGPURA",
          "action": "Reduce green phase on CG Road NB by 20s",
          "expected_impact": "Clears emergency vehicle path within 5 min",
          "confidence": 0.82
        }
      ],
      "diversion_plan": {
        "route_description": "Divert via Navrangpura → C.U. Shah College Road → Usmanpura Link Road",
        "estimated_extra_minutes": 6.0,
        "traffic_redistribution_pct": 50.0,
        "confidence": 0.88,
        "evidence_refs": ["SOP-2", "SOP-4"],
        "waypoints": [
          { "name": "Incident — Swastik Cross Roads", "lat": 23.0269, "lng": 72.5855 },
          { "name": "Navrangpura Diversion", "lat": 23.031, "lng": 72.581 },
          { "name": "C.U. Shah College Rd", "lat": 23.035, "lng": 72.576 },
          { "name": "Usmanpura Link", "lat": 23.039, "lng": 72.582 },
          { "name": "Income Tax Re-entry", "lat": 23.042, "lng": 72.587 }
        ]
      },
      "alert_drafts": [
        { "channel": "vms", "message": "FATAL ACCIDENT SWASTIK X-RD. CG RD CLOSED.", "char_count": 42 },
        { "channel": "radio", "message": "CG Road closed at Swastik Cross Roads...", "char_count": 120 },
        { "channel": "social", "message": "CG Road/Swastik closed...", "char_count": 80 }
      ],
      "narrative": "Critical incident on AMD-CGR-01 (CG Road)...",
      "conversational_answer": null,
      "overall_confidence": 0.88,
      "review_required": true,
      "blocked_reason": null,
      "evidence_refs": ["SOP-2", "SOP-4", "osm_way=AMD-CGR-01"],
      "emergency_controls": []
    }
  }
]
```

**`rec_type` values:**
| Value | Meaning |
|-------|---------|
| `composite` | Full AI recommendation (signal + diversion + alerts) |
| `chat` | Response to officer question via `/chat/` |

**`status` lifecycle:** `pending` → `approved` → `executed` / `rejected` / `expired`

---

### `POST /recommendations/{recommendation_id}/approve`
Officer approves a recommendation. Required before alerts can be published.

**Request Body**
```json
{
  "officer_id": "officer_badge_42",
  "note": "Verified — diversion confirmed safe",
  "phone_number": "+918758830100"
}
```

**Response `200` — `ApprovalOut`**
```json
{
  "id": "8ef68ef1-0815-4909-9d3b-7a6087d17580",
  "recommendation_id": "7b6ad84d-1142-4615-83ac-9ac557e0a8d0",
  "officer_id": "officer_badge_42",
  "action": "approved",
  "note": "Verified — diversion confirmed safe",
  "actioned_at": "2026-03-21T20:02:52.399185Z"
}
```

---

### `POST /recommendations/{recommendation_id}/reject`
Officer rejects a recommendation.

**Request Body** — same as approve
**Response `200`** — same `ApprovalOut` shape with `"action": "rejected"`

---

## 4. Alerts

### `GET /alerts/{incident_id}`
Get all alert drafts for an incident.

**Response `200` — `AlertOut[]`**
```json
[
  {
    "id": "cc56df1c-da55-4365-bb1d-05f210ba335c",
    "recommendation_id": "7b6ad84d-1142-4615-83ac-9ac557e0a8d0",
    "channel": "vms",
    "draft_text": "FATAL ACCIDENT SWASTIK X-RD. CG RD CLOSED. USE NAVRANGPURA.",
    "status": "draft",
    "created_at": "2026-03-21T20:05:29.000000Z"
  },
  {
    "id": "babd53ea-c803-497c-8913-2f7f40d9cb66",
    "recommendation_id": "7b6ad84d-1142-4615-83ac-9ac557e0a8d0",
    "channel": "radio",
    "draft_text": "CG Road closed at Swastik Cross Roads following a serious pedestrian incident...",
    "status": "draft",
    "created_at": "2026-03-21T20:05:29.000000Z"
  },
  {
    "id": "3a0e8a57-3e90-47d1-aff5-cc9a850de4e4",
    "recommendation_id": "7b6ad84d-1142-4615-83ac-9ac557e0a8d0",
    "channel": "social",
    "draft_text": "CG Road/Swastik closed — serious incident. Use Navrangpura...",
    "status": "draft",
    "created_at": "2026-03-21T20:05:29.000000Z"
  }
]
```

**`channel` values:** `vms` (variable message sign), `radio`, `social`
**`status` lifecycle:** `draft` → `published` | `rejected`

---

### `POST /alerts/{alert_id}/publish`
Publish a single alert. The linked recommendation must be `approved` first.

**Request Body**
```json
{
  "officer_id": "officer_badge_42",
  "note": "Manually verified message text",
  "phone_number": "+918758830100"
}
```

**Response `200`**
```json
{
  "alert_id": "cc56df1c-da55-4365-bb1d-05f210ba335c",
  "status": "published",
  "channel": "vms",
  "message": "FATAL ACCIDENT SWASTIK X-RD. CG RD CLOSED. USE NAVRANGPURA.",
  "sms": {
    "sent": true,
    "sid": "SMf7b819fb08fb23cc8b4015dbf4cd912a",
    "to": "+918758830100"
  }
}
```

> ⚠️ Will return `400` if `recommendation.status != "approved"`. Always approve the recommendation first.

---

### `POST /alerts/bulk-publish`
Publish multiple alerts at once + one consolidated SMS.

**Request Body**
```json
{
  "alert_ids": [
    "cc56df1c-da55-4365-bb1d-05f210ba335c",
    "babd53ea-c803-497c-8913-2f7f40d9cb66",
    "3a0e8a57-3e90-47d1-aff5-cc9a850de4e4"
  ],
  "officer_id": "officer_badge_42",
  "phone_number": "+918758830100",
  "send_sms": true,
  "sms_recipients": ["+918758830100"]
}
```

**Response `200` — `BulkPublishOut`**
```json
{
  "published_count": 3,
  "skipped_count": 0,
  "error_count": 0,
  "results": [
    { "alert_id": "cc56df1c-...", "status": "published", "channel": "vms", "message": "FATAL ACCIDENT...", "detail": null },
    { "alert_id": "babd53ea-...", "status": "published", "channel": "radio", "message": "CG Road closed...", "detail": null },
    { "alert_id": "3a0e8a57-...", "status": "published", "channel": "social", "message": "CG Road/Swastik closed...", "detail": null }
  ],
  "sms": {
    "sent": true,
    "sid": "SMf7b819fb08fb23cc8b4015dbf4cd912a",
    "to": "+918758830100"
  }
}
```

---

## 5. Chat (AI Copilot)

### `POST /chat/`
Ask the AI copilot a question about an active incident. Returns a recommendation record with `conversational_answer` populated.

**Request Body**
```json
{
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "question": "What alternative route should I take?",
  "officer_id": "officer_badge_42"
}
```

**Response `200` — `RecommendationOut`**
```json
{
  "id": "06fc7ec4-aa60-428e-a61d-f3ef9037e916",
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "rec_type": "chat",
  "action": "What alternative route should I take?",
  "expected_impact": "Divert via Navrangpura → C.U. Shah College Road → Usmanpura Link Road.",
  "confidence": 0.8,
  "blocked_reason": null,
  "review_required": false,
  "status": "pending",
  "created_at": "2026-03-21T20:03:04.524469Z",
  "copilot_response": {
    "incident_summary": "Chat Q&A — intent: action_request",
    "signal_actions": [],
    "diversion_plan": null,
    "alert_drafts": [],
    "narrative": "",
    "conversational_answer": "Divert via Navrangpura → C.U. Shah College Road → Usmanpura Link Road. Avoid CG Road between Swastik and Income Tax Cross Road entirely.",
    "overall_confidence": 0.8,
    "review_required": false,
    "blocked_reason": null,
    "evidence_refs": [],
    "emergency_controls": []
  }
}
```

> The key field to display is `copilot_response.conversational_answer`.
> If `blocked_reason === "llm_unavailable"`, the Groq API is rate-limited — show a retry notice.

**Common questions to ask:**
- `"What alternative route should I take?"`
- `"What signal actions should I take at the nearest intersection?"`
- `"Draft a radio broadcast message for this incident"`
- `"How long will this incident last?"`
- `"What is the estimated delay for commuters?"`

---

## 6. Vision / Image Upload

### `POST /incidents/{incident_id}/vision`
Upload a single image to analyse for incident detection using HuggingFace ViT model.

**Request** — `multipart/form-data`
```
image: <file>           (JPEG/PNG/WebP, max ~10MB)
officer_id: officer_42
```

**Response `200` — `VisionAnalysisOut`**
```json
{
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "incident_detected": true,
  "confidence": 0.72,
  "top_label": "wrecker",
  "scores": {
    "wrecker": 0.72,
    "trailer truck": 0.18,
    "fire engine": 0.06
  },
  "model": "google/vit-base-patch16-224",
  "source": "huggingface",
  "kafka_published": true
}
```

> When `incident_detected: true`, a `CameraMetaEvent` is published to Kafka and the vision confidence is written to Redis at key `vision:{incident_id}`. The next recommendation for this incident will include the vision score in its `overall_confidence` calculation.

---

### `POST /incidents/{incident_id}/vision/bulk`
Upload up to 10 images at once. Best confidence wins and is cached.

**Request** — `multipart/form-data`
```
images: <file1>
images: <file2>
images: <file3>
officer_id: officer_42
```

**Response `200` — `BulkVisionAnalysisOut`**
```json
{
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "total_images": 3,
  "processed": 3,
  "results": [
    { "incident_detected": true, "confidence": 0.72, "top_label": "wrecker", ... },
    { "incident_detected": false, "confidence": 0.04, "top_label": "library", ... },
    { "incident_detected": true, "confidence": 0.81, "top_label": "fire engine", ... }
  ],
  "kafka_published_count": 2,
  "highest_confidence": 0.81
}
```

**Frontend upload example (React):**
```javascript
const formData = new FormData();
files.forEach(f => formData.append("images", f));
formData.append("officer_id", "officer_42");

const res = await fetch(`/incidents/${incidentId}/vision/bulk`, {
  method: "POST",
  body: formData,
});
const data = await res.json();
// data.highest_confidence → show confidence badge
// data.results[i].incident_detected → show detection status per image
```

---

## 7. Map Data (GeoJSON)

### `GET /incidents/{incident_id}/map-data`
Returns a GeoJSON `FeatureCollection` ready to plug directly into Leaflet or Mapbox.

**Response `200`**
```json
{
  "type": "FeatureCollection",
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "corridor_id": "AMD-CGR-01",
  "severity": "critical",
  "status": "active",
  "graph_loaded": true,
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [72.5855, 23.0269]
      },
      "properties": {
        "feature_type": "incident_point",
        "incident_id": "d97b950c-...",
        "severity": "critical",
        "status": "active",
        "corridor_id": "AMD-CGR-01",
        "description": "Pedestrian fatality at CG Road / Swastik Cross Roads...",
        "detection_confidence": 0.92,
        "marker_color": "#ff3333",
        "marker_icon": "warning"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [72.585839, 23.026893],
          [72.584492, 23.027474],
          [72.583155, 23.027630],
          "... 65 more real OSM road nodes ...",
          [72.584611, 23.043155],
          [72.586315, 23.043505]
        ]
      },
      "properties": {
        "feature_type": "diversion_route",
        "source": "osm_waypoint_routing",
        "description": "Both directions: divert via Navrangpura → C.U. Shah College Road → Usmanpura Link Road. Avoid CG Road between Swastik and Income Tax Cross Road entirely.",
        "estimated_extra_minutes": 5.0,
        "traffic_redistribution_pct": 30.0,
        "confidence": 0.88,
        "waypoint_names": [
          "Incident — Swastik Cross Roads",
          "Navrangpura Diversion",
          "C.U. Shah College Rd",
          "Usmanpura Link",
          "Income Tax Re-entry"
        ],
        "road_names": ["Kasturba Gandhi Road"],
        "distance_m": 4561.2,
        "coordinate_count": 68,
        "stroke_color": "#3399ff",
        "stroke_width": 4,
        "stroke_dash": "8,4"
      }
    }
  ],
  "meta": {
    "incident_point": true,
    "affected_segments_count": 108,
    "diversion_source": "osm_waypoint_routing",
    "signal_actions_count": 5
  }
}
```

**`feature_type` values:**

| `feature_type` | Geometry | What it is |
|----------------|----------|------------|
| `incident_point` | `Point` | Exact incident location — place a marker here |
| `diversion_route` | `LineString` | Road-following diversion path (68+ real OSM nodes) — draw as dashed blue line |
| `affected_segment` | `LineString` | Congested OSM road segment — draw as red/orange line |
| `signal_action` | `Point` | Intersection requiring signal change — place a traffic light icon |

**`diversion_route` extra properties:**
| Property | Type | Meaning |
|----------|------|---------|
| `source` | `"osm_waypoint_routing"` \| `"osm_graph"` \| `"llm_waypoints"` | How coordinates were generated |
| `road_names` | `string[]` | Actual road names along the route (e.g. `["Kasturba Gandhi Road"]`) |
| `distance_m` | `float` | Total route length in metres |
| `coordinate_count` | `int` | Number of real OSM road nodes in the LineString |
| `waypoint_names` | `string[]` | Human-readable labels for the 4–6 anchor waypoints |

> When `source === "osm_waypoint_routing"`, coordinates follow real Ahmedabad roads via NetworkX Dijkstra routing — suitable for display directly on OpenStreetMap/Mapbox tiles. When `source === "llm_waypoints"`, only 4–5 straight-line anchor points are available (fallback if graph routing fails).

**`marker_color` by severity:**
| Severity | Color |
|----------|-------|
| `critical` | `#ff3333` |
| `high` | `#ff8800` |
| `medium` | `#ffcc00` |
| `low` | `#33aa33` |

---

## 8. WebSocket — Live Updates

### `WS /ws/{incident_id}`
Subscribe to real-time updates for a specific incident.

**Connect:**
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${incidentId}`);
```

**Message shape — all server messages:**
```json
{
  "event_type": "state_updated",
  "incident_id": "d97b950c-4da5-4f18-95f9-65da1d411778",
  "data": { ... full Kafka payload ... }
}
```

**`event_type` values (exact strings from server):**

| `event_type` | Kafka topic consumed | When fired | `data` contents |
|-------------|---------------------|-----------|-----------------|
| `connected` | — | Immediately on WS connect | `{ "message": "Subscribed to incident {id}" }` |
| `ping` | — | Every 30 seconds | `{}` |
| `state_updated` | `incident.state.updated` | Incident created/updated, sensor event processed, image confidence updated | Full incident snapshot: `{ incident_id, status, severity, detection_confidence, corridor_id, segments, queue_data }` |
| `recommendation_ready` | `recommendation.ready` | Groq LLM finishes generating (~3–8s after state_updated) | `{ incident_id, action, signal_actions, diversion_plan, alert_drafts, confidence, narrative }` |
| `approval_actioned` | `approval.actioned` | Officer approves or rejects a recommendation | `{ incident_id, recommendation_id, officer_id, action: "approved" \| "rejected" }` |

**Client → Server (optional ping):**
```json
{ "event_type": "ping", "incident_id": "d97b950c-..." }
```
Server replies with `{ "event_type": "pong", ... }`.

**Vision upload → WS sequence (confidence >= 0.5):**
```
POST /incidents/{id}/vision
  → HuggingFace ViT analysis (confidence: 0.73)
  → Redis: vision:{incident_id} cached
  → Kafka: traffic.events.raw (CameraMetaEvent)
      → incident_processor: updates detection_confidence in DB
      → Kafka: incident.state.updated
          → WS MSG 1: event_type="state_updated"  ← arrives ~1s after upload
              data.detection_confidence = 0.73
          → copilot_trigger: Groq LLM call (reads vision confidence from Redis)
              → Kafka: recommendation.ready
                  → WS MSG 2: event_type="recommendation_ready"  ← arrives ~5-10s
                      data.confidence = 0.73 (vision score incorporated)
```

---

## 9. Complete Flow: Incident → SMS

This is the exact sequence your frontend should implement:

```
Step 1 — Create or receive incident
  POST /incidents/                     → get incident_id
  (or incident already exists from Kafka feed replay)

Step 2 — Open WebSocket immediately
  WS /ws/{incident_id}                 → subscribe to live updates
  On event_type="state_updated"        → update incident card (severity, confidence badge)
  On event_type="recommendation_ready" → show recommendation panel + redraw map

Step 3 — Show map
  GET /incidents/{incident_id}/map-data → GeoJSON FeatureCollection
  Render:
    incident_point   → red marker at accident location
    affected_segment → orange lines showing congested roads
    diversion_route  → dashed blue line (68 real road coords, follows actual streets)
    signal_action    → yellow traffic light markers at intersections

Step 4 — Fetch recommendations
  GET /incidents/{incident_id}/recommendations → array of RecommendationOut
  Display: narrative, signal_actions[], diversion_plan.route_description,
           diversion_plan.road_names, diversion_plan.distance_m, alert_drafts[]

Step 5 — (Optional) Upload image from scene
  POST /incidents/{incident_id}/vision  (multipart/form-data)
  → VisionAnalysisOut.confidence shown as badge (e.g. "Camera: 73%")
  → triggers WS state_updated then recommendation_ready automatically
  → next recommendation includes vision confidence in overall_confidence

Step 6 — Ask AI copilot
  POST /chat/
  Body: { incident_id, question: "Is it safe to open the southbound lane now?" }
  → copilot_response.conversational_answer shown in chat bubble
  → answer references real diversion data from DB (not generic)

Step 7 — Approve recommendation
  POST /recommendations/{rec_id}/approve
  Body: { officer_id, note }
  → Required before any alert can be published
  → triggers WS event_type="approval_actioned"

Step 8 — Publish all alerts + SMS
  POST /alerts/bulk-publish
  Body: { alert_ids: [...], officer_id: "...", phone_number: "+91..." }
  → VMS / Radio / Social alerts published
  → SMS sends radio alert text (max 130 chars) to officer's phone via Twilio
```

---

## 10. Map Rendering Guide (Leaflet / Mapbox)

### Leaflet.js Example

```javascript
import L from "leaflet";

async function renderIncidentMap(incidentId, mapContainer) {
  // 1. Init map centred on Ahmedabad
  const map = L.map(mapContainer).setView([23.03, 72.58], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

  // 2. Fetch GeoJSON from API
  const res = await fetch(`http://localhost:8000/incidents/${incidentId}/map-data`);
  const geojson = await res.json();

  // 3. Render each feature
  L.geoJSON(geojson, {
    pointToLayer(feature, latlng) {
      const p = feature.properties;
      if (p.feature_type === "incident_point") {
        return L.circleMarker(latlng, {
          radius: 12,
          fillColor: p.marker_color,
          color: "#fff",
          weight: 2,
          fillOpacity: 0.9,
        }).bindPopup(`
          <b>${p.severity.toUpperCase()} — ${p.corridor_id}</b><br>
          ${p.description}<br>
          <small>Confidence: ${(p.detection_confidence * 100).toFixed(0)}%</small>
        `);
      }
      if (p.feature_type === "signal_action") {
        return L.marker(latlng, {
          icon: L.divIcon({ className: "signal-icon", html: "🚦" }),
        }).bindPopup(p.action);
      }
    },
    style(feature) {
      const p = feature.properties;
      if (p.feature_type === "diversion_route") {
        return {
          color: p.stroke_color || "#3399ff",
          weight: p.stroke_width || 4,
          dashArray: p.stroke_dash || "8,4",
          opacity: 0.85,
        };
      }
      if (p.feature_type === "affected_segment") {
        return { color: "#ff4444", weight: 5, opacity: 0.7 };
      }
    },
    onEachFeature(feature, layer) {
      const p = feature.properties;
      if (p.feature_type === "diversion_route") {
        layer.bindPopup(`
          <b>Diversion Route</b><br>
          ${p.description}<br>
          Extra time: +${p.estimated_extra_minutes} min<br>
          Confidence: ${(p.confidence * 100).toFixed(0)}%
        `);
      }
    },
  }).addTo(map);

  // 4. Fit map bounds to all features
  const bounds = geojson.features
    .flatMap(f => {
      const c = f.geometry.coordinates;
      return f.geometry.type === "Point" ? [[c[1], c[0]]] : c.map(p => [p[1], p[0]]);
    });
  if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
}
```

### Mapbox GL JS Example

```javascript
import mapboxgl from "mapbox-gl";

async function renderIncidentMapbox(incidentId, containerId) {
  mapboxgl.accessToken = "YOUR_MAPBOX_TOKEN";

  const map = new mapboxgl.Map({
    container: containerId,
    style: "mapbox://styles/mapbox/dark-v11",
    center: [72.58, 23.03],
    zoom: 13,
  });

  map.on("load", async () => {
    const res = await fetch(`http://localhost:8000/incidents/${incidentId}/map-data`);
    const geojson = await res.json();

    map.addSource("incident-data", { type: "geojson", data: geojson });

    // Diversion route — dashed blue line
    map.addLayer({
      id: "diversion-route",
      type: "line",
      source: "incident-data",
      filter: ["==", ["get", "feature_type"], "diversion_route"],
      paint: {
        "line-color": "#3399ff",
        "line-width": 4,
        "line-dasharray": [2, 1],
        "line-opacity": 0.85,
      },
    });

    // Affected segments — red
    map.addLayer({
      id: "affected-segments",
      type: "line",
      source: "incident-data",
      filter: ["==", ["get", "feature_type"], "affected_segment"],
      paint: { "line-color": "#ff4444", "line-width": 5, "line-opacity": 0.7 },
    });

    // Incident point — pulsing circle
    map.addLayer({
      id: "incident-point",
      type: "circle",
      source: "incident-data",
      filter: ["==", ["get", "feature_type"], "incident_point"],
      paint: {
        "circle-radius": 14,
        "circle-color": ["get", "marker_color"],
        "circle-stroke-width": 3,
        "circle-stroke-color": "#ffffff",
      },
    });

    // Popup on click
    map.on("click", "incident-point", (e) => {
      const p = e.features[0].properties;
      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(`<b>${p.severity.toUpperCase()} — ${p.corridor_id}</b><br>${p.description}`)
        .addTo(map);
    });
  });
}
```

---

## 11. WebSocket Integration Guide

```javascript
class IncidentSocket {
  constructor(incidentId, onMessage) {
    this.incidentId = incidentId;
    this.onMessage = onMessage;
    this.ws = null;
    this.reconnectDelay = 1000;
  }

  connect() {
    this.ws = new WebSocket(`ws://localhost:8000/ws/${this.incidentId}`);

    this.ws.onopen = () => {
      console.log(`[WS] Connected to incident ${this.incidentId}`);
      this.reconnectDelay = 1000; // reset backoff on success
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      switch (msg.event_type) {
        case "connected":
          console.log("[WS] Subscribed:", msg.data.message);
          break;

        case "ping":
          // Server pings every 30s — optionally reply
          this.ws.send(JSON.stringify({ event_type: "ping", incident_id: this.incidentId }));
          break;

        case "incident_update":
          // Incident severity/status changed — refresh incident card
          this.onMessage("incident_update", msg.data);
          break;

        case "recommendation_ready":
          // New AI recommendation — show notification + refresh panel
          this.onMessage("recommendation_ready", msg.data);
          break;

        case "alert_published":
          // Alert went live — update alert status badge
          this.onMessage("alert_published", msg.data);
          break;

        case "segment_update":
          // Congestion changed — update map layer
          this.onMessage("segment_update", msg.data);
          break;
      }
    };

    this.ws.onclose = () => {
      console.warn(`[WS] Disconnected — reconnecting in ${this.reconnectDelay}ms`);
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // exponential backoff, max 30s
    };

    this.ws.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }

  disconnect() {
    if (this.ws) this.ws.close();
  }
}

// Usage
const socket = new IncidentSocket("d97b950c-4da5-4f18-95f9-65da1d411778", (type, data) => {
  if (type === "recommendation_ready") {
    // Re-fetch recommendations and refresh UI
    fetchRecommendations(data.incident_id);
  }
  if (type === "incident_update") {
    updateIncidentCard(data);
  }
});
socket.connect();
```

---

## 12. Severity & Status Reference

### Incident Severity → UI Color
| Severity | Hex | Use |
|----------|-----|-----|
| `critical` | `#ff3333` | Red — immediate officer action required |
| `high` | `#ff8800` | Orange |
| `medium` | `#ffcc00` | Yellow |
| `low` | `#33aa33` | Green |

### Incident Status
| Status | Meaning |
|--------|---------|
| `active` | Ongoing, requires management |
| `monitoring` | Under observation, no blockage |
| `resolved` | Cleared |
| `false_alarm` | No actual incident |

### Recommendation Confidence → Badge
| Range | Badge |
|-------|-------|
| `>= 0.85` | ✅ High confidence |
| `0.65 – 0.84` | ⚠️ Review recommended |
| `< 0.65` | ❌ Low confidence — officer must verify |

### Alert Channels → Icons
| Channel | Icon | Description |
|---------|------|-------------|
| `vms` | 🚧 | Variable Message Sign on highway |
| `radio` | 📻 | Radio broadcast |
| `social` | 📱 | Social media / push notification |

---

## 13. Error Handling

All errors return standard HTTP codes with a JSON body:

```json
{ "detail": "Cannot publish alert — linked recommendation is 'pending', must be 'approved'." }
```

| Code | Meaning | Common cause |
|------|---------|-------------|
| `400` | Bad request | Publishing alert without approval, invalid enum value |
| `404` | Not found | Wrong `incident_id` or `recommendation_id` |
| `422` | Validation error | Missing required field, type mismatch |
| `500` | Server error | DB down, Kafka disconnected |

**Recommendation `blocked_reason` values:**
| Value | Meaning | UI action |
|-------|---------|-----------|
| `null` | Not blocked | Normal flow |
| `"llm_unavailable"` | Groq rate limited | Show retry notice, use fallback data |
| `"parse_error"` | LLM returned invalid JSON | Show raw narrative instead |
| `"low_confidence"` | Score below threshold | Flag for manual review |

---

## Ahmedabad Corridor IDs

| Corridor ID | Name | Location |
|-------------|------|----------|
| `AMD-SPRR-01` | SP Ring Road (West) | Bopal Circle area |
| `AMD-SGH-01` | SG Highway | Pakwan Cross Roads |
| `AMD-CGR-01` | CG Road | Swastik Cross Roads |
| `AMD-ASH-01` | Ashram Road | Income Tax Cross Roads |
| `AMD-DIN-01` | Drive-in Road | Gurukul Cross Roads |
| `AMD-NHW-08` | NH-48 (Delhi-Mumbai Hwy) | Narol Interchange |

---

*Generated from live API — TrafficCopilot v1.0.0 | Base URL: `http://localhost:8000`*

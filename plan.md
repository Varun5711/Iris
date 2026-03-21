# TrafficCopilot — Final Implementation Plan

## Context

Build an officer-in-the-loop traffic incident co-pilot that reduces coordination time from minutes to
seconds. Officers get structured AI recommendations (signal retiming, diversions, public alert drafts,
conversational Q&A) — but every action requires explicit human approval before anything is published.

**Scope:** Backend + WebSocket API only. `apps/web` scaffold is created (package.json + vite config)
but not implemented. All intelligence lives in `apps/api`.

**Key decisions:**
- **LLM:** Groq API (llama-3.3-70b-versatile) — OpenAI-compatible, sub-second inference, free tier
- **Event Backbone:** Apache Kafka in KRaft mode (no ZooKeeper) — durable topics, consumer groups, WS fanout
- **Cache:** Redis 7 — hot state cache only (not pub/sub; Kafka owns the event bus)
- **DB:** PostgreSQL + PostGIS + pgvector
- **Routing:** OSMnx + NetworkX
- **Deploy:** Docker Compose (`compose.yaml`)

**Why Kafka KRaft over Redis pub/sub:**
- KRaft mode: single `apache/kafka:3.7` container, no ZooKeeper, no extra deps
- Durable log: events are replayable; Redis pub/sub is fire-and-forget
- Native consumer groups: multiple API pods each consume the same topics independently
- Same `aiokafka` client used everywhere — one pattern for ingest, processing, and WS fanout
- Production upgrade path: swap single-node for MSK/Confluent Cloud with zero code changes

---

## Exact Folder Structure to Create

```
traffic-copilot/
├── README.md
├── .env.example
├── .gitignore
├── compose.yaml
├── Makefile
│
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   ├── prompt-design.md
│   ├── demo-script.md
│   └── judging-points.md
│
├── apps/
│   ├── web/                            # scaffold only — not implemented
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── public/
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── app/
│   │       ├── pages/
│   │       ├── components/
│   │       ├── features/
│   │       │   ├── map/
│   │       │   ├── incident/
│   │       │   ├── recommendations/
│   │       │   ├── alerts/
│   │       │   └── chat/
│   │       ├── lib/
│   │       │   ├── api.ts
│   │       │   ├── ws.ts
│   │       │   └── constants.ts
│   │       ├── hooks/
│   │       ├── types/
│   │       └── styles/
│   │
│   └── api/
│       ├── pyproject.toml
│       ├── alembic.ini
│       └── src/
│           ├── main.py                 # FastAPI app + lifespan
│           ├── core/
│           │   ├── config.py           # pydantic-settings, all env vars
│           │   ├── logging.py          # structlog JSON logger
│           │   └── security.py         # JWT decode, RBAC roles
│           ├── api/
│           │   ├── routes/
│           │   │   ├── incidents.py    # POST /incidents, GET /incidents/{id}
│           │   │   ├── recommendations.py  # GET /recommendations/{incident_id}
│           │   │   ├── alerts.py       # POST /alerts/approve, POST /alerts/reject
│           │   │   └── chat.py         # POST /chat
│           │   └── ws/
│           │       └── live_updates.py # WS /ws/{incident_id}
│           ├── db/
│           │   ├── session.py          # async SQLAlchemy engine + session
│           │   ├── models/             # SQLAlchemy ORM models
│           │   │   ├── incident.py
│           │   │   ├── segment.py
│           │   │   ├── recommendation.py
│           │   │   ├── alert.py
│           │   │   └── audit.py
│           │   └── migrations/         # Alembic migration files
│           ├── schemas/
│           │   ├── incident.py         # Pydantic request/response models
│           │   ├── event.py            # TrafficEvent, SensorEvent, etc.
│           │   ├── recommendation.py   # RecommendationOut, CopilotResponse
│           │   └── alert.py            # AlertDraft, ApprovalRequest
│           ├── modules/
│           │   ├── ingest/
│           │   │   ├── __init__.py
│           │   │   └── normalizer.py       # raw input → TrafficEvent
│           │   ├── detector/               # <-- CORE: incident detection
│           │   │   ├── __init__.py
│           │   │   ├── rules.py            # heuristic rules per signal type
│           │   │   ├── scorer.py           # multi-signal confidence aggregator
│           │   │   └── lifecycle.py        # create/update/resolve incident records
│           │   ├── state_engine/
│           │   │   ├── __init__.py
│           │   │   ├── deduper.py
│           │   │   ├── map_matcher.py      # snap lat/lon → OSM way
│           │   │   ├── queue_estimator.py
│           │   │   └── corridor.py         # affected segment propagation
│           │   ├── routing/
│           │   │   ├── __init__.py
│           │   │   ├── graph.py        # OSMnx graph load + pickle cache
│           │   │   └── diversion.py    # NetworkX k-shortest-paths
│           │   ├── signal_plans/
│           │   │   ├── __init__.py
│           │   │   └── heuristics.py   # phase extension rules
│           │   ├── copilot/
│           │   │   ├── __init__.py
│           │   │   ├── llm_client.py   # Groq API + structured JSON output
│           │   │   └── prompt_loader.py # load prompts/ txt files
│           │   ├── context_builder/
│           │   │   ├── __init__.py
│           │   │   └── builder.py      # assemble state + pgvector SOP chunks
│           │   ├── policies/
│           │   │   ├── __init__.py
│           │   │   └── validator.py    # hard rules, confidence scoring, blocked_reason
│           │   ├── alerts/
│           │   │   ├── __init__.py
│           │   │   └── publisher.py    # mock VMS/radio/social output (post-approval)
│           │   └── audit/
│           │       ├── __init__.py
│           │       └── logger.py       # write every action to audit_log table
│           ├── integrations/
│           │   ├── groq/
│           │   │   └── client.py       # groq SDK wrapper, model=llama-3.3-70b-versatile
│           │   ├── redis/
│           │   │   └── client.py       # redis.asyncio client pointed at Redis
│           │   ├── postgres/
│           │   │   └── client.py       # pgvector helpers, PostGIS queries
│           │   └── osm/
│           │       └── loader.py       # OSMnx download + save graph
│           ├── workers/
│           │   ├── feed_replay.py      # async: replay data/ scenario JSONs
│           │   ├── incident_processor.py # async: poll new events → state engine
│           │   └── embedding_sync.py   # async: embed SOP chunks → pgvector
│           └── tests/
│               ├── unit/
│               ├── integration/
│               └── fixtures/
│
├── packages/
│   ├── shared-contracts/
│   │   ├── traffic_event.schema.json
│   │   ├── incident_snapshot.schema.json
│   │   ├── recommendation.schema.json
│   │   └── public_alert.schema.json
│   └── prompt-schemas/
│       ├── incident_summary.schema.json
│       ├── signal_plan.schema.json
│       ├── diversion.schema.json
│       └── answer.schema.json
│
├── prompts/
│   ├── system/
│   │   ├── officer_copilot.txt
│   │   └── public_alert_writer.txt
│   ├── tasks/
│   │   ├── summarize_incident.txt
│   │   ├── generate_signal_plan.txt
│   │   ├── generate_diversion.txt
│   │   └── answer_question.txt
│   └── examples/
│
├── data/
│   ├── raw/
│   │   ├── incidents/
│   │   ├── speed_feeds/
│   │   ├── camera_metadata/
│   │   └── radio_transcripts/
│   ├── processed/
│   ├── seeds/
│   │   ├── road_network/
│   │   ├── intersections/
│   │   ├── signals/
│   │   └── sop_docs/
│   └── replays/
│       ├── scenario_1/
│       ├── scenario_2/
│       └── scenario_3/
│
├── scripts/
│   ├── setup/
│   ├── import_osm/
│   ├── seed_db/
│   ├── replay_feeds/
│   ├── generate_embeddings/
│   └── smoke_tests/
│
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.example.yaml
│   ├── postgres.yaml
│   ├── redis.yaml
│   ├── ollama.yaml               # kept as placeholder / swap target
│   ├── api.yaml
│   ├── web.yaml
│   └── ingress.yaml
│
└── assets/
    ├── screenshots/
    ├── diagrams/
    └── sample-alerts/
```

---

## Database Schema (`apps/api/db/migrations/001_initial.sql` via Alembic)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE incidents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status          TEXT NOT NULL DEFAULT 'active',      -- active | resolved | archived
  severity        TEXT NOT NULL,                        -- low | medium | high | critical
  description     TEXT,
  reporter_id     TEXT,
  location        GEOMETRY(Point, 4326),
  corridor_id     TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE incident_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     UUID REFERENCES incidents(id) ON DELETE CASCADE,
  source          TEXT NOT NULL,   -- sensor | camera | radio | manual
  raw_payload     JSONB,
  event_time      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE affected_segments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     UUID REFERENCES incidents(id) ON DELETE CASCADE,
  osm_way_id      BIGINT,
  geom            GEOMETRY(LineString, 4326),
  delay_seconds   INT,
  congestion_pct  FLOAT
);

CREATE TABLE diversion_routes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     UUID REFERENCES incidents(id) ON DELETE CASCADE,
  route_geojson   JSONB,
  extra_minutes   FLOAT,
  redistribution_pct FLOAT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE signal_plan_candidates (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     UUID REFERENCES incidents(id) ON DELETE CASCADE,
  intersection_id TEXT,
  current_plan    JSONB,
  suggested_plan  JSONB,
  rationale       TEXT,
  confidence      FLOAT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE recommendations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id     UUID REFERENCES incidents(id) ON DELETE CASCADE,
  rec_type        TEXT,     -- diversion | signal_retiming | alert_draft | narrative
  action          TEXT,
  location        TEXT,
  expected_impact TEXT,
  evidence_refs   JSONB,
  confidence      FLOAT,
  blocked_reason  TEXT,
  review_required BOOLEAN DEFAULT false,
  status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
  prompt_snapshot JSONB,
  llm_response    JSONB,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id UUID REFERENCES recommendations(id),
  channel         TEXT,    -- vms | radio | social
  draft_text      TEXT,
  status          TEXT DEFAULT 'draft',  -- draft | approved | published
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE approvals (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id   UUID REFERENCES recommendations(id),
  officer_id          TEXT,
  action              TEXT,    -- approved | rejected
  note                TEXT,
  actioned_at         TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type  TEXT NOT NULL,
  actor       TEXT,
  payload     JSONB,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sop_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT,
  content     TEXT,
  embedding   VECTOR(1024)    -- nomic-embed or Groq embeddings
);
CREATE INDEX ON sop_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
```

---

## Pydantic Schemas (key models)

### `apps/api/src/schemas/event.py`
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

class TrafficEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    source: Literal["sensor", "camera", "radio", "manual"]
    event_time: datetime
    corridor_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    payload: dict

class SensorSpeedEvent(TrafficEvent):
    source: Literal["sensor"] = "sensor"
    segment_id: str
    speed_kmh: float
    free_flow_kmh: float
    occupancy_pct: float

class CameraMetaEvent(TrafficEvent):
    source: Literal["camera"] = "camera"
    camera_id: str
    lane_blocked: bool
    vehicle_count: int
    incident_detected: bool
    confidence: float
```

### `apps/api/src/schemas/recommendation.py`
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class SignalAction(BaseModel):
    intersection_id: str
    action: str
    expected_impact: str
    confidence: float = Field(ge=0, le=1)

class DiversionPlan(BaseModel):
    route_description: str
    estimated_extra_minutes: float
    traffic_redistribution_pct: float
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str]

class AlertDraft(BaseModel):
    channel: Literal["vms", "radio", "social"]
    message: str

class CopilotResponse(BaseModel):
    incident_summary: str
    signal_actions: list[SignalAction]
    diversion_plan: Optional[DiversionPlan] = None
    alert_drafts: list[AlertDraft]
    narrative: str
    conversational_answer: Optional[str] = None
    overall_confidence: float = Field(ge=0, le=1)
    review_required: bool
    blocked_reason: Optional[str] = None
    evidence_refs: list[str]
```

---

## Groq Integration (`apps/api/src/integrations/groq/client.py`)

```python
from groq import AsyncGroq
from apps.api.src.schemas.recommendation import CopilotResponse
import json

client = AsyncGroq()  # reads GROQ_API_KEY from env

MODEL = "llama-3.3-70b-versatile"

async def call_copilot(system_prompt: str, user_prompt: str) -> CopilotResponse:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2048,
    )
    raw = json.loads(response.choices[0].message.content)
    return CopilotResponse.model_validate(raw)
```

---

## Prompt Design (`prompts/system/officer_copilot.txt`)

```
You are an advisory AI co-pilot for a traffic control officer.
You MUST NEVER issue direct signal actuation commands.
You MUST ONLY provide recommendations that require human approval before any action is taken.
Every recommendation must include: action, location, expected_impact, evidence_refs, confidence (0.0–1.0).
Set review_required=true whenever overall_confidence < 0.6 or any evidence ref is missing.
Return ONLY valid JSON matching the CopilotResponse schema. No prose outside the JSON object.
```

---

## WebSocket Architecture (`apps/api/src/api/ws/live_updates.py`)

```python
# Room-based WebSocket fanout
# WS endpoint: /ws/{incident_id}
# On connect: subscribe to incident room
# On state update: push RecommendationReady event to all subscribers in room
# On approval: push ApprovalResult event
# Redis pub/sub backs the fanout across multiple API workers

class ConnectionManager:
    rooms: dict[str, set[WebSocket]]
    async def connect(incident_id, ws)
    async def disconnect(incident_id, ws)
    async def broadcast(incident_id, message: dict)
```

---

## `compose.yaml` (infrastructure)

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: trafficcopilot
      POSTGRES_USER: tc
      POSTGRES_PASSWORD: tc_secret
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tc -d trafficcopilot"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10

  kafka:
    image: apache/kafka:3.7.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_LOG_DIRS: /tmp/kraft-combined-logs
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    ports: ["9092:9092"]
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1"]
      interval: 10s
      retries: 10

  api:
    build: ./apps/api
    env_file: .env
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
      kafka:    { condition: service_healthy }
    volumes:
      - ./data:/app/data
      - ./prompts:/app/prompts

  prometheus:
    image: prom/prometheus
    volumes: ["./k8s/prometheus.yml:/etc/prometheus/prometheus.yml"]
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana
    ports: ["3001:3000"]

volumes:
  pg_data:
```

---

## `.env.example`

```
# Groq
GROQ_API_KEY=gsk_...

# Postgres
DATABASE_URL=postgresql+asyncpg://tc:tc_secret@postgres:5432/trafficcopilot

# Redis / Redis-compatible
REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_CONSUMER_GROUP_ID=trafficcopilot-api

# App
SECRET_KEY=change_me_in_production
ENVIRONMENT=development
LOG_LEVEL=INFO

# OSMnx corridor (seed city)
OSM_PLACE_NAME="Manhattan, New York, USA"
OSM_GRAPH_CACHE=data/processed/graph.gpickle
```

---

## API Endpoints

| Method | Path | Module | Description |
|--------|------|--------|-------------|
| POST | `/incidents` | ingest → state_engine | Create incident, trigger processing |
| GET | `/incidents/{id}` | db | Fetch incident + affected segments |
| POST | `/incidents/{id}/events` | ingest | Append sensor/camera/radio event |
| GET | `/recommendations/{incident_id}` | copilot | Get latest CopilotResponse |
| POST | `/recommendations/{id}/approve` | policies → audit | Approve recommendation |
| POST | `/recommendations/{id}/reject` | policies → audit | Reject recommendation |
| POST | `/alerts/{id}/publish` | alerts.publisher | Mock-publish approved alert |
| POST | `/chat` | copilot | Conversational Q&A on incident |
| WS | `/ws/{incident_id}` | ws/live_updates | Real-time push of state changes |
| GET | `/health` | core | Liveness probe |

---

## Data Flow (Runtime) — Full System Boundary

```
╔══════════════════════════════════════════════════════════════════════╗
║                  PLATFORM BOUNDARY (all inside our system)           ║
║                                                                      ║
║  [Simulated / Replayed Signals]                                      ║
║   speed_feed JSON  │  camera_meta JSON  │  manual form  │  transcript║
║         │                │                   │               │       ║
║         └────────────────┴───────────────────┴───────────────┘       ║
║                                  │                                   ║
║                                  ▼                                   ║
║  ┌───────────────────────────────────────────────────┐               ║
║  │  LAYER 1 — INGEST                                 │               ║
║  │  ingest/normalizer.py                             │               ║
║  │  raw input ──► TrafficEvent (typed, validated)    │               ║
║  │  POST to /incidents/{id}/events or /incidents     │               ║
║  └───────────────────────────┬───────────────────────┘               ║
║                              │                                       ║
║                              ▼                                       ║
║  ┌───────────────────────────────────────────────────┐               ║
║  │  LAYER 2 — INCIDENT DETECTION                     │               ║
║  │  detector/rules.py     — per-source rules:        │               ║
║  │    speed < 20% free-flow        → score += 0.4    │               ║
║  │    camera.incident_detected     → score += 0.4    │               ║
║  │    radio keyword match (crash)  → score += 0.3    │               ║
║  │    manual report                → score += 0.9    │               ║
║  │  detector/scorer.py    — aggregate multi-signal   │               ║
║  │    confidence = weighted_sum, capped at 1.0       │               ║
║  │  detector/lifecycle.py — decision:                │               ║
║  │    confidence ≥ 0.5 → CREATE or UPDATE incident   │               ║
║  │    confidence < 0.5 → log as unconfirmed watch    │               ║
║  │    all signals clear  → RESOLVE incident          │               ║
║  └───────────────────────────┬───────────────────────┘               ║
║                              │                                       ║
║                              ▼                                       ║
║  ┌───────────────────────────────────────────────────┐               ║
║  │  LAYER 3 — TRAFFIC STATE ESTIMATION               │               ║
║  │  state_engine/deduper.py       — drop duplicate   │               ║
║  │  state_engine/map_matcher.py   — snap to OSM way  │               ║
║  │  state_engine/queue_estimator  — delay heuristic  │               ║
║  │  state_engine/corridor.py      — propagate impact │               ║
║  │                                                   │               ║
║  │       ┌────────────────────┐                      │               ║
║  │       ▼                    ▼                      │               ║
║  │   Postgres              Redis                     │               ║
║  │   (persistent state)    (hot cache + pub/sub)     │               ║
║  └───────────────────────────┬───────────────────────┘               ║
║                              │                                       ║
║                              ▼                                       ║
║  ┌───────────────────────────────────────────────────┐               ║
║  │  LAYER 4 — RECOMMENDATION ENGINE                  │               ║
║  │  routing/diversion.py   — OSMnx + NetworkX        │               ║
║  │  signal_plans/heuristics— phase extension rules   │               ║
║  │  context_builder/       — state + pgvector SOPs   │               ║
║  │  integrations/groq/     — llama-3.3-70b-versatile │               ║
║  │    response_format: json_object                   │               ║
║  │    → CopilotResponse (structured, typed)          │               ║
║  │  policies/validator     — hard rules + confidence │               ║
║  └───────────────────────────┬───────────────────────┘               ║
║                              │                                       ║
║                              ▼                                       ║
║  ┌───────────────────────────────────────────────────┐               ║
║  │  LAYER 5 — OFFICER APPROVAL LOOP                  │               ║
║  │  recommendations table   — stored, versioned      │               ║
║  │  audit/logger.py         — every action logged    │               ║
║  │  WS /ws/{incident_id}    — Redis pub/sub fanout   │               ║
║  │  POST /approve or /reject— RBAC enforced          │               ║
║  │  alerts/publisher.py     — ONLY after approval    │               ║
║  └───────────────────────────┬───────────────────────┘               ║
║                              │                                       ║
╚══════════════════════════════╪═════════════════════════════════════╝
                               │
         ┌─────────────────────┼────────────────────────┐
         ▼                     ▼                        ▼
   Mock VMS board         Mock Radio            Mock Social post
   (logged to stdout)     (logged to stdout)    (logged to stdout)
```

---

## Kafka-Driven Workers

All workers are `asyncio.Task`s started inside FastAPI's `lifespan` context in `main.py`.
Each worker is a long-running Kafka producer or consumer loop.

| Worker | File | Kafka role | What it does |
|--------|------|-----------|--------------|
| `feed_replay` | `workers/feed_replay.py` | **Producer** → `traffic.events.raw` | Reads `data/replays/scenario_N/*.json`, publishes TrafficEvent messages on a configurable interval. Simulates live sensors for demo. |
| `incident_processor` | `workers/incident_processor.py` | **Consumer** `traffic.events.raw` → **Producer** `incident.state.updated` | Runs the full pipeline: deduper → map_matcher → detector (confidence scoring) → state_engine → corridor → writes Postgres/Redis → publishes IncidentSnapshot |
| `copilot_trigger` | `workers/copilot_trigger.py` | **Consumer** `incident.state.updated` → **Producer** `recommendation.ready` | Calls context_builder → Groq API → policy_validator → writes recommendations table → publishes CopilotResponse |
| `ws_fanout` | `workers/ws_fanout.py` | **Consumer** `incident.state.updated` + `recommendation.ready` + `approval.actioned` | Calls `ConnectionManager.broadcast(incident_id, msg)` for every message → pushes to all active WS clients in that incident room |
| `embedding_sync` | `workers/embedding_sync.py` | No Kafka — one-shot | On startup: reads `data/seeds/sop_docs/`, calls Groq embeddings API, upserts into `sop_chunks` pgvector table |

### Worker Data Flow via Kafka

```
feed_replay
    │ PRODUCE
    ▼
traffic.events.raw ──► incident_processor
                              │ PRODUCE
                              ▼
                       incident.state.updated ──► copilot_trigger
                              │                          │ PRODUCE
                              │                          ▼
                              │                   recommendation.ready
                              │                          │
                              └──────────┐               │
                                         ▼               ▼
                                      ws_fanout (consumes all 3 topics)
                                         │
                                         ▼
                                  ConnectionManager
                                  broadcast to WS clients
```

---

## Prompt Files

### `prompts/tasks/generate_signal_plan.txt`
```
Given the incident context below, suggest signal retiming for up to 5 intersections.
Rules:
- Only suggest phase extensions or cycle splits. Never suggest direct actuation.
- Each suggestion must name the intersection_id, describe the action, state expected_impact, and give a confidence between 0.0 and 1.0.
- If confidence < 0.6 set review_required=true.
Context: {context}
```

### `prompts/tasks/answer_question.txt`
```
The officer asks: "{question}"
Using only the incident context below, answer concisely. Cite evidence_refs from the context.
Do not speculate beyond the data. If data is insufficient, say so and set review_required=true.
Context: {context}
```

---

## Fallback / Graceful Degradation

| Failure | Fallback Behavior |
|---------|-------------------|
| Groq API unavailable / timeout | Return deterministic diversion + signal plan only; alert drafts from template; `review_required=true`, `blocked_reason="llm_unavailable"` |
| Redis unavailable | Skip cache layer; read directly from Postgres |
| OSMnx graph missing | Return empty diversion; log warning; continue with signal + alert recommendations |
| pgvector empty | Skip SOP retrieval; proceed with state-only context |
| Postgres write fails | Abort recommendation; return 503 with audit entry in structured log |

---

## Shared JSON Contracts (`packages/shared-contracts/`)

### `traffic_event.schema.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "TrafficEvent",
  "required": ["event_id", "source", "event_time", "payload"],
  "properties": {
    "event_id": { "type": "string", "format": "uuid" },
    "source":   { "type": "string", "enum": ["sensor","camera","radio","manual"] },
    "event_time": { "type": "string", "format": "date-time" },
    "corridor_id": { "type": "string" },
    "lat": { "type": "number" },
    "lon": { "type": "number" },
    "payload": { "type": "object" }
  }
}
```

### `recommendation.schema.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "title": "CopilotResponse",
  "required": ["incident_summary","signal_actions","alert_drafts","narrative","overall_confidence","review_required","evidence_refs"],
  "properties": {
    "incident_summary": { "type": "string" },
    "signal_actions": { "type": "array" },
    "diversion_plan": { "type": ["object","null"] },
    "alert_drafts": { "type": "array" },
    "narrative": { "type": "string" },
    "conversational_answer": { "type": ["string","null"] },
    "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "review_required": { "type": "boolean" },
    "blocked_reason": { "type": ["string","null"] },
    "evidence_refs": { "type": "array", "items": { "type": "string" } }
  }
}
```

---

## Kafka KRaft — Topics & Roles

Apache Kafka in KRaft mode (single broker, no ZooKeeper) is the event backbone.
It handles: raw signal ingestion → incident processing pipeline → WS fanout.

### Kafka Topics

| Topic | Producer | Consumer | Payload |
|-------|----------|----------|---------|
| `traffic.events.raw` | ingest routes (POST /events) | incident_processor worker | `TrafficEvent` JSON |
| `incident.state.updated` | state_engine / detector | ws_fanout worker, copilot trigger | `IncidentSnapshot` JSON |
| `recommendation.ready` | copilot-service path | ws_fanout worker | `CopilotResponse` JSON |
| `approval.actioned` | approval routes | publisher worker, ws_fanout | `ApprovalEvent` JSON |

### Kafka Configuration (KRaft, single broker, Docker)
```yaml
# compose.yaml snippet
kafka:
  image: apache/kafka:3.7.0
  environment:
    KAFKA_NODE_ID: 1
    KAFKA_PROCESS_ROLES: broker,controller
    KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
    KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"  # base64 UUID, any valid value
  ports: ["9092:9092"]
```

### WebSocket Fanout via Kafka
The `ws_fanout` worker (inside `workers/`) is a long-running Kafka consumer that subscribes to
`incident.state.updated` and `recommendation.ready`. On each message it calls
`connection_manager.broadcast(incident_id, payload)` to push to all connected WebSocket clients in that room.

```
Kafka topic: incident.state.updated
       │
       ▼
ws_fanout worker (aiokafka consumer)
       │
       ▼
ConnectionManager.broadcast(incident_id, msg)
       │
       ├──► WS client 1 (officer 1)
       ├──► WS client 2 (supervisor)
       └──► WS client 3 (public info officer)
```

---

## Redis — Hot State Cache Only

Redis is now **cache only** — Kafka owns the event bus. Redis stores only the latest computed state
for fast reads by the copilot and WS gateway without hitting Postgres.

| Key | Type | TTL | Written by | Read by |
|-----|------|-----|-----------|---------|
| `incident:{id}:snapshot` | JSON string | 60 s | state_engine | copilot, WS gateway |
| `incident:{id}:segments` | JSON string | 60 s | state_engine | context_builder |
| `incident:{id}:diversion` | JSON string | 60 s | routing module | context_builder |
| `incident:{id}:signal_plan` | JSON string | 60 s | signal_plans | context_builder |
| `sensor:{segment_id}:speed` | JSON string | 30 s | incident_processor | context_builder |

---

## What You Need to Provide (Credentials & Data)

### API Keys — Required on Day 1
| Key | Where to get | Environment variable |
|-----|-------------|---------------------|
| Groq API key | [console.groq.com](https://console.groq.com) → free tier, no CC needed | `GROQ_API_KEY=gsk_...` |

That is the **only** external API key needed for the core system.

### Optional / Nice-to-Have
| Service | Purpose | Env var |
|---------|---------|---------|
| Mapbox token | If you wire the React map later | `VITE_MAPBOX_TOKEN=pk.xxx` |
| OpenTelemetry endpoint | If pushing traces to Grafana Cloud | `OTEL_EXPORTER_OTLP_ENDPOINT` |

### Data You Need to Decide
| Decision | Options | We recommend |
|----------|---------|-------------|
| Which city / corridor? | Any city OSMnx can download | Manhattan, NYC — dense grid, well-documented |
| Number of replay scenarios | 1–3 | 3 (minor / major / multi-incident) |
| SOP documents | Your own or synthetic | We generate 10–15 synthetic SOPs on setup |
| Intersection IDs | From OSM node IDs or named | OSM node IDs from the downloaded graph |

### Infrastructure — All Self-Hosted via Docker Compose
Everything below runs locally or on any Linux box — **no cloud accounts needed**:
- PostgreSQL 16 + PostGIS + pgvector
- Redis 7
- Prometheus + Grafana
- The API itself

---

## Why This Wins the Hackathon

### What Judges Care About
1. **Real-time intelligence under pressure** — we deliver first recommendation in < 30 seconds, refreshed every 5–10 s
2. **Human-in-the-loop** — every action requires approval; judges trust this more than autonomous control
3. **Grounded outputs** — every recommendation has `evidence_refs` pointing to actual sensor data or SOP chunks
4. **Structured, reliable AI** — Groq + `response_format: json_object` means zero hallucinated free text in recommendations
5. **Fallback resilience** — system degrades gracefully; judges will try to break it
6. **Audit trail** — every prompt, response, approval, and publish is logged; this is what a city would demand

### Demo Story (8 minutes, judge-facing)
```
0:00  "A multi-vehicle accident just hit I-5 SB Exit 42. Normal tools: radio + 4 separate screens."
0:10  Feed simulator fires. Live map: affected segment goes red. Congestion heatmap builds.
0:28  Recommendation card appears — < 30 seconds from detection.
       Signal retiming: 3 intersections, phase +20s, confidence 0.87
       Diversion: via SR-99, +4 min, 35% redistribution, confidence 0.82
       Alert drafts: VMS / Radio / Twitter — ready to publish
0:40  Officer asks: "How bad is the queue right now?"
       → Chat answer in 1.2 seconds, cites sensor segment IDs as evidence
0:55  Officer asks: "Is it safe to open the shoulder lane?"
       → SOP chunk retrieved from pgvector, answer + confidence 0.71, review_required=false
1:10  Officer hits APPROVE on diversion.
       → Audit log written. Mock VMS fires. Publisher logs the alert text.
1:30  "Now watch what happens when we kill the Groq API."
       → Restart with bad key. System still returns deterministic diversion.
       → blocked_reason="llm_unavailable". Signal plan from heuristics. Alert from template.
2:00  Grafana: p95 recommendation latency 2.1s. Time from incident to first approval: 62s.
       "Manual coordination at this center averages 4–6 minutes."
```

### Differentiators vs Typical Hackathon Submissions
- **Not a chatbot** — structured JSON output, not prose
- **Not a dashboard** — active recommendations with approval flow
- **Not mock data** — real OSMnx graph of the city, real road segments
- **Not stateless** — full incident state machine, not a one-shot LLM call
- **Reproducible** — `make up && make seed && make replay` → full demo in 3 commands

---

## `pyproject.toml` (key dependencies)

```toml
[project]
name = "trafficcopilot-api"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "redis>=5.0",         # redis.asyncio — hot state cache only
    "aiokafka>=0.11",     # async Kafka KRaft producer + consumer
    "groq>=0.9",
    "osmnx>=1.9",
    "networkx>=3.3",
    "shapely>=2.0",
    "pgvector>=0.3",
    "structlog>=24.0",
    "opentelemetry-api>=1.25",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-instrumentation-fastapi>=0.46b0",
    "httpx>=0.27",
    "python-jose[cryptography]>=3.3",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "httpx", "ruff", "mypy"]
```

---

## Makefile Targets

```makefile
up:         docker compose -f compose.yaml up -d
down:       docker compose -f compose.yaml down
migrate:    docker compose exec api alembic upgrade head
seed:       docker compose exec api python scripts/seed_db/run.py
graph:      docker compose exec api python scripts/import_osm/run.py
embeddings: docker compose exec api python scripts/generate_embeddings/run.py
replay:     docker compose exec api python scripts/replay_feeds/run.py --scenario 1
smoke:      docker compose exec api python scripts/smoke_tests/run.py
logs:       docker compose logs -f api
```

---

## Build Order (48 Hours)

### Phase 1 — Foundation (0–8h)
- `compose.yaml` + Postgres + Redis + Prometheus + Grafana services
- `apps/api/pyproject.toml` with all dependencies
- `.env.example` + `apps/api/src/core/config.py`
- `apps/api/src/db/session.py` + Alembic init + `001_initial.sql`
- All `apps/api/src/schemas/` Pydantic models
- All `packages/shared-contracts/*.schema.json`
- `data/` directory structure + 3 replay scenario JSON files

### Phase 2 — Ingest + Detection + State Engine (8–20h)
- `modules/ingest/normalizer.py` — TrafficEvent typed schema
- **`modules/detector/rules.py`** — per-source detection rules with confidence scores
- **`modules/detector/scorer.py`** — multi-signal weighted confidence aggregator
- **`modules/detector/lifecycle.py`** — create / update / resolve incident records
- `modules/state_engine/` — deduper, map_matcher, queue_estimator, corridor
- `integrations/kafka/producer.py` + `consumer.py` + `topics.py` — aiokafka wrappers
- `integrations/redis/client.py` — cache only client
- `integrations/postgres/client.py` — pgvector + PostGIS helpers
- `api/routes/incidents.py` (POST + GET) — validates + produces to `traffic.events.raw`
- `workers/incident_processor.py` — Kafka consumer: `traffic.events.raw` → detector + state_engine → produces `incident.state.updated`
- `workers/feed_replay.py` — Kafka producer: reads `data/replays/scenario_N/` → `traffic.events.raw`
- `workers/ws_fanout.py` — Kafka consumer: `incident.state.updated` → WS broadcast
- `scripts/import_osm/run.py` + `integrations/osm/loader.py`

### Phase 3 — Routing + Signals (20–30h)
- `modules/routing/graph.py` + `modules/routing/diversion.py`
- `modules/signal_plans/heuristics.py`
- `scripts/seed_db/` + `scripts/generate_embeddings/`
- `workers/embedding_sync.py`
- `data/seeds/sop_docs/` — 10–15 realistic SOP text files

### Phase 4 — Copilot + LLM (30–40h)
- `prompts/` all system + task txt files
- `integrations/groq/client.py`
- `modules/copilot/prompt_loader.py` + `llm_client.py`
- `modules/context_builder/builder.py`
- `modules/policies/validator.py`
- `workers/copilot_trigger.py` — Kafka consumer: `incident.state.updated` → Groq → produces `recommendation.ready`
- `api/routes/recommendations.py`
- `api/routes/chat.py`
- Fallback path in `llm_client.py` (Groq unavailable → deterministic response)

### Phase 5 — Approval + WS + Publish (40–48h)
- `api/ws/live_updates.py` WebSocket fanout
- `modules/audit/logger.py`
- `api/routes/alerts.py` (approve / reject / publish)
- `modules/alerts/publisher.py` (mock VMS/radio/social)
- `apps/api/src/main.py` lifespan wiring of all workers
- `scripts/smoke_tests/run.py` end-to-end checks
- `docs/` all 5 markdown files

---

## NLP in the Platform — Where and Why

NLP is not optional here. The problem statement explicitly requires:
- Extracting incident signals from radio transcripts (unstructured text)
- Understanding officer conversational questions ("Should I open the southbound lane?")
- Generating natural-language alert drafts (VMS, radio, social media)
- Maintaining a running incident narrative the officer can query

### NLP Touch Points End-to-End

```
┌─────────────────────────────────────────────────────────────────────┐
│  NLP TOUCH POINT 1 — Radio Transcript Ingestion                     │
│  File: modules/ingest/normalizer.py + modules/detector/rules.py     │
│                                                                     │
│  Raw radio text: "Unit 7 reports multi-car on I-5 SB near Exit 42"  │
│           │                                                         │
│           ▼  Groq call: extract_incident_signals()                  │
│  Structured output:                                                 │
│    { "incident_type": "multi-vehicle collision",                    │
│      "location": "I-5 SB Exit 42",                                 │
│      "severity_hint": "high",                                       │
│      "confidence": 0.82 }                                           │
│           │                                                         │
│           ▼  → fed into detector/scorer.py as +0.3 confidence       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  NLP TOUCH POINT 2 — Recommendation Generation                      │
│  File: workers/copilot_trigger.py + modules/copilot/llm_client.py   │
│                                                                     │
│  Input: full incident context (state + segments + speeds + SOPs)    │
│           │                                                         │
│           ▼  Groq llama-3.3-70b-versatile                           │
│           response_format: json_object → CopilotResponse            │
│           Outputs:                                                  │
│             incident_summary: natural language situation summary    │
│             signal_actions:   named intersections + phase changes   │
│             diversion_plan:   route description + impact estimate   │
│             alert_drafts:     VMS (≤100 chars), radio, social       │
│             narrative:        running incident chronicle            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  NLP TOUCH POINT 3 — Officer Conversational Q&A                     │
│  File: api/routes/chat.py + modules/context_builder/builder.py      │
│                                                                     │
│  Officer: "Should I open the southbound shoulder lane?"             │
│           │                                                         │
│           ▼  context_builder assembles:                             │
│             - current incident state (Postgres)                     │
│             - live segment speeds (Redis)                           │
│             - current diversion load (Redis)                        │
│             - active signal plan (Redis)                            │
│             - top-5 SOP chunks via pgvector semantic search         │
│               (query embedding matches "shoulder lane opening SOP") │
│           │                                                         │
│           ▼  Groq call with conversational_answer task prompt       │
│           Structured output:                                        │
│             conversational_answer: "Based on sensor data segment    │
│               S-042, speeds have recovered to 48 km/h (87% of      │
│               free flow). SOP 4.3 requires ≥80% free flow before   │
│               shoulder opening. Opening is advisable. Confidence    │
│               0.81. Requires supervisor approval."                  │
│             evidence_refs: ["sensor:S-042", "sop:4.3"]             │
│             review_required: false                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  NLP TOUCH POINT 4 — Alert Draft Generation                         │
│  File: prompt task: generate_alert_drafts (inside copilot_trigger)  │
│                                                                     │
│  Input: incident summary + location + severity                      │
│  Output per channel:                                                │
│    VMS:    "ACCIDENT I-5 SB EXIT 42. USE SR-99. EXPECT 20 MIN DELAY"│
│    Radio:  "Attention drivers: major accident on I-5 southbound at  │
│             Exit 42. Police on scene. Use SR-99 as alternate."      │
│    Social: "🚨 TRAFFIC ALERT: Multi-vehicle accident I-5 SB Exit 42.│
│             Expect major delays. Use SR-99. Updates to follow."     │
└─────────────────────────────────────────────────────────────────────┘
```

### New Module: `modules/nlp/`

```
modules/nlp/
├── __init__.py
├── transcript_extractor.py   # extract structured signals from radio text via Groq
├── intent_classifier.py      # classify officer question intent (status_check | safety_query | eta_query | action_request)
└── alert_formatter.py        # enforce channel-specific formatting rules (char limits, tone, etc.)
```

Add to folder structure inside `apps/api/src/modules/`.

### NLP Prompt Files to Add

```
prompts/tasks/
├── extract_transcript_signals.txt   # radio → structured incident signal
├── classify_officer_intent.txt      # officer question → intent type
└── generate_alert_drafts.txt        # incident context → VMS/radio/social text
```

---

## pgvector — Used End-to-End (Not Just SOP Lookup)

pgvector is used in **four distinct places** in the system, not only for SOPs.

### 1. SOP / Policy Retrieval (existing — already planned)
```
Query: officer question or current incident summary
Embedding: Groq text-embedding-ada or nomic-embed-text
Table: sop_chunks (embedding VECTOR(1024))
Result: top-5 most relevant SOP paragraphs injected into LLM context
```

### 2. Incident Similarity Search (NEW)
When a new incident is detected, find the 3 most similar historical incidents.
Injects their resolution time, diversions used, and outcome into the copilot context.
```sql
-- incident_summaries table
CREATE TABLE incident_summaries (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id),
  summary_text TEXT,
  embedding   VECTOR(1024),
  outcome     TEXT,
  resolution_minutes INT,
  created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON incident_summaries USING ivfflat (embedding vector_cosine_ops);
```
When a new incident is created → embed its description → query top-3 → inject as
`similar_past_incidents` in the copilot context.

### 3. Alert Template Retrieval (NEW)
Pre-written approved alert templates are embedded. When drafting alerts, retrieve the
most similar approved template as a starting point for the LLM.
```sql
CREATE TABLE alert_templates (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel     TEXT,
  template    TEXT,
  embedding   VECTOR(1024)
);
```

### 4. Officer Question Semantic Routing (NEW)
Officer questions are classified by embedding similarity before being sent to the LLM.
This lets us pick the right task prompt and skip the LLM entirely for simple queries.
```
"What's the current speed on segment S-042?"
  → embedding → cosine sim → matches "sensor_status_query" intent
  → answered directly from Redis cache, no LLM call needed
  → saves latency, saves tokens
```

### Updated `schemigrations` — Add 3 New Tables
Add to `apps/api/db/migrations/002_pgvector_extended.sql`:
- `incident_summaries` (embedding VECTOR(1024))
- `alert_templates` (embedding VECTOR(1024))
- Keep `sop_chunks` (embedding VECTOR(1024))

### Updated `embedding_sync` Worker
`workers/embedding_sync.py` now handles:
1. `data/seeds/sop_docs/` → embed → `sop_chunks`
2. `data/seeds/alert_templates/` → embed → `alert_templates`
3. Resolved incidents (on resolve) → embed summary → `incident_summaries`

### Updated `context_builder`
`modules/context_builder/builder.py` now assembles 5 context sources:

```python
async def build_context(incident_id: UUID, question: str | None = None) -> dict:
    return {
        "incident_state":       await postgres.get_incident_snapshot(incident_id),
        "live_segments":        await redis.get_segments(incident_id),
        "sop_chunks":           await pgvector.search_sop(question or summary, top_k=5),
        "similar_incidents":    await pgvector.search_similar_incidents(summary, top_k=3),
        "alert_templates":      await pgvector.search_alert_templates(channel, top_k=2),
    }
```

---

## Key Non-Negotiables (Enforced in Code)

1. `policies/validator.py` rejects any LLM output that contains phrases like "actuate", "set signal", "change phase to" as direct commands — returns `blocked_reason="direct_actuation_detected"`
2. `alerts/publisher.py` checks `recommendation.status == "approved"` before publishing — hard guard
3. `audit/logger.py` write is in the same DB transaction as the approval write — no orphan approvals
4. `review_required = True` whenever `overall_confidence < 0.6` OR `evidence_refs` is empty
5. System prompt in `prompts/system/officer_copilot.txt` must contain the non-actuation clause — loaded at startup, validated at boot

---

## Verification Steps

1. `make up` → all containers healthy (`docker compose ps`) — postgres, redis, kafka, api all green
2. `make migrate` → all tables + pgvector index created
3. Kafka topic check: `docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list` → 4 topics visible
4. `make graph` → OSMnx graph saved to `data/processed/graph.gpickle`
5. `make embeddings` → `sop_chunks` table populated
6. `curl -X POST localhost:8000/incidents -d '{"severity":"high","lat":40.75,"lon":-73.99,"description":"MVA I-5 SB"}'` → 201, incident UUID returned; message visible in `traffic.events.raw`
7. `make replay` → feed_replay produces to `traffic.events.raw`; incident_processor consumes and produces to `incident.state.updated`
8. `curl localhost:8000/recommendations/{incident_id}` → CopilotResponse JSON, confidence > 0, alert_drafts populated; message visible in `recommendation.ready`
9. `curl -X POST localhost:8000/recommendations/{id}/approve` → status "approved", audit_log row inserted, `approval.actioned` topic message produced
10. `wscat -c ws://localhost:8000/ws/{incident_id}` → receives broadcast within 5 s of state change (ws_fanout consuming Kafka)
11. Stop API → restart with `GROQ_API_KEY=invalid` → recommendations return `blocked_reason="llm_unavailable"`, deterministic diversion still present
12. `make smoke` → all checks pass, prints time-to-first-recommendation metric (target < 30 s)

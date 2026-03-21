# TrafficCopilot — Officer-in-the-Loop Incident Co-Pilot

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B-F55036?logo=meta&logoColor=white)](https://groq.com/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL%2016-pgvector%200.7-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-3.7%20KRaft-231F20?logo=apachekafka&logoColor=white)](https://kafka.apache.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Problem Statement

Traffic Management Officers (TMOs) managing major corridor incidents face an information overload problem. Sensor feeds, CCTV metadata, officer radio transcripts, and CAD data arrive simultaneously across disconnected systems. Under time pressure, critical decisions — which lanes to close, which diversions to activate, what to broadcast on VMS — are made inconsistently and without always referencing the department's own Standard Operating Procedures.

**TrafficCopilot** fuses these real-time signals into a single coherent incident view, runs them through an SOP-grounded LLM recommendation engine, and surfaces ranked, justifiable action recommendations to the TMO in under 30 seconds. The AI proposes; the human decides. Every approval and rejection is immutably logged.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL DATA SOURCES                                │
│   [Loop Sensors]  [CCTV/CV]  [Officer Radio]  [CAD System]  [Waze CCP]      │
└──────────┬──────────┬──────────┬──────────────┬──────────────┬───────────────┘
           │          │          │              │              │
           ▼          ▼          ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: INGEST                                                             │
│  FastAPI HTTP/WS endpoints + Kafka feed_replay worker                       │
│  Schema validation → canonical TrafficEvent model                           │
│                              │ Kafka: raw.traffic_events                    │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: DETECTION                                                          │
│  incident_processor — multi-signal scorer, lifecycle manager, deduplication │
│                              │ Kafka: detected.incidents                    │
│                              │ Redis: corridor_state:{corridor_id}          │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: STATE ENGINE                                                       │
│  Queue length, severity tier, signal plan mismatch                          │
│  Redis: incident_snapshot:{id} (TTL 24h) + PostgreSQL (persistent)          │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: RECOMMENDATION ENGINE                                              │
│  copilot_trigger worker                                                      │
│   a) Context Builder: Redis snapshot + pgvector RAG (top-5 SOP chunks)      │
│      + OSMnx routing + signal heuristics + radio NLP (Groq call 1)          │
│   b) LLM Inference: Groq Llama 3.3 70B, JSON-mode, structured output        │
│   c) Policy Validation: schema check, SOP compliance flags                  │
│   d) Persist: PostgreSQL recommendations + Redis cache (TTL 1h)             │
│                              │ Kafka: recommendations.pending               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: APPROVAL & DISPATCH                                                │
│  TMO reviews in web dashboard → approve / reject individual actions         │
│  Approved actions dispatched to VMS / Radio / Social / Signal controllers   │
│  All decisions written to append-only audit_log                             │
│  WebSocket fanout → live updates to all connected dashboards                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- GNU Make
- A Groq API key ([console.groq.com](https://console.groq.com))

### 1. Clone

```bash
git clone https://github.com/your-org/traffic-copilot.git
cd traffic-copilot
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set your key:

```dotenv
GROQ_API_KEY=gsk_your_key_here
```

All other defaults work out of the box for local development.

### 3. Bootstrap (one command)

```bash
make bootstrap
```

This runs `docker compose up -d`, waits for services to become healthy, then runs database migrations, seeds SOP documents, imports the OSM road graph, and generates pgvector embeddings.

### 4. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

---

## Demo Walkthrough

Four commands to run the full end-to-end demo:

```bash
# Terminal 1 — start all services
make bootstrap

# Terminal 2 — replay the scenario feed (simulates sensor/camera/radio events)
make replay

# Terminal 3 — watch the Kafka topics fill up
make topics

# Terminal 4 — run the smoke test suite (creates incident, waits for recommendation, approves it)
make smoke
```

The smoke test prints a full trace:

```
[1/5] POST /incidents           → 201 Created   (id: abc-123)
[2/5] GET  /incidents/abc-123   → 200 OK         (severity: 2, status: open)
[3/5] WS   /ws/abc-123          → connected, waiting for recommendation_ready...
[4/5] recommendation_ready      → 3 actions proposed (fallback_mode: false)
[5/5] POST approve action-001   → 200 OK         (action dispatched)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness / readiness probe |
| `POST` | `/events` | Ingest a raw TrafficEvent (sensor, camera, manual, radio) |
| `POST` | `/incidents` | Manually create an incident |
| `GET` | `/incidents/{id}` | Fetch incident by ID |
| `GET` | `/incidents/{id}/recommendations` | List recommendations for an incident |
| `POST` | `/recommendations/{id}/actions/{action_id}/approve` | Approve a recommended action |
| `POST` | `/recommendations/{id}/actions/{action_id}/reject` | Reject a recommended action |
| `GET` | `/incidents/{id}/alerts` | List public alerts for an incident |
| `POST` | `/alerts/{id}/publish` | Publish an approved alert to its channel |
| `POST` | `/copilot/ask` | Ask a natural-language question about an incident |
| `WS` | `/ws/{incident_id}` | WebSocket channel — live incident updates |
| `GET` | `/metrics` | Prometheus metrics endpoint |

---

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `raw.traffic_events` | Ingest API, `feed_replay` | `incident_processor` | All normalised incoming events |
| `detected.incidents` | `incident_processor` | `copilot_trigger`, `ws_fanout` | New or updated incident records |
| `recommendations.pending` | `copilot_trigger` | `ws_fanout`, REST API | Generated recommendations awaiting TMO review |
| `alerts.approved` | Approval API | `alerts_publisher` | Approved alert messages ready for dispatch |
| `audit.actions` | Approval API | `audit_logger` | Immutable record of all officer decisions |

---

## Redis Cache Keys

| Key Pattern | Type | TTL | Contents |
|-------------|------|-----|----------|
| `corridor_state:{corridor_id}` | Hash | 15 min | Latest speed index, occupancy, active `incident_id` |
| `incident_snapshot:{incident_id}` | Hash | 24 h | Full `IncidentSnapshot` struct (severity, queues, signal state) |
| `recommendation:{incident_id}` | JSON string | 1 h | Latest `CopilotResponse` for fast API reads |
| `sop_embed_cache:{text_hash}` | String | 7 days | Cached embedding vector — avoids re-embedding identical text |
| `ws:channel:{incident_id}` | Pub/Sub channel | — | Live update fan-out channel for dashboard WebSocket subscribers |
| `ratelimit:llm:{officer_id}` | String + TTL | 60 s | LLM request rate-limiting per officer |

---

## pgvector Usage

SOP documents are chunked, embedded (Groq `text-embedding-ada-002` compatible), and stored in PostgreSQL:

```sql
CREATE TABLE sop_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sop_id      TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(1536),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON sop_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
```

At recommendation time, the incident description is embedded and the top-5 most relevant SOP chunks are retrieved in a single query:

```sql
SELECT sop_id, chunk_index, text,
       1 - (embedding <=> $1::vector) AS relevance
FROM sop_chunks
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

No external vector database is required — pgvector keeps the deployment footprint minimal.

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| API framework | FastAPI 0.111 (Python 3.12) | Async-native, auto OpenAPI docs, WebSocket, fastest Python I/O framework |
| LLM inference | Groq API — Llama 3.3 70B | Lowest-latency hosted inference; JSON-mode structured outputs; < 5 s per call |
| Message bus | Apache Kafka 3.7 (KRaft) | Durable replayable event log; decouples ingest from processing; enables demo feed replay |
| Cache / state | Redis 7 | Sub-millisecond corridor state reads; pub/sub for WebSocket fan-out |
| Primary DB | PostgreSQL 16 + PostGIS + pgvector 0.7 | ACID store for incidents, recommendations, audits; native cosine similarity for RAG |
| Routing | OSMnx + NetworkX | Open road network; congestion-aware shortest path; no vendor lock-in |
| ORM | SQLAlchemy 2.x (async) + Alembic | Async sessions match FastAPI; schema migrations |
| Validation | Pydantic v2 | Fast C-extension validation; integrates with FastAPI and SQLAlchemy |
| Frontend | React 18 + Vite + MapLibre GL | Fast SPA build; WebSocket live updates; open-source map renderer |
| Monitoring | Prometheus + Grafana | Recommendation latency, approval rate, Kafka consumer lag |
| Containers | Docker + Docker Compose | Reproducible local dev; single `make bootstrap` to run everything |
| Kubernetes | k8s manifests in `k8s/` | Production deployment path; ingress, StatefulSets, ConfigMaps, Secrets |

---

## Non-Negotiables — What the LLM Never Does

TrafficCopilot is built around a strict human-in-the-loop contract:

| Capability | LLM Role | Human Role |
|-----------|---------|-----------|
| Signal plan retiming | Recommends timing parameters | Must approve before sent to signal controller |
| Diversion activation | Suggests routes + messaging | Must approve before field units are notified |
| VMS / radio / social alerts | Drafts text per channel | Must approve before publication |
| Lane closure orders | Recommends scope and duration | Must approve before field dispatch |
| Incident closure | Suggests when conditions are met | Must confirm before record is closed |

The LLM **never** writes directly to field control systems. Every `RecommendedAction` requires an explicit `POST /approve` from an authenticated officer before any downstream dispatch occurs. The `audit_log` table is append-only at the application layer — no UPDATE or DELETE is permitted.

---

## Project Structure

```
traffic-copilot/
├── apps/
│   ├── api/                  # FastAPI application (Python 3.12)
│   │   ├── src/
│   │   │   ├── api/          # Route handlers
│   │   │   ├── modules/      # copilot, nlp, routing, signal_plans
│   │   │   ├── workers/      # Kafka consumers (incident_processor, copilot_trigger, ws_fanout)
│   │   │   └── tests/
│   │   └── Dockerfile
│   └── web/                  # React + Vite frontend (scaffold)
│       └── src/
│           └── lib/
│               ├── api.ts    # REST API client
│               └── ws.ts     # WebSocket client with auto-reconnect
├── data/
│   ├── replays/              # Scenario JSON files for feed replay demo
│   └── seeds/                # SOP documents + alert templates
├── docs/                     # Architecture, API contracts, demo script
├── infra/                    # Prometheus config
├── k8s/                      # Kubernetes manifests
├── packages/
│   ├── prompt-schemas/       # JSON Schemas for LLM output validation
│   └── shared-contracts/     # Canonical event/recommendation schemas
├── prompts/                  # LLM system + task prompts (plain text)
├── scripts/                  # Bootstrap, seed, OSM import, smoke tests
├── compose.yaml              # Docker Compose (all services)
├── Makefile                  # Developer shortcuts
└── .env.example              # Environment variable template
```

---

## Makefile Reference

```bash
make bootstrap    # Full one-shot setup: up + migrate + seed + graph + embeddings
make up           # docker compose up -d
make down         # docker compose down
make logs         # Tail API logs
make migrate      # Run Alembic migrations
make seed         # Seed SOP documents and alert templates
make graph        # Import OSM road network for Manhattan
make embeddings   # Generate pgvector embeddings for all SOP chunks
make replay       # Replay scenario 1 feed through Kafka
make smoke        # Run end-to-end smoke test suite
make topics       # List Kafka topics
make test         # Run pytest unit + integration tests
make shell        # Interactive shell inside the API container
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID |
| `LLM_TEMPERATURE` | `0.1` | LLM sampling temperature |
| `LLM_MAX_TOKENS` | `2048` | Max tokens per LLM response |
| `DATABASE_URL` | `postgresql+asyncpg://tc:tc_secret@postgres:5432/trafficcopilot` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `KAFKA_CONSUMER_GROUP_ID` | `trafficcopilot-api` | Kafka consumer group |
| `SECRET_KEY` | `change_me_in_production` | JWT signing secret |
| `ENVIRONMENT` | `development` | Runtime environment |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `OSM_PLACE_NAME` | `Manhattan, New York, USA` | OSMnx place query for road graph |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5` | Min score to open an incident |

---

## Hackathon Context

Built for the **2026 AI Hackathon** — "Real-World AI Systems" track.

**Team:** TrafficCopilot

**Challenge:** Design an AI-assisted decision-support system for a safety-critical domain that demonstrably keeps humans in control, provides auditable reasoning, and degrades gracefully when the AI is unavailable.

**Judging criteria addressed:**
- Technical depth — 5-layer async pipeline, pgvector RAG, Kafka event sourcing, KRaft Kafka, structured LLM outputs
- Human-in-the-loop design — no action dispatched without explicit officer approval
- Auditability — append-only audit log, SOP citations on every recommendation
- Demo-ability — `make bootstrap && make replay && make smoke` fully automated
- Production readiness — Kubernetes manifests, Prometheus metrics, fallback engine, health probes

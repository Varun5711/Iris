# TrafficCopilot — System Architecture

Version 1.2 | Last Updated: 2026-03-21

---

## 1. System Overview

TrafficCopilot is an AI-assisted Traffic Management decision-support system. It ingests real-time signals from road sensors, CCTV cameras, officer radio transcripts, and manual reports; fuses them into a coherent corridor state; and uses a retrieval-augmented LLM to generate ranked, SOP-aligned action recommendations for Traffic Management Officers (TMOs). All recommendations require explicit human approval before any action is dispatched to public-facing channels or field units.

The system is designed for a hackathon proof-of-concept but follows production-grade architectural patterns to demonstrate operability at scale.

**Key design principles:**
- Human-in-the-loop: the AI recommends, the human decides.
- SOP grounding: every recommendation is tied to a retrieved SOP document chunk via pgvector RAG.
- Speed: first recommendation delivered in under 30 seconds from incident trigger.
- Resilience: fallback rule-based engine operates if LLM API is unavailable.
- Auditability: every action, approval, and alert is immutably logged.

---

## 2. High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL DATA SOURCES                              │
│  [Loop Sensors]  [CCTV/CV]  [Officer Radio]  [CAD System]  [Waze CCP]      │
└──────────┬───────────┬──────────┬───────────────┬──────────────┬────────────┘
           │           │          │               │              │
           ▼           ▼          ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 1: INGEST                                     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  FastAPI HTTP/WS endpoints  +  Kafka Consumer (feed_replay worker)   │  │
│   │  Schema validation (TrafficEvent JSON Schema)                        │  │
│   │  Source normalisation → canonical TrafficEvent model                 │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │  Kafka topic: raw.traffic_events          │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 2: DETECTION                                    │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  incident_processor worker                                           │  │
│   │  - Multi-signal scorer (sensor speed, camera confidence, manual)     │  │
│   │  - Incident lifecycle manager (open / update / close)                │  │
│   │  - Deduplication via corridor_id + time window                       │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │  Kafka topic: detected.incidents          │
│                                  │  Redis: corridor_state:{corridor_id}      │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LAYER 3: STATE ENGINE                                  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  State aggregation per corridor:                                     │  │
│   │  - Speed index, occupancy, queue length estimate                     │  │
│   │  - Active incident list, severity tier                               │  │
│   │  - Signal plan state, diversion activation status                   │  │
│   │  Snapshot written to:                                                │  │
│   │  - Redis hash: incident_snapshot:{incident_id}  (TTL 24h)           │  │
│   │  - PostgreSQL: incidents table (persistent)                          │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 4: RECOMMENDATION ENGINE                           │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  copilot_trigger worker                                              │  │
│   │                                                                      │  │
│   │  a) Context Builder                                                  │  │
│   │     - Pulls IncidentSnapshot from Redis                              │  │
│   │     - RAG: pgvector cosine search → top-k SOP chunks                │  │
│   │     - Routing module: OSMnx shortest paths + alternatives           │  │
│   │     - Signal heuristics: compute retiming recommendations            │  │
│   │     - NLP: extract signals from radio transcript (Groq LLM call 1)  │  │
│   │                                                                      │  │
│   │  b) LLM Prompt Assembly & Inference                                  │  │
│   │     - System prompt: officer_copilot.txt                             │  │
│   │     - Task prompts: summarize_incident, generate_signal_plan,        │  │
│   │       generate_diversion, generate_alert_drafts                     │  │
│   │     - JSON-mode output enforced via Groq structured outputs          │  │
│   │     - Fallback: rule-based engine if Groq returns error or timeout  │  │
│   │                                                                      │  │
│   │  c) Policy Validation                                                │  │
│   │     - Validate LLM output against CopilotResponse JSON Schema        │  │
│   │     - Check SOP compliance flags on each action                      │  │
│   │     - Strip any actions that failed schema validation                │  │
│   │                                                                      │  │
│   │  d) Persist                                                          │  │
│   │     - Write CopilotResponse to PostgreSQL recommendations table      │  │
│   │     - Cache in Redis: recommendation:{incident_id} (TTL 1h)         │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │  Kafka topic: recommendations.pending     │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LAYER 5: APPROVAL & DISPATCH                            │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  REST API + WebSocket fanout (ws_fanout worker)                      │  │
│   │                                                                      │  │
│   │  - TMO reviews recommendation in web dashboard                       │  │
│   │  - Approve / reject individual actions or full bundle                │  │
│   │  - Approved actions dispatched to:                                   │  │
│   │      VMS controllers (NTCIP protocol adapter)                        │  │
│   │      Radio broadcast API                                             │  │
│   │      Social media API                                                │  │
│   │      Signal Management System (SCATS/SCOOT adapter)                 │  │
│   │  - All decisions written to audit_log table                          │  │
│   │  - WebSocket pushes live updates to all connected dashboards         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack Rationale

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| API framework | FastAPI (Python 3.12) | Async-native, OpenAPI auto-docs, WebSocket support, fastest Python framework for I/O-bound workloads |
| Message bus | Apache Kafka | Durable, replayable event log; enables feed replay for demo; decouples ingest from processing |
| Cache / state | Redis 7 (hashes + pub/sub) | Sub-millisecond corridor state reads; pub/sub for WebSocket fanout without polling |
| Primary DB | PostgreSQL 16 + pgvector 0.7 | Single ACID store for incidents, recommendations, audits; pgvector enables native cosine similarity for SOP RAG without a separate vector DB |
| LLM inference | Groq API (Llama 3.3 70B) | Lowest latency hosted inference for large open-weight models; token/s throughput enables < 5s LLM response; JSON mode for structured outputs |
| Routing | OSMnx + NetworkX | Open road network data; custom weight functions for congestion-aware shortest path; no vendor lock-in |
| ORM | SQLAlchemy 2.x (async) | Async sessions match FastAPI's async model; Alembic migrations |
| Schema validation | Pydantic v2 | Fast C-extension validation; integrates with FastAPI and SQLAlchemy |
| Containerisation | Docker + Docker Compose | Reproducible local dev; compose.yaml orchestrates all services |
| Monitoring | Prometheus + Grafana | Standard operator metrics (recommendation latency, approval rate, Kafka lag) |
| Frontend | Next.js 14 (React) | SSE/WebSocket for live dashboard updates; Mapbox GL for map visualisation |

---

## 4. Layer Descriptions

### 4.1 Ingest Layer

All incoming data is normalised to the canonical `TrafficEvent` model defined in `packages/shared-contracts/traffic_event.schema.json`. Events enter via:

- **HTTP POST** `/events` — for manual reports, CAD push, and Waze CCP webhook.
- **Kafka consumer** (`feed_replay` worker) — replays scenario JSON files from `data/replays/` in time order for demo purposes, or consumes a live Kafka topic in production.

Events are validated against the JSON Schema, assigned an `ingested_at` timestamp, written to the `raw_events` table, and published to the `raw.traffic_events` Kafka topic.

### 4.2 Detection Layer

The `incident_processor` worker consumes `raw.traffic_events`. For each corridor it applies a multi-signal scorer:

- **Speed index** = `speed_kmh / free_flow_kmh`. Below 0.4 scores high.
- **Camera confidence** from `CameraMetaEvent.confidence` and `lane_blocked` flag.
- **Manual report severity** from `ManualIncidentEvent.severity`.
- **Radio transcript NLP** — a lightweight Groq call to `extract_transcript_signals` extracts structured signals (incident type, lane status, injury flag) from free-text transcripts.

When the composite score exceeds `detection_confidence_threshold` (default 0.5, configurable), an Incident record is opened or updated. Deduplication uses a 5-minute tumbling window per `corridor_id`.

### 4.3 State Engine

On each incident update, the State Engine computes:

- Queue length estimate from sensor occupancy and upstream speed differential.
- Severity tier (1–3) using a decision table.
- Signal plan mismatch flag (if current plan deviates from baseline for the time of day).

The computed `IncidentSnapshot` is written to Redis (`incident_snapshot:{incident_id}`) for sub-millisecond reads by the Recommendation Engine, and persisted to PostgreSQL for the audit trail.

### 4.4 Recommendation Engine

The `copilot_trigger` worker triggers on `detected.incidents` events with severity Tier 1 or 2. It assembles a context bundle:

1. **RAG retrieval**: embeds the incident description using the Groq embedding endpoint (or a local fallback), then queries `sop_chunks` table via pgvector `<=>` cosine distance, returning the top-5 most relevant SOP paragraphs.
2. **Routing**: calls OSMnx to compute 2–3 alternative routes from the congestion point.
3. **Signal heuristics**: `signal_plans/heuristics.py` computes green time extension recommendations per intersection.
4. **LLM inference**: a single Groq API call with the assembled context, system prompt, and task prompt produces a structured `CopilotResponse` JSON.
5. **Policy validation**: the response is validated against the `recommendation.schema.json`. Failed validations fall back to the rule-based engine output.

Target latency: < 30 seconds end-to-end from incident trigger to `recommendation.pending` Kafka publish.

### 4.5 Approval Layer

The web dashboard presents the `CopilotResponse` to the TMO. Each `RecommendedAction` can be approved or rejected individually, or the officer can bulk-approve the bundle. Approved actions are dispatched to their target systems. Every approval or rejection is written to the `audit_log` table with the officer's ID, timestamp, and optional notes. WebSocket subscribers (multiple dashboard instances) receive real-time updates via the `ws_fanout` worker which subscribes to Redis pub/sub.

---

## 5. Kafka Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `raw.traffic_events` | Ingest API, feed_replay | incident_processor | All normalised incoming events |
| `detected.incidents` | incident_processor | copilot_trigger, ws_fanout | New or updated incident records |
| `recommendations.pending` | copilot_trigger | ws_fanout, REST API | Generated recommendations awaiting review |
| `alerts.approved` | Approval API | alerts publisher | Approved alert messages for dispatch |
| `audit.actions` | Approval API | audit logger | Immutable record of all officer decisions |

---

## 6. Redis Cache Keys

| Key Pattern | Type | TTL | Contents |
|-------------|------|-----|----------|
| `corridor_state:{corridor_id}` | Hash | 15 min | Latest sensor speed, occupancy, incident_id |
| `incident_snapshot:{incident_id}` | Hash | 24 h | Full IncidentSnapshot struct |
| `recommendation:{incident_id}` | JSON string | 1 h | Latest CopilotResponse for fast API reads |
| `sop_embed_cache:{text_hash}` | String | 7 days | Cached embedding vector to avoid re-embedding identical text |
| `ws:channel:{incident_id}` | Pub/Sub channel | — | Live update fan-out channel for dashboard WebSockets |
| `ratelimit:llm:{officer_id}` | String + TTL | 60 s | LLM request rate limiting per officer |

---

## 7. pgvector Usage

The `sop_chunks` table stores pre-computed embeddings of SOP document paragraphs:

```sql
CREATE TABLE sop_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sop_id      TEXT NOT NULL,          -- e.g. SOP-001
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(1536),           -- Groq text-embedding-ada-002 compatible
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON sop_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
```

At query time, the incident description is embedded and a single pgvector query returns the top-k chunks:

```sql
SELECT sop_id, chunk_index, text,
       1 - (embedding <=> $1::vector) AS relevance
FROM sop_chunks
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

This approach eliminates the need for an external vector database, keeping the deployment footprint minimal.

---

## 8. NLP Touch Points

| Location | Model Call | Purpose |
|----------|-----------|---------|
| `modules/nlp/transcript_extractor.py` | Groq Llama 3.3 70B | Extract structured signals (incident type, lane count, injuries) from free-text radio transcripts |
| `modules/nlp/intent_classifier.py` | Groq Llama 3.3 70B | Classify officer chat messages into intents (query, approve, reject, modify) |
| `modules/nlp/alert_formatter.py` | Groq Llama 3.3 70B | Generate channel-specific alert text from structured incident data + approved template |
| `modules/copilot/llm_client.py` | Groq Llama 3.3 70B | Main recommendation generation — structured JSON output via function calling |
| `workers/embedding_sync.py` | Groq Embeddings | Batch embed SOP chunks during seeding; re-embed on SOP document update |

---

## 9. Fallback Behavior

If the Groq API is unavailable or returns an error (network timeout, rate limit, invalid JSON), the `copilot_trigger` worker falls back to the rule-based engine in `modules/copilot/fallback.py`. The fallback engine uses a decision table keyed on `(severity, incident_type, lanes_blocked)` to produce a deterministic `CopilotResponse` with `fallback_mode: true`. The fallback response references hardcoded SOP IDs rather than RAG-retrieved chunks. The dashboard displays a "Fallback Mode" warning badge to inform the TMO that AI-powered reasoning was not available for this recommendation.

---

## 10. Security & Compliance

- JWT-based authentication on all API endpoints (HS256, 60-minute expiry).
- Role-based access: `tmo` role can view and approve; `supervisor` role can also modify signal plans and activate diversions; `readonly` role for monitoring dashboards.
- All traffic events and recommendations are retained for 90 days minimum for post-incident review.
- PII handling: radio transcripts may contain officer names; these are stored encrypted at rest (AES-256) and redacted in log outputs.
- The audit_log table is append-only; no UPDATE or DELETE is permitted at the application layer.

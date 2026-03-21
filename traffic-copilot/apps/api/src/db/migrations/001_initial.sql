-- =============================================================================
-- Migration 001 — Initial schema
-- TrafficCopilot: officer-in-the-loop traffic incident co-pilot
--
-- Requirements:
--   PostgreSQL >= 14
--   PostGIS extension
--   pgvector extension
--   pgcrypto extension (ships with PostgreSQL contrib)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- incidents
-- Core entity.  One incident per real-world traffic event, created either
-- manually by an officer or automatically by the detector pipeline.
-- =============================================================================
CREATE TABLE IF NOT EXISTS incidents (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    status               TEXT         NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'monitoring', 'resolved', 'false_alarm')),
    severity             TEXT         NOT NULL
                             CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description          TEXT,
    reporter_id          TEXT,
    -- PostGIS point geometry; NULL until coordinates are known
    location             GEOMETRY(Point, 4326),
    corridor_id          TEXT,
    detection_confidence FLOAT        NOT NULL DEFAULT 0.0
                             CHECK (detection_confidence >= 0.0 AND detection_confidence <= 1.0),
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS incidents_status_idx      ON incidents (status);
CREATE INDEX IF NOT EXISTS incidents_severity_idx    ON incidents (severity);
CREATE INDEX IF NOT EXISTS incidents_corridor_idx    ON incidents (corridor_id);
CREATE INDEX IF NOT EXISTS incidents_created_at_idx  ON incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS incidents_location_gist   ON incidents USING GIST (location);


-- =============================================================================
-- incident_events
-- Raw events correlated with an incident (sensor, camera, radio, manual).
-- =============================================================================
CREATE TABLE IF NOT EXISTS incident_events (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID         NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    source      TEXT         NOT NULL
                    CHECK (source IN ('sensor', 'camera', 'radio', 'manual')),
    raw_payload JSONB,
    event_time  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS incident_events_incident_id_idx ON incident_events (incident_id);
CREATE INDEX IF NOT EXISTS incident_events_source_idx      ON incident_events (source);
CREATE INDEX IF NOT EXISTS incident_events_event_time_idx  ON incident_events (event_time DESC);
-- Partial index for recent events — useful for sliding-window queries
CREATE INDEX IF NOT EXISTS incident_events_recent_idx
    ON incident_events (incident_id, event_time DESC)
    WHERE event_time > (now() - INTERVAL '24 hours');


-- =============================================================================
-- affected_segments
-- Road segments impacted by an incident, enriched with delay and congestion.
-- =============================================================================
CREATE TABLE IF NOT EXISTS affected_segments (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID    NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    osm_way_id      BIGINT  NOT NULL,
    geom            GEOMETRY(LineString, 4326),
    delay_seconds   INT     NOT NULL DEFAULT 0 CHECK (delay_seconds >= 0),
    congestion_pct  FLOAT   NOT NULL DEFAULT 0.0
                        CHECK (congestion_pct >= 0.0 AND congestion_pct <= 100.0)
);

CREATE INDEX IF NOT EXISTS affected_segments_incident_id_idx ON affected_segments (incident_id);
CREATE INDEX IF NOT EXISTS affected_segments_osm_way_id_idx  ON affected_segments (osm_way_id);
CREATE INDEX IF NOT EXISTS affected_segments_geom_gist       ON affected_segments USING GIST (geom);


-- =============================================================================
-- diversion_routes
-- Computed alternative routes associated with an incident.
-- =============================================================================
CREATE TABLE IF NOT EXISTS diversion_routes (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID         NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    route_geojson       JSONB        NOT NULL DEFAULT '{}',
    extra_minutes       FLOAT        CHECK (extra_minutes >= 0.0),
    redistribution_pct  FLOAT        CHECK (redistribution_pct >= 0.0 AND redistribution_pct <= 100.0),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS diversion_routes_incident_id_idx ON diversion_routes (incident_id);


-- =============================================================================
-- signal_plan_candidates
-- Intersection signal-timing plan candidates produced by the heuristic engine.
-- =============================================================================
CREATE TABLE IF NOT EXISTS signal_plan_candidates (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      UUID         NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    intersection_id  TEXT         NOT NULL,
    current_plan     JSONB,
    suggested_plan   JSONB,
    rationale        TEXT,
    confidence       FLOAT        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS signal_plan_candidates_incident_id_idx      ON signal_plan_candidates (incident_id);
CREATE INDEX IF NOT EXISTS signal_plan_candidates_intersection_id_idx  ON signal_plan_candidates (intersection_id);


-- =============================================================================
-- recommendations
-- AI-generated recommendations awaiting officer approval.
-- =============================================================================
CREATE TABLE IF NOT EXISTS recommendations (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      UUID         NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    rec_type         TEXT         NOT NULL
                         CHECK (rec_type IN ('signal', 'diversion', 'alert', 'composite')),
    action           TEXT,
    location         TEXT,
    expected_impact  TEXT,
    evidence_refs    JSONB        NOT NULL DEFAULT '[]',
    confidence       FLOAT        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    blocked_reason   TEXT,
    review_required  BOOLEAN      NOT NULL DEFAULT FALSE,
    status           TEXT         NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'expired')),
    -- Full prompt context snapshot for reproducibility and audit
    prompt_snapshot  JSONB,
    -- Raw LLM response for debugging and re-processing
    llm_response     JSONB,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendations_incident_id_idx ON recommendations (incident_id);
CREATE INDEX IF NOT EXISTS recommendations_status_idx      ON recommendations (status);
CREATE INDEX IF NOT EXISTS recommendations_rec_type_idx    ON recommendations (rec_type);
CREATE INDEX IF NOT EXISTS recommendations_created_at_idx  ON recommendations (created_at DESC);


-- =============================================================================
-- alerts
-- Individual channel-specific alert drafts linked to a recommendation.
-- =============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID         NOT NULL REFERENCES recommendations (id) ON DELETE CASCADE,
    channel           TEXT         NOT NULL
                          CHECK (channel IN ('vms', 'radio', 'social')),
    draft_text        TEXT         NOT NULL,
    status            TEXT         NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'approved', 'published', 'rejected')),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS alerts_recommendation_id_idx ON alerts (recommendation_id);
CREATE INDEX IF NOT EXISTS alerts_channel_idx           ON alerts (channel);
CREATE INDEX IF NOT EXISTS alerts_status_idx            ON alerts (status);


-- =============================================================================
-- approvals
-- Immutable officer approval / rejection records (append-only audit trail).
-- =============================================================================
CREATE TABLE IF NOT EXISTS approvals (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID         NOT NULL REFERENCES recommendations (id) ON DELETE CASCADE,
    officer_id        TEXT         NOT NULL,
    action            TEXT         NOT NULL
                          CHECK (action IN ('approved', 'rejected', 'modified')),
    note              TEXT,
    actioned_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS approvals_recommendation_id_idx ON approvals (recommendation_id);
CREATE INDEX IF NOT EXISTS approvals_officer_id_idx        ON approvals (officer_id);
CREATE INDEX IF NOT EXISTS approvals_actioned_at_idx       ON approvals (actioned_at DESC);


-- =============================================================================
-- audit_log
-- Append-only event log for all system actions (recommendations created,
-- approved, rejected, alerts published, etc.).
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  TEXT         NOT NULL,
    actor       TEXT,
    payload     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_event_type_idx  ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx       ON audit_log (actor);
CREATE INDEX IF NOT EXISTS audit_log_created_at_idx  ON audit_log (created_at DESC);


-- =============================================================================
-- sop_chunks
-- Standard Operating Procedure document chunks for vector similarity search.
-- Embedding dimension: 1024 (matches Groq / text-embedding-3-large outputs).
-- =============================================================================
CREATE TABLE IF NOT EXISTS sop_chunks (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,
    content     TEXT    NOT NULL,
    embedding   VECTOR(1024),
    source_file TEXT
);

-- IVFFlat index for approximate nearest-neighbour search.
-- lists=50 is appropriate for < 1 M rows; increase proportionally for larger
-- corpora (rule of thumb: sqrt(n_rows)).
CREATE INDEX IF NOT EXISTS sop_chunks_embedding_idx
    ON sop_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS sop_chunks_source_file_idx ON sop_chunks (source_file);


-- =============================================================================
-- Trigger: automatically maintain updated_at on incidents
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS incidents_updated_at ON incidents;
CREATE TRIGGER incidents_updated_at
    BEFORE UPDATE ON incidents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

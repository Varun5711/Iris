-- =============================================================================
-- Migration 002 — pgvector extended tables
-- TrafficCopilot: officer-in-the-loop traffic incident co-pilot
--
-- Depends on: 001_initial.sql (incidents table must exist)
--
-- Adds two additional vector-search tables used for:
--   incident_summaries  — semantic search over historical incident outcomes
--                         (enables few-shot evidence retrieval in the co-pilot)
--   alert_templates     — template retrieval for each channel and incident type
--                         (used by alert_formatter to ground draft generation)
-- =============================================================================

-- =============================================================================
-- incident_summaries
-- One row per resolved incident, capturing a text summary, embedding, and
-- outcome metadata so similar past incidents can be surfaced as evidence.
-- =============================================================================
CREATE TABLE IF NOT EXISTS incident_summaries (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID         NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    summary_text        TEXT         NOT NULL,
    -- 1024-dimensional embedding produced by the embedding_sync worker
    embedding           VECTOR(1024),
    -- Outcome label, e.g. 'cleared_in_target_time', 'significant_delay',
    -- 'false_alarm', 'escalated_to_major_incident'
    outcome             TEXT,
    -- Minutes from incident creation to status='resolved'; NULL if unresolved
    resolution_minutes  INT          CHECK (resolution_minutes >= 0),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ANN index — cosine similarity for semantic nearest-neighbour retrieval
CREATE INDEX IF NOT EXISTS incident_summaries_embedding_idx
    ON incident_summaries
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS incident_summaries_incident_id_idx
    ON incident_summaries (incident_id);

CREATE INDEX IF NOT EXISTS incident_summaries_outcome_idx
    ON incident_summaries (outcome)
    WHERE outcome IS NOT NULL;


-- =============================================================================
-- alert_templates
-- Pre-approved message templates used as retrieval targets when generating
-- alert drafts.  The embedding encodes the combination of channel,
-- incident_type, and template_text so semantically relevant templates can
-- be fetched even when the incident type label does not exactly match.
-- =============================================================================
CREATE TABLE IF NOT EXISTS alert_templates (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    channel        TEXT         NOT NULL
                       CHECK (channel IN ('vms', 'radio', 'social')),
    template_text  TEXT         NOT NULL,
    -- Optional incident-type tag, e.g. 'multi_vehicle_collision',
    -- 'signal_failure', 'road_works', 'flooding'
    incident_type  TEXT,
    -- 1024-dimensional embedding produced by the embedding_sync worker
    embedding      VECTOR(1024),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ANN index — cosine similarity for nearest-template retrieval
CREATE INDEX IF NOT EXISTS alert_templates_embedding_idx
    ON alert_templates
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS alert_templates_channel_idx
    ON alert_templates (channel);

CREATE INDEX IF NOT EXISTS alert_templates_incident_type_idx
    ON alert_templates (incident_type)
    WHERE incident_type IS NOT NULL;

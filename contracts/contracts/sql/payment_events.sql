-- Payment Pipeline Bronze Layer Tables
-- These tables store enriched payment events from Temporal workflows
-- Data is later batch-loaded to Iceberg for analytics
--
-- This is the source of truth for the PostgreSQL schema.
-- Any changes here should be reflected in:
--   - contracts/schemas/iceberg.py (PyArrow schemas)
--   - infrastructure/docker/payments-db/init.sql (deployment)

-- Payment events bronze table (successful processing)
CREATE TABLE IF NOT EXISTS payment_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    provider_event_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    merchant_id VARCHAR(255),
    customer_id VARCHAR(255),
    amount_cents BIGINT,
    currency VARCHAR(3),
    payment_method_type VARCHAR(50),
    card_brand VARCHAR(50),
    card_last_four VARCHAR(4),
    status VARCHAR(50),
    failure_code VARCHAR(100),
    failure_message TEXT,

    -- Enrichment data from inference service
    fraud_score DECIMAL(5,4),
    risk_level VARCHAR(20),
    retry_strategy VARCHAR(50),
    retry_delay_seconds INTEGER,

    -- Churn prediction data
    churn_score DECIMAL(5,4),
    churn_risk_level VARCHAR(20),
    days_to_churn_estimate INTEGER,

    -- Model tracking
    fraud_model_version VARCHAR(50),
    churn_model_version VARCHAR(50),

    -- Validation metadata
    validation_status VARCHAR(20) DEFAULT 'passed',
    validation_errors JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    provider_created_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    schema_version INTEGER DEFAULT 1,

    -- Tracking for batch loading to Iceberg
    loaded_to_iceberg BOOLEAN DEFAULT FALSE,
    loaded_at TIMESTAMPTZ
);

-- Quarantine table for failed/invalid events
CREATE TABLE IF NOT EXISTS payment_events_quarantine (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50),
    provider_event_id VARCHAR(255),
    original_payload JSONB NOT NULL,
    validation_errors JSONB DEFAULT '[]'::jsonb,
    failure_reason TEXT,
    source_topic VARCHAR(255),
    kafka_partition INTEGER,
    kafka_offset BIGINT,
    quarantined_at TIMESTAMPTZ DEFAULT NOW(),

    -- Review tracking
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(255),
    resolution VARCHAR(50),  -- 'reprocessed', 'discarded', 'manual_fix'

    schema_version INTEGER DEFAULT 1
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_payment_events_provider ON payment_events(provider);
CREATE INDEX IF NOT EXISTS idx_payment_events_merchant ON payment_events(merchant_id);
CREATE INDEX IF NOT EXISTS idx_payment_events_customer ON payment_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_payment_events_status ON payment_events(status);
CREATE INDEX IF NOT EXISTS idx_payment_events_ingested_at ON payment_events(ingested_at);
CREATE INDEX IF NOT EXISTS idx_payment_events_not_loaded ON payment_events(loaded_to_iceberg) WHERE NOT loaded_to_iceberg;

CREATE INDEX IF NOT EXISTS idx_quarantine_event_id ON payment_events_quarantine(event_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_not_reviewed ON payment_events_quarantine(reviewed) WHERE NOT reviewed;
CREATE INDEX IF NOT EXISTS idx_quarantine_quarantined_at ON payment_events_quarantine(quarantined_at);

-- Comments for documentation
COMMENT ON TABLE payment_events IS 'Bronze layer storage for enriched payment events from Temporal workflows';
COMMENT ON TABLE payment_events_quarantine IS 'Quarantine storage for failed/invalid payment events awaiting review';
COMMENT ON COLUMN payment_events.loaded_to_iceberg IS 'Flag for batch ETL process - marks events that have been loaded to Iceberg';

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Guidelines

**Memory & Context:**
- **Check Memory MCP at conversation start**: Always check the memory MCP at the beginning of a new conversation to retrieve user preferences, project context, and previous decisions
- **Use Context7 for technical documentation**: When checking technical documentation, syntax, or implementation details, use the Context7 MCP instead of general web search or training data

**Commit Messages:**
- Keep commit messages concise and action-focused
- Show what was done, not long explanations
- Example: `security: remove hardcoded credentials, add pre-commit hooks`

## Project Overview

This is a **mentorship learning project** focused on building an end-to-end MLOps platform. The project demonstrates production-grade data engineering patterns with a payment processing pipeline as the primary data source.

**Key Philosophy:**
- **Learn by Building**: Start with data foundation, then add ML capabilities
- **Hands-on Practice**: Manual deployment and configuration to understand each component
- **MLOps Focus**: Phase 4 (MLOps integration) is the primary learning goal
- **Portfolio Quality**: Demonstrate enterprise patterns for production systems

## Architecture

**Core Stack:**
- **Storage**: MinIO (S3-compatible) stores Parquet files
- **Catalog**: Apache Polaris (REST catalog for unified Iceberg metadata)
- **Table Format**: Apache Iceberg (ACID, schema evolution, time travel)
- **Ingestion**: Dagster with PostgresResource for batch ingestion from payment pipeline
- **Transformations**: DBT Core (SQL models) orchestrated by dagster-dbt
- **Query Engine**: Trino (distributed SQL over Iceberg)
- **BI**: Apache Superset (Phase 3+)

**Data Flow:**
```
Payment Pipeline (Primary):
Stripe Webhook --> Gateway (FastAPI) --> Kafka --> Normalizer (Python) --> Kafka
                        |                              |
                     [DLQ]                          [DLQ]
                                                       |
                                                       v
                                          Temporal Orchestrator
                                                       |
                      +--------------------------------+
                      |                                |
                      v                                v
               Inference Service                 PostgreSQL
              (Fraud/Churn/Retry)                    |
                                                     v
                                              Dagster Batch
                                                     |
                                                     v
                                         Iceberg (lakehouse.data)
                                                     |
                                                     v
                                           DBT Transformations
                                      (intermediate --> marts)
                                                     |
                                                     v
                                            Trino Queries
                                                     |
                                                     v
                                        Superset Dashboards / ML
```

**Data Layers:**
- **Bronze**: Enriched payment events from PostgreSQL (payment_events, payment_events_quarantine)
- **Intermediate**: Customer metrics, merchant metrics, daily summaries (ephemeral)
- **Marts**: Dimension tables (dim_customer, dim_merchant, dim_date) and fact tables (fct_payments, fct_daily_payments)

**Kubernetes Namespace:**
- `lakehouse` - All services (MinIO, Dagster, Trino, Polaris)

## Commands

### Makefile Commands (Preferred)

```bash
# Setup & Deployment
make check               # Verify prerequisites (kubectl, helm, cluster)
make setup               # Add/update Helm repositories
make deploy              # Deploy all services to lakehouse namespace
make destroy             # Tear down entire cluster (with confirmation)

# Status & Monitoring
make status              # Show overall cluster status
make polaris-status      # Show Polaris-specific status
make polaris-logs        # Tail Polaris logs (live)

# Port-Forwarding
make port-forward-start  # Start all port-forwards
make port-forward-stop   # Stop all port-forwards
make port-forward-status # Show active port-forwards

# Payment Pipeline (Docker Compose)
make pipeline-up         # Start full pipeline (Kafka + Gateway + Normalizer + Temporal)
make pipeline-down       # Stop full pipeline
make orchestrator-up     # Start orchestrator with Temporal
make gateway-simulator   # Start webhook simulator

# Get help
make help                # Show all available commands
```

**Quick Start:**
```bash
make check && make setup      # Verify and setup
make deploy                   # Deploy platform
make pipeline-up              # Start payment pipeline
make port-forward-start       # Access services
make status                   # Check deployment
```

### Dagster Development

```bash
cd orchestration-dagster

# Install dependencies
uv sync

# Configure environment
export POSTGRES_HOST=localhost  # For local development
export POSTGRES_USER=payments
export POSTGRES_PASSWORD=payments
export POSTGRES_DB=payments
source set_pyiceberg_env.sh    # Sets PyIceberg and Polaris config

# Run Dagster
uv run dagster dev             # Starts on http://localhost:3000

# Materialize assets
dagster asset materialize -m orchestration_dagster.definitions -a payment_events
```

### DBT Transformations

```bash
cd orchestration-dbt/dbt

dbt parse                        # Validate syntax
dbt compile                      # Generate SQL
dbt run                          # Run all models
dbt run --select tag:payments    # Payment models only
dbt run --select marts.payments  # Marts layer only
dbt test                         # Run data quality tests
dbt docs generate && dbt docs serve  # Generate documentation
```

### Testing

```bash
# orchestration-dagster tests
cd orchestration-dagster
uv run pytest

# payment-pipeline tests
cd payment-pipeline
uv run pytest tests/unit/ -v                    # All unit tests
uv run pytest tests/unit/test_gateway.py -v     # Specific test file
uv run pytest -k "fraud" -v                     # Tests matching pattern

# Linting (payment-pipeline)
uv run ruff check .
uv run ruff format .
```

### Trino Queries

```bash
# Connect to Trino
kubectl exec -n lakehouse deployment/trino-coordinator -- trino

# Example queries
SHOW SCHEMAS FROM lakehouse;
SHOW TABLES FROM lakehouse.data;
SELECT COUNT(*) FROM lakehouse.data.payment_events;
SELECT * FROM lakehouse.data.dim_customer LIMIT 10;
```

## Key Architectural Decisions

### Payment Pipeline as Primary Data Source

The payment pipeline is the primary data source:
- **Gateway**: Webhook ingestion with signature verification
- **Normalizer**: Validation and schema normalization
- **Orchestrator**: Temporal workflows with ML inference enrichment
- **PostgreSQL Bronze Layer**: Enriched events with fraud_score, churn_score, retry_strategy

### Dagster-DBT Integration

DBT models are orchestrated as Dagster assets using `dagster-dbt`:
- Automatic asset dependency mapping
- DBT tests run as part of materialization
- Unified lineage view in Dagster UI

### Star Schema Design (Marts Layer)

**Dimensional modeling** for analytics:
- **Dimension tables**: `dim_customer`, `dim_merchant`, `dim_date`
- **Fact tables**: `fct_payments`, `fct_daily_payments`
- **Surrogate keys**: Use `dbt_utils.generate_surrogate_key()` for dimension PKs
- **SCD Type 2**: Track historical changes with `valid_from`, `valid_to`, `is_current`

### Same-Namespace Service Communication

**All services in `lakehouse` namespace** - uses simplified Kubernetes DNS:
- MinIO S3 API: `minio:9000`
- Trino: `trino:8080`
- Polaris REST API: `polaris:8181`
- Payments PostgreSQL: `payments-db:5432`

## File Structure

### orchestration-dagster Structure

```
orchestration-dagster/
├── src/orchestration_dagster/
│   ├── definitions.py          # Asset/job/resource/schedule definitions
│   ├── resources/
│   │   ├── iceberg.py          # Iceberg IO manager
│   │   ├── postgres.py         # PostgreSQL resource for payment ingestion
│   │   ├── trino.py            # Trino query resource
│   │   └── dbt.py              # dagster-dbt integration
│   └── sources/
│       ├── payment_ingestion.py  # PostgreSQL -> Iceberg assets
│       └── payments.py           # Data quality monitoring assets
├── pyproject.toml              # Dependencies
└── set_pyiceberg_env.sh        # Environment setup
```

### DBT Project Structure

```
orchestration-dbt/dbt/
├── dbt_project.yml             # Project config: lakehouse_analytics
├── profiles.yml                # Trino connection
├── macros/
│   └── payment_macros.sql      # customer_tier, risk_profile, etc.
└── models/
    ├── sources.yml             # Bronze payment tables
    ├── staging/payments/       # (legacy, from Flink)
    ├── intermediate/payments/  # Customer/merchant metrics
    │   ├── int_payment_customer_metrics.sql
    │   ├── int_payment_merchant_metrics.sql
    │   └── int_payment_daily_summary.sql
    └── marts/payments/         # Star schema
        ├── dim_customer.sql
        ├── dim_merchant.sql
        ├── dim_date.sql
        ├── fct_payments.sql
        └── fct_daily_payments.sql
```

## Important Patterns

### Payment Pipeline Architecture

**Components:**
- **Gateway** (FastAPI): Webhook receiver with HMAC-SHA256 signature verification
- **Normalizer** (Python + aiokafka): ISO 4217 validation, null normalization, unified schema
- **Orchestrator** (Temporal): Durable workflow execution with per-activity retry policies

**Kafka Topics:**
- Input: `webhooks.stripe.payment_intent`, `webhooks.stripe.charge`, `webhooks.stripe.refund`
- Output: `payments.normalized`
- DLQ: `payments.validation.dlq`

See `payment-pipeline/CLAUDE.md` for detailed payment pipeline guidance.

### Dagster PostgreSQL Ingestion

```python
@asset(
    key_prefix=["data"],
    io_manager_key="iceberg_io_manager",
    metadata={"partition_expr": "ingested_at"},
    group_name="payment_ingestion",
)
def payment_events(context, postgres_resource: PostgresResource) -> pd.DataFrame:
    events = postgres_resource.get_unloaded_events(table="payment_events")
    df = pd.DataFrame(events)
    # ... prepare for Iceberg
    postgres_resource.mark_as_loaded("payment_events", event_ids)
    return df
```

### DBT Payment Macros

```sql
-- Customer tier classification
{{ customer_tier('total_revenue_cents') }}  -- Returns: platinum/gold/silver/bronze

-- Risk profile based on failure rate
{{ risk_profile('failure_rate') }}  -- Returns: high_risk/medium_risk/low_risk

-- Currency conversion
{{ cents_to_dollars('amount_cents') }}  -- Returns: DECIMAL amount in dollars

-- Merchant health score
{{ merchant_health_score('dispute_rate', 'refund_rate', 'failure_rate') }}
```

## Current Phase Status

**Phase 1 (Foundation):** Complete
- Kubernetes infrastructure, MinIO, Dagster, Trino, Polaris

**Phase 2 (Analytics):** Complete
- Payment pipeline (Gateway + Normalizer + Temporal Orchestrator)
- Dagster PostgreSQL ingestion to Iceberg
- dagster-dbt integration
- DBT star schema (dim_customer, dim_merchant, fct_payments)

**Phase 3 (Governance & BI):** In Progress
- Polaris REST catalog deployed
- Apache Superset dashboards (planned)
- RBAC and data lineage tracking (planned)

**Phase 4 (MLOps):** Planned
- Feast feature store for customer/merchant features
- ML model training (fraud, churn, retry)
- Kubeflow pipelines

## Troubleshooting

### PostgreSQL Connection Failed

**Symptom:** Dagster asset fails with "PostgreSQL connection failed"
**Fix:**
```bash
# Check PostgreSQL is running
docker compose ps payments-db

# Verify connection
export POSTGRES_HOST=localhost
export POSTGRES_USER=payments
export POSTGRES_PASSWORD=payments
export POSTGRES_DB=payments
```

### Cannot Connect to Polaris Catalog

```bash
# Check Polaris is running
make polaris-status

# Start port-forward
make port-forward-start

# Test connection
curl http://localhost:8181/api/catalog/v1/config
```

### DBT Model Fails

```bash
# Check Trino connection
cd orchestration-dbt/dbt
dbt debug

# Run specific model with verbose output
dbt run --select fct_payments --full-refresh
```

## References

**Payment Pipeline:**
- [payment-pipeline/CLAUDE.md](payment-pipeline/CLAUDE.md) - Payment pipeline specific guidance
- [payment-pipeline/README.md](payment-pipeline/README.md) - Gateway, Normalizer, Orchestrator docs

**Dagster Integration:**
- [orchestration-dagster/README.md](orchestration-dagster/README.md)

**Architecture:**
- [infrastructure/README.md](infrastructure/README.md) - Component docs
- [docs/guides/payment-pipeline.md](docs/guides/payment-pipeline.md) - Full system design

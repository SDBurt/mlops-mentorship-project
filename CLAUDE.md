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

This is a **mentorship learning project** focused on building an end-to-end MLOps platform. The journey starts with foundational data engineering (batch pipelines, dimensional modeling) and progressively integrates MLOps capabilities (feature stores, model training, model serving).

**Key Philosophy:**
- **Learn by Building**: Start with data foundation, then add ML capabilities
- **Hands-on Practice**: Manual deployment and configuration to understand each component
- **MLOps Focus**: Phase 4 (MLOps integration) is the primary learning goal
- **Progress Tracking**: README.md contains weekly learning progress sections
- **Portfolio Quality**: Demonstrate enterprise patterns for production systems

**Important:** This is a mentorship project. Follow the phased approach in README.md and track progress weekly.

## Architecture

**Core Stack:**
- **Storage**: MinIO (S3-compatible) stores Parquet files
- **Catalog**: Apache Polaris (REST catalog for unified Iceberg metadata)
- **Table Format**: Apache Iceberg (ACID, schema evolution, time travel)
- **Ingestion**: dagster-iceberg with PRAW for Reddit data extraction
- **Transformations**: DBT Core (SQL models) orchestrated by Dagster
- **Query Engine**: Trino (distributed SQL over Iceberg)
- **BI**: Apache Superset (Phase 2+)

**Data Flow:**
```
Reddit API → PRAW → Dagster Assets → dagster-iceberg → Polaris Catalog
                                                              ↓
                                                        MinIO/S3 (Iceberg)
                                                              ↓
                                                         Trino Query
                                                              ↓
                                                    Single 'data' Namespace
                                          (organized by table naming conventions)
```

**Data Layers:**
- **Raw**: Ingested data from sources (minimal transformation)
- **Staging**: Cleaned, typed, and deduplicated data
- **Intermediate**: Business logic transformations (reusable models)
- **Marts**: Final business-facing models (star schema, aggregations)

**Kubernetes Namespace:**
- `lakehouse` - All services (MinIO, Dagster, Trino, Polaris)

## Commands

### Makefile Commands (Preferred)

The project includes a comprehensive Makefile for common operations:

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

# Port-Forwarding (runs in background)
make port-forward-start  # Start all port-forwards
make port-forward-stop   # Stop all port-forwards
make port-forward-status # Show active port-forwards

# Service Restarts
make restart-dagster     # Restart Dagster deployments
make restart-trino       # Restart Trino deployments
make restart-polaris     # Restart Polaris deployment
make restart-all         # Restart all services

# Migration Commands (one-time use)
make clean-nessie        # Remove Nessie (if migrating from Nessie)
make clean-old           # Remove old separate namespaces

# Get help
make help                # Show all available commands
```

**Quick Start:**
```bash
make check && make setup      # Verify and setup
make deploy                   # Deploy platform
make port-forward-start       # Access services
make status                   # Check deployment
```

### Manual Kubernetes Commands

If not using Makefile:

```bash
# Deployment (order matters - see SETUP_GUIDE.md)
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# 1. MinIO (storage)
kubectl apply -f infrastructure/kubernetes/minio/minio-standalone.yaml -n lakehouse

# 2. Dagster (orchestration with embedded PostgreSQL)
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n lakehouse --wait --timeout 10m

# 3. Trino (query engine)
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --wait --timeout 10m

# 4. Polaris (REST catalog)
kubectl apply -f infrastructure/kubernetes/polaris/secrets.yaml
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### Dagster Development

**Working with orchestration-dagster:**

```bash
cd orchestration-dagster

# Install dependencies
uv sync                          # Using uv (recommended)
# or
pip install -e ".[dev]"          # Using pip

# Configure environment
source set_pyiceberg_env.sh      # Sets PyIceberg and Polaris config

# Create .env file with Reddit credentials
cat > .env <<EOF
REDDIT_CLIENT_ID="your_client_id"
REDDIT_CLIENT_SECRET="your_client_secret"
REDDIT_USER_AGENT="lakehouse:v1.0.0 (by /u/your_username)"
EOF

# Run Dagster
uv run dagster dev               # Starts on http://localhost:3000

# Materialize assets
dagster asset materialize -m orchestration_dagster.definitions -a reddit_posts
```

### DBT Transformations

```bash
# From transformations/dbt/ directory

dbt parse                        # Validate syntax
dbt compile                      # Generate SQL
dbt run                          # Run all models
dbt run --select staging.*       # Staging layer only
dbt run --select intermediate.*  # Intermediate layer only
dbt run --select marts.*         # Marts layer only
dbt test                         # Run data quality tests
dbt docs generate && dbt docs serve  # Generate documentation
```

**Important:** DBT models are example templates. Do not run until data sources are configured and ingested.

### Trino Queries

```bash
# Connect to Trino (via port-forward or in-cluster)
kubectl exec -n lakehouse deployment/trino-coordinator -- trino

# Example queries
SHOW SCHEMAS FROM lakehouse;
SHOW TABLES FROM lakehouse.raw;
SELECT COUNT(*) FROM lakehouse.raw.reddit_posts;
```

## Key Architectural Decisions

### Polaris REST Catalog (Not Nessie)

**The project uses Apache Polaris** as the REST catalog for Iceberg:
- Simpler authentication (basic auth vs token-based)
- Tighter integration with Iceberg REST specification
- Built-in RBAC and governance features
- Sufficient for Phase 1-3 requirements

**Endpoints:**
- Cluster: `http://polaris:8181/api/catalog`
- Port-forward: `http://localhost:8181`

**If you see Nessie references**, they are outdated. The project migrated from Nessie to Polaris.

### dagster-iceberg with PRAW (Not DLT)

**Data ingestion uses dagster-iceberg** IO manager:
- **PRAW**: Python Reddit API Wrapper for data extraction
- **dagster-iceberg**: Official Dagster integration for Iceberg
- **Dual Backend Support**:
  - **Pandas** (default): Best for learning, small-to-medium datasets
  - **PyArrow** (optional): Best for performance, large datasets (2-3x faster)

**Project Location:** `orchestration-dagster/` (not `ingestion/dlt/`)

**Backend Selection:**
```python
# Pandas backend (default)
resources={
    "iceberg_io_manager": create_iceberg_io_manager(backend="pandas")
}

# PyArrow backend (for performance)
resources={
    "iceberg_io_manager": create_iceberg_io_manager(backend="pyarrow")
}
```

See `orchestration-dagster/BACKEND_COMPARISON.md` for detailed comparison.

### Same-Namespace Service Communication

**All services in `lakehouse` namespace** - uses simplified Kubernetes DNS:

**Pattern:** `<service-name>:<port>` (within same namespace)

**Examples:**
- MinIO S3 API: `minio:9000`
- Trino: `trino:8080` (full: `trino.lakehouse.svc.cluster.local:8080`)
- Dagster PostgreSQL: `dagster-postgresql:5432`
- Polaris REST API: `polaris:8181`

**Usage:**
- Trino → MinIO: `s3.endpoint=http://minio:9000`
- Trino → Polaris: `iceberg.rest.uri=http://polaris:8181/api/catalog`
- dagster-iceberg → Polaris: Uses `PYICEBERG_CATALOG__DEFAULT__URI`

### Secret Management

**All secrets externalized** to separate Secret resources (gitignored via comprehensive patterns in `.gitignore`).

**Secret Management Approach:**
- All secrets stored in Kubernetes Secret resources (not committed to git)
- `.example` template files provided for each secret type
- Credentials injected via environment variables or volume mounts
- Pre-commit hooks prevent accidental credential commits

**Setup Secrets:**
1. Copy `.example` files: `cp *-secrets.yaml.example *-secrets.yaml`
2. Edit and replace placeholders with actual values
3. Apply to cluster: `kubectl apply -f *-secrets.yaml`

**See SECURITY.md for complete setup instructions.**

**Generate secrets:**
```bash
openssl rand -base64 32              # Random password
echo -n "password" | base64          # Base64 encode for K8s
echo "base64-string" | base64 -d     # Decode to verify
```

### Star Schema Design (Marts Layer)

**Dimensional modeling** for analytics:
- **Fact tables**: `fct_orders` (measures, foreign keys to dimensions)
- **Dimension tables**: `dim_customer`, `dim_product`, `dim_date`
- **Surrogate keys**: Use `dbt_utils.surrogate_key()` for dimension PKs
- **SCD Type 2**: Track historical changes with `valid_from`, `valid_to`, `is_current`

### Monorepo Domain Separation

**Team domains prevent conflicts:**
- `infrastructure/` - Platform/DevOps (Helm charts, K8s manifests, Makefile)
- `transformations/` - Analytics engineering (DBT models)
- `lakehouse/` - Data architecture (Iceberg schemas, conventions)
- `orchestration-dagster/` - Data engineering (Dagster + dagster-iceberg pipelines)
- `analytics/` - BI/Analytics (Superset dashboards) - Phase 2+
- `ml/` - ML engineering (Feast, Kubeflow, DVC) - Phase 4

## File Structure

### Infrastructure Configuration

**Helm values pattern:**
- `values.yaml` - Custom overrides (actively edited)
- `values-default.yaml` - Complete defaults from upstream (reference only)

**Only edit `values.yaml`** - keep minimal with necessary overrides only.

### orchestration-dagster Structure

```
orchestration-dagster/
├── src/orchestration_dagster/
│   ├── definitions.py          # Asset/job/resource definitions
│   ├── resources/
│   │   └── iceberg.py         # Iceberg IO manager (Pandas + PyArrow)
│   └── sources/
│       ├── reddit.py          # Pandas backend assets
│       └── reddit_pyarrow.py  # PyArrow backend assets (optional)
├── iceberg_config.yaml        # Polaris catalog configuration
├── set_pyiceberg_env.sh       # Environment variable setup
├── pyproject.toml             # Dependencies (uv or pip)
├── BACKEND_COMPARISON.md      # Pandas vs PyArrow guide
├── IMPLEMENTATION_SUMMARY.md  # Setup and configuration guide
└── README.md                  # Quick start
```

### DBT Project Structure

```
transformations/dbt/
├── dbt_project.yml         # Project config: lakehouse_analytics
├── profiles.yml            # Trino connection (lakehouse database)
└── models/
    ├── sources.yml         # Raw table definitions
    ├── staging/            # Cleaned, typed data (stg_*)
    ├── intermediate/       # Business logic transformations (int_*)
    └── marts/              # Business-facing models (dim_*, fct_*)
```

## Important Patterns

### Iceberg Table Creation (via Trino)

```sql
CREATE TABLE lakehouse.raw.reddit_posts (
    id VARCHAR,
    subreddit VARCHAR,
    title VARCHAR,
    score BIGINT,
    created_utc TIMESTAMP
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['month(created_utc)'],
    location = 's3://lakehouse/warehouse/raw/reddit_posts/'
)
```

### dagster-iceberg Asset (Pandas)

```python
from dagster import asset
import pandas as pd

@asset(
    key_prefix=["raw", "reddit"],
    io_manager_key="iceberg_io_manager",
    metadata={"partition_expr": "created_utc"},
    group_name="reddit_ingestion",
)
def reddit_posts(context) -> pd.DataFrame:
    # Extract data using PRAW
    data = extract_reddit_posts()
    df = pd.DataFrame(data)
    return df  # dagster-iceberg handles persistence
```

### DBT Incremental Model (Iceberg)

```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg',
    incremental_strategy='merge',
    partition_by=['month(valid_from)']
  )
}}

SELECT
    {{ dbt_utils.surrogate_key(['customer_id', 'valid_from']) }} as customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    updated_at as valid_from,
    NULL as valid_to,
    TRUE as is_current
FROM {{ source('raw', 'customers') }}

{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(valid_from) FROM {{ this }})
{% endif %}
```

## Current Phase Status

**Phase 1 (Foundation):** ✅ Complete
- Kubernetes infrastructure
- MinIO S3 storage
- Dagster deployment
- Trino deployment
- Polaris REST catalog deployed
- Makefile automation
- Comprehensive documentation

**Phase 2 (Analytics):** 🔄 In Progress
- ✅ dagster-iceberg integration
- ✅ PRAW Reddit data source
- ✅ Dual backend support (Pandas + PyArrow)
- ⏳ Verify end-to-end data flow
- ⏳ DBT model implementation
- ⏳ Superset deployment (optional)

**Phase 3 (Governance):** Ready to Start
- ✅ Polaris deployed
- ⏳ RBAC setup
- ⏳ Data lineage tracking
- ⏳ Audit logging

**Phase 4 (MLOps):** Planned
- Feast feature store
- Kubeflow ML platform
- DVC data versioning

## Common Workflows

### Adding a New Data Source

1. Create source file in `orchestration-dagster/src/orchestration_dagster/sources/<source>.py`
2. Define assets using `@asset` decorator
3. Return `pd.DataFrame` (Pandas) or `pa.Table` (PyArrow)
4. Add assets to `definitions.py`
5. Set `io_manager_key="iceberg_io_manager"`
6. Add metadata: `{"partition_expr": "timestamp_column"}`

Example:
```python
@asset(
    key_prefix=["raw", "my_source"],
    io_manager_key="iceberg_io_manager",
    metadata={"partition_expr": "created_at"},
)
def my_data(context) -> pd.DataFrame:
    data = fetch_data()
    return pd.DataFrame(data)
```

### Switching Backend (Pandas ↔ PyArrow)

**In `definitions.py`:**
```python
# Change from Pandas to PyArrow
resources={
    "iceberg_io_manager": create_iceberg_io_manager(
        namespace="raw",
        backend="pyarrow"  # Was: "pandas"
    ),
}

# Import PyArrow assets
from .sources.reddit_pyarrow import reddit_posts_pyarrow
```

**Update asset return type:**
```python
import pyarrow as pa

@asset(...)
def my_asset(context) -> pa.Table:  # Was: pd.DataFrame
    data = fetch_data()
    return pa.Table.from_pylist(data)  # Was: pd.DataFrame(data)
```

### Debugging Failed Deployments

```bash
# Use Makefile commands
make status                      # Quick overview
make polaris-status              # Check Polaris specifically
make polaris-logs                # View live logs

# Manual debugging
kubectl get pods -n lakehouse
kubectl describe pod <pod-name> -n lakehouse
kubectl logs <pod-name> -n lakehouse --tail=100 -f

# Test service connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -n lakehouse -- \
  nslookup polaris
```

## Troubleshooting

### Polaris Database Warnings

**Symptom:** Logs show database connection warnings
**Status:** Known, non-blocking for development
**Fix (if needed):** Check `infrastructure/kubernetes/polaris/secrets.yaml` for database credentials

### Reddit Credentials Not Found

**Symptom:** Asset materialization fails with "Reddit credentials not found"
**Fix:**
```bash
cd orchestration-dagster
cat > .env <<EOF
REDDIT_CLIENT_ID="your_id"
REDDIT_CLIENT_SECRET="your_secret"
REDDIT_USER_AGENT="your_agent"
EOF
source set_pyiceberg_env.sh
```

### Cannot Connect to Polaris Catalog

**Fix:**
```bash
# Check Polaris is running
make polaris-status

# Start port-forward
make port-forward-start

# Test connection
curl http://localhost:8181/api/catalog/v1/config
```

### Trino Cannot Access MinIO S3

**Check:**
1. MinIO service running: `kubectl get svc -n lakehouse minio`
2. Trino catalog config: S3 endpoint = `http://minio:9000`
3. Path style access: Must be `true` for MinIO
4. Credentials match MinIO values.yaml

## References

**Setup & Deployment:**
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete deployment walkthrough
- [TEARDOWN.md](TEARDOWN.md) - Clean cluster teardown
- [Makefile](Makefile) - Automation commands

**Recent Migration:**
- [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) - Nessie → Polaris migration details
- [MAKEFILE_UPDATES.md](MAKEFILE_UPDATES.md) - New Makefile commands
- [POLARIS_DAGSTER_SETUP.md](POLARIS_DAGSTER_SETUP.md) - Complete setup guide

**Dagster Integration:**
- [orchestration-dagster/IMPLEMENTATION_SUMMARY.md](orchestration-dagster/IMPLEMENTATION_SUMMARY.md)
- [orchestration-dagster/BACKEND_COMPARISON.md](orchestration-dagster/BACKEND_COMPARISON.md)
- [orchestration-dagster/README.md](orchestration-dagster/README.md)

**Architecture:**
- [infrastructure/README.md](infrastructure/README.md) - Component docs
- [docs/topics/polaris-rest-catalog.md](docs/topics/polaris-rest-catalog.md)
- [docs/topics/dagster.md](docs/topics/dagster.md)
- [docs/topics/apache-iceberg.md](docs/topics/apache-iceberg.md)

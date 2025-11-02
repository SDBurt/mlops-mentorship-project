# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **mentorship learning project** focused on building an end-to-end MLOps platform. The journey starts with foundational data engineering (batch pipelines, dimensional modeling) and progressively integrates MLOps capabilities (feature stores, model training, model serving).

**Key Philosophy:**
- **Learn by Building**: Start with data foundation, then add ML capabilities
- **Hands-on Practice**: Manual deployment and configuration to understand each component
- **MLOps Focus**: Phase 4 (MLOps integration) is the primary learning goal
- **Progress Tracking**: README.md contains weekly learning progress sections
- **Portfolio Quality**: Demonstrate enterprise patterns for production systems

**Important:** This is a mentorship project. Follow the phased approach in README.md and track progress weekly. DBT models are example templates - not ready until data sources configured.

## Architecture

**Core Stack:**
- **Storage**: MinIO (S3-compatible) stores Parquet files
- **Table Format**: Apache Iceberg (ACID, schema evolution, time travel)
- **Ingestion**: Meltano (Singer taps/targets) for ELT pipelines
- **Transformations**: DBT Core (SQL models) orchestrated by Dagster
- **Query Engine**: Trino (distributed SQL over Iceberg)
- **BI**: Apache Superset (Phase 2+)

**Data Flow:**
```
Data Sources → Meltano (Singer Taps) → MinIO/S3 (Parquet)
                                              ↓
                                      Iceberg Tables
                                              ↓
                                    Trino ← DBT (Dagster)
                                              ↓
                                    Bronze → Silver → Gold
```

**Medallion Layers:**
- **Bronze**: Raw staging (views of ingested data)
- **Silver**: Cleaned dimensions (incremental Iceberg tables)
- **Gold**: Business facts (star schema for analytics)

**Kubernetes Namespace:**
- `lakehouse` - All services (MinIO, Dagster, Trino)

## Commands

### Deployment

**Always refer users to:** [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete step-by-step deployment.

Quick reference (see SETUP_GUIDE.md for full context):

```bash
# Prerequisites
helm repo add dagster https://dagster-io.github.io/helm
helm repo add trino https://trinodb.github.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Create lakehouse namespace
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# Deploy services to lakehouse namespace (order matters - see SETUP_GUIDE.md)
# 1. MinIO (storage)
kubectl apply -f infrastructure/kubernetes/minio/minio-standalone.yaml \
  -f infrastructure/kubernetes/minio/values.yaml \
  -n lakehouse --wait

# 2. Dagster (orchestration - includes embedded PostgreSQL)
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n lakehouse --wait --timeout 10m

# 3. Trino (query engine)
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### Teardown

**Refer users to:** [TEARDOWN.md](TEARDOWN.md) for complete teardown process.

Quick reference:
```bash
# Uninstall Helm releases
helm uninstall dagster -n lakehouse
helm uninstall trino -n lakehouse
kubectl delete -f infrastructure/kubernetes/minio/minio-standalone.yaml

# Delete namespace
kubectl delete namespace lakehouse
```

### Check Status

```bash
# All pods in lakehouse namespace
kubectl get pods -n lakehouse

# All services
kubectl get svc -n lakehouse

# Helm releases in lakehouse namespace
helm list -n lakehouse

# Pod logs
kubectl logs -n lakehouse <pod-name> --tail=100 -f
```

### Port-Forward Services

**Note:** Port-forward blocks the terminal. Open separate terminals for each service.

```bash
# Dagster UI (separate terminal)
kubectl port-forward -n lakehouse svc/dagster-dagster-webserver 3000:80

# Trino UI (separate terminal)
kubectl port-forward -n lakehouse svc/trino 8080:8080

# MinIO S3 API (separate terminal)
kubectl port-forward -n lakehouse svc/minio 9000:9000

# MinIO Console (separate terminal)
kubectl port-forward -n lakehouse svc/minio 9001:9001
```

Access:
- Dagster: http://localhost:3000
- Trino: http://localhost:8080
- MinIO API: http://localhost:9000
- MinIO Console: http://localhost:9001

### MinIO S3 Operations

**Note:** MinIO automatically creates the default bucket specified in values.yaml.

```bash
# Get MinIO credentials (from values.yaml or secrets)
# Default: admin / minio123

# Access MinIO Console at http://localhost:9001
# Or use MinIO Client (mc)

# Install mc (MinIO Client)
# https://min.io/docs/minio/linux/reference/minio-mc.html

# Configure mc alias
mc alias set myminio http://localhost:9000 admin minio123

# List buckets
mc ls myminio

# Create bucket (if not using defaultBuckets in values.yaml)
mc mb myminio/lakehouse

# Upload file
mc cp myfile.parquet myminio/lakehouse/

# List objects in bucket
mc ls myminio/lakehouse
```

### DBT Transformations

```bash
# From transformations/dbt/ directory

# Parse project (validate syntax)
dbt parse

# Compile SQL (dry run - check generated SQL)
dbt compile

# Run models
dbt run                        # All models
dbt run --select bronze.*      # Bronze layer only
dbt run --select silver.*      # Silver layer only
dbt run --select gold.*        # Gold layer only
dbt run --select stg_customers # Single model

# Test data quality
dbt test                       # All tests
dbt test --select bronze.*     # Layer tests

# Generate and serve documentation
dbt docs generate && dbt docs serve
```

**Important:** DBT models in `transformations/dbt/models/` are example templates. Do not run until:
1. Data sources configured and ingested
2. Raw Iceberg tables created in MinIO S3
3. `sources.yml` updated with actual table names

### Meltano ELT Pipelines

```bash
# From ingestion/meltano/ directory

# Initialize Meltano project
meltano init lakehouse-ingestion

# Add extractors (taps)
meltano add extractor tap-postgres
meltano add extractor tap-github
meltano add extractor tap-stripe

# Add loaders (targets)
meltano add loader target-parquet

# Configure plugins
meltano config tap-postgres set --interactive
meltano config target-parquet set filepath s3://lakehouse/raw/

# Test extraction
meltano invoke tap-postgres

# Run ELT job (tap | target)
meltano run tap-postgres target-parquet

# View installed plugins
meltano list plugins

# Check plugin configuration
meltano config tap-postgres list

# Manage state
meltano state list
meltano state get tap-postgres target-parquet
meltano state set tap-postgres target-parquet '{"bookmarks":{}}'

# Run with Dagster orchestration
dagster dev -f dagster_defs.py
```

**Important:** Meltano configuration is stored in `meltano.yml`. Use environment variables for secrets, never hardcode in config files.

## Key Architectural Decisions

### Terminology: "Lakehouse" vs "Data Lake"

**Use "lakehouse" in naming** (databases, profiles, project names):
- `database: lakehouse` in Trino connections
- `profile: lakehouse` in DBT profiles
- `project: lakehouse_analytics` in DBT

**Why?** Reflects the vision - governance (Phase 3 with Apache Polaris) will transform the data lake into a true lakehouse with unified catalog, RBAC, and audit trails.

### Same-Namespace Service Communication

**All services in same `lakehouse` namespace** - uses simplified Kubernetes DNS:

**Pattern:** `<service-name>:<port>` (within same namespace)

**Examples:**
- MinIO S3 API: `minio:9000`
- Trino: `trino.trino.svc.cluster.local:8080`
- Dagster PostgreSQL (embedded): `dagster-postgresql.dagster.svc.cluster.local:5432`

**Usage:**
- Trino connects to Garage: `s3.endpoint=http://minio:9000`
- DBT connects to Trino: `host=trino.trino.svc.cluster.local`

### Secret Management

**All secrets externalized** to `secrets.yaml` files (gitignored via `**/*/secrets.yaml` pattern).

**Note:**
- MinIO credentials are configured in `values.yaml` (change for production)
- PostgreSQL credentials for Dagster are configured in `values.yaml` (embedded database)

**Never hardcode secrets** in `values.yaml` files.

**Generate secrets:**
```bash
# Random password
openssl rand -base64 32

# Encode for Kubernetes (base64)
echo -n "your-password" | base64

# Decode to verify
echo "base64-string" | base64 -d
```

**Secret Format:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <service>-secret
  namespace: lakehouse
type: Opaque
data:
  # Base64 encoded values
  password: <base64-encoded-password>
stringData:
  # Plain text (Kubernetes encodes automatically)
  username: myuser
```

### DBT Models as Templates

All DBT models in `transformations/dbt/models/` are **example templates**:
- Clearly marked as "EXAMPLE TEMPLATE - NOT READY FOR USE"
- Show patterns for Bronze/Silver/Gold layers
- Demonstrate star schema (fact + dimension tables)
- Include SCD Type 2 patterns

**Do not run** until:
1. Data sources configured and ingested
2. Raw Iceberg tables created
3. `sources.yml` updated with actual table names

### Star Schema Design (Gold Layer)

**Dimensional modeling** for analytics:
- **Fact tables**: `fct_orders` (measures, foreign keys to dimensions)
- **Dimension tables**: `dim_customer`, `dim_product`, `dim_date`
- **Surrogate keys**: Use `dbt_utils.surrogate_key()` for dimension PKs
- **SCD Type 2**: Track historical changes with `valid_from`, `valid_to`, `is_current`

### Monorepo Domain Separation

**Team domains prevent conflicts:**
- `infrastructure/` - Platform/DevOps (Helm charts, K8s manifests, secrets)
- `transformations/` - Analytics engineering (DBT models)
- `lakehouse/` - Data architecture (Iceberg schemas, conventions)
- `orchestration/` - Data engineering (Dagster pipelines)
- `analytics/` - BI/Analytics (Superset dashboards) - Phase 2+
- `ml/` - ML engineering (Feast, Kubeflow, DVC) - Phase 4

Teams work independently in their domains with minimal cross-domain changes.

## File Structure Notes

### Infrastructure Configuration

**Helm values pattern:**
- `values.yaml` - Custom overrides (actively edited)
- `values-default.yaml` - Complete defaults from upstream (reference only, never edit)

**Only edit `values.yaml`** - keep it minimal with necessary overrides only.

### DBT Project Structure

```
transformations/dbt/
├── dbt_project.yml         # Project config: lakehouse_analytics
├── profiles.yml            # Trino connection (lakehouse database)
└── models/
    ├── sources.yml         # Raw table definitions (update for your sources)
    ├── bronze/             # Staging views (stg_*)
    │   ├── stg_customers.sql
    │   ├── stg_orders.sql
    │   └── stg_products.sql
    ├── silver/             # Dimensions (dim_*)
    │   ├── dim_customer.sql
    │   ├── dim_product.sql
    │   └── dim_date.sql
    └── gold/               # Facts (fct_*)
        └── fct_orders.sql
```

## Important Patterns

### Iceberg Table Creation (via Trino)

```sql
CREATE TABLE lakehouse.analytics.dim_customer (
    customer_key BIGINT,
    customer_id STRING,
    email STRING,
    first_name STRING,
    last_name STRING,
    -- SCD Type 2 columns
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['month(valid_from)'],
    location = 's3://lakehouse/warehouse/analytics/dim_customer/'
)
```

### DBT Incremental Models (Iceberg)

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

### MinIO S3 Configuration (for Trino/DBT)

```yaml
# In Trino catalog properties or DBT profiles
s3:
  endpoint: http://minio:9000  # Same namespace - simplified DNS
  path-style-access: true  # Required for MinIO
  aws-access-key-id: admin  # From MinIO values.yaml
  aws-secret-access-key: minio123  # From MinIO values.yaml
  region: us-east-1  # Default region for MinIO
```

## Iceberg Table Format Strategy

**Iceberg is configured in phases:**

### Phase 2: Direct Iceberg Table Creation
- **Approach**: Create Iceberg tables directly via Trino SQL or programmatically
- **Catalog**: Hadoop catalog (filesystem-based) or REST catalog (Apache Polaris)
- **Setup**: Configure Trino Iceberg connector pointing to MinIO S3
- **Output**: Iceberg tables written to `s3://lakehouse/warehouse/`
- **Access**: Trino reads/writes Iceberg tables using the configured catalog

**Key Configuration**:
```yaml
# Trino Iceberg Catalog Settings
connector.name: iceberg
iceberg.catalog.type: hadoop
hive.metastore.uri: thrift://localhost:9083  # Or use REST catalog
s3.endpoint: http://minio:9000
s3.path-style-access: true
```

### Phase 3: Apache Polaris Catalog (Upgrade)
- **Approach**: Deploy Polaris REST catalog for unified table management
- **Benefits**:
  - Centralized catalog governance
  - Multi-engine support (Trino, Spark, Flink)
  - RBAC and access control
  - Better metadata management
- **Migration**: Update Trino to use Polaris REST catalog
- **Trino Config**: Switch from Hadoop to REST catalog type

**Why Not Hive Metastore?**
- Adds complexity (extra PostgreSQL, Hive service)
- Harder to configure for S3-compatible storage
- Polaris is cloud-native and designed for modern lakehouses

## Current Phase Status

**Phase 1 (Foundation):** Complete
- ✅ Kubernetes infrastructure
- ✅ MinIO S3 storage
- ✅ Dagster deployment
- ✅ Trino deployment
- ✅ Secret externalization
- ✅ Documentation (SETUP_GUIDE.md, TEARDOWN.md)

**Phase 2 (Analytics):** Ready to Start
- ✅ DBT project structure (templates)
- ✅ Star schema examples
- ✅ Trino deployed and accessible
- ⏳ Deploy Meltano for data ingestion
- ⏳ Configure Singer taps (data sources)
- ⏳ Ingest data to MinIO S3 as Parquet
- ⏳ Create Iceberg tables in MinIO S3
- ⏳ Configure Trino Iceberg catalog
- ⏳ DBT model implementation
- ⏳ Superset deployment (optional)

**Phase 3 (Governance):** Planned
- Deploy Apache Polaris REST catalog
- Migrate Trino to Polaris catalog
- RBAC and access control
- Data lineage tracking
- Multi-engine catalog sharing

**Phase 4 (MLOps):** Planned
- Feast feature store
- Kubeflow ML platform
- DVC data versioning

**Phase 5 (Real-Time):** Planned
- Kafka/Redpanda streaming
- Flink stream processing
- CDC integration

## Common Workflows

### Adding a New Service to Infrastructure

1. Create Helm values: `infrastructure/kubernetes/<service>/values.yaml`
2. Create secrets file: `infrastructure/kubernetes/<service>/secrets.yaml` (gitignored, must set `namespace: lakehouse`)
3. Update `infrastructure/kubernetes/<service>/values.yaml` with service endpoints using simplified DNS (`service:port`)
4. Add deployment section to `infrastructure/README.md`
5. Add deployment phase to `SETUP_GUIDE.md` with:
   - Prerequisites
   - Deployment commands (deploy to `lakehouse` namespace)
   - Initialization steps
   - Verification commands
   - Access instructions

**Note:** No need to create separate namespace file - all services use the single `lakehouse` namespace.

### Adding DBT Models

1. **Bronze layer** (staging): Create `models/bronze/stg_<entity>.sql`
   - Materialized as views (no storage overhead)
   - Basic type casting and renaming
   - Reference source tables via `{{ source('raw', 'table') }}`
   - Minimal transformations (just prepare for Silver)

2. **Silver layer** (dimensions): Create `models/silver/dim_<entity>.sql`
   - Materialized as incremental Iceberg tables
   - Business logic and enrichment
   - SCD Type 2 if tracking history
   - Deduplication and cleaning

3. **Gold layer** (facts): Create `models/gold/fct_<entity>.sql`
   - Materialized as incremental Iceberg tables
   - Join to dimensions for foreign keys
   - Star schema pattern
   - Aggregations and metrics

### Debugging Failed Deployments

```bash
# Check pod status and events
kubectl get pods -n lakehouse
kubectl describe pod <pod-name> -n lakehouse

# View logs
kubectl logs <pod-name> -n lakehouse --tail=100 -f

# Check service endpoints
kubectl get svc -n lakehouse
kubectl get endpoints -n lakehouse

# Check persistent volumes
kubectl get pvc -n lakehouse
kubectl describe pvc <pvc-name> -n lakehouse

# Test DNS resolution (same namespace - use short name)
kubectl run -it --rm debug --image=busybox --restart=Never -n lakehouse -- nslookup <service>

# Check resource constraints
kubectl top pods -n lakehouse
kubectl top nodes
```

## Learning Path

**Recommended order for new developers:**

1. **Week 1**: Deploy infrastructure following SETUP_GUIDE.md, understand MinIO S3 initialization
2. **Week 2**: Create Iceberg tables via Trino, understand table format and catalog
3. **Week 3**: Learn DBT, create Bronze layer models
4. **Week 4**: Build Silver layer dimensions (star schema, SCD Type 2)
5. **Week 5**: Build Gold layer facts (dimensional joins, metrics)
6. **Week 6**: Query optimization and Trino performance tuning
7. **Week 7**: Create Superset dashboards (Phase 2)
8. **Week 8+**: Explore governance (Phase 3) or MLOps (Phase 4)

## Troubleshooting

### MinIO Pod Not Starting

**Check:** Persistent volume binding
```bash
kubectl get pvc -n lakehouse
kubectl describe pvc -n lakehouse
```

### DBT Cannot Connect to Trino

**Check:**
1. Port-forward active: `kubectl port-forward -n lakehouse svc/trino 8080:8080`
2. `profiles.yml` host: Should be `localhost` (if using port-forward) or `trino` (from within cluster)
3. Trino catalog exists: `SHOW CATALOGS;` in Trino CLI

### Trino Cannot Access MinIO S3

**Check:**
1. MinIO S3 service: `kubectl get svc -n lakehouse minio`
2. Catalog properties: S3 endpoint should be `http://minio:9000` (simplified DNS)
3. Access keys: Match credentials in MinIO values.yaml (default: admin/minio123)
4. Path style access: Must be `true` for MinIO

## References

- **Setup Guide**: Complete deployment walkthrough - see [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Teardown Guide**: Clean cluster teardown - see [TEARDOWN.md](TEARDOWN.md)
- **Infrastructure**: Component documentation - see [infrastructure/README.md](infrastructure/README.md)
- **Architecture**: Technical deep dive - see [ARCHITECTURE.md](ARCHITECTURE.md)
- **Iceberg**: ACID table format with schema evolution
- **Star Schema**: Dimensional modeling in Gold layer (fact + dimension tables)
- **Medallion Architecture**: Bronze → Silver → Gold data quality progression
- **SCD Type 2**: Historical tracking with `valid_from`/`valid_to`/`is_current` columns

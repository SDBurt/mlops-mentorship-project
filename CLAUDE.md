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
- **Storage**: Garage (S3-compatible) stores Parquet files
- **Table Format**: Apache Iceberg (ACID, schema evolution, time travel)
- **Ingestion**: Airbyte writes raw data as Iceberg tables
- **Transformations**: DBT Core (SQL models) orchestrated by Dagster
- **Query Engine**: Trino (distributed SQL over Iceberg)
- **BI**: Apache Superset (Phase 2+)

**Data Flow:**
```
Data Sources → Airbyte → Garage/S3 (Parquet)
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

**Kubernetes Namespaces:**
- `garage` - S3-compatible storage
- `airbyte` - Data ingestion (includes embedded PostgreSQL)
- `dagster` - Orchestration (includes embedded PostgreSQL)
- `trino` - Query engine

## Commands

### Deployment

**Always refer users to:** [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete step-by-step deployment.

Quick reference (see SETUP_GUIDE.md for full context):

```bash
# Prerequisites
helm repo add airbyte https://airbytehq.github.io/helm-charts
helm repo add dagster https://dagster-io.github.io/helm
helm repo add trino https://trinodb.github.io/charts
helm repo update

# Fetch Garage chart (no Helm repo available)
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo
cp -r /tmp/garage-repo/script/helm/garage infrastructure/helm/garage
rm -rf /tmp/garage-repo

# Deploy services (order matters - see SETUP_GUIDE.md)
# 1. Garage (storage)
helm upgrade --install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage --create-namespace --wait

# 2. Airbyte (ingestion - includes embedded PostgreSQL)
helm upgrade --install airbyte airbyte/airbyte --version 1.8.5 \
  -f infrastructure/kubernetes/airbyte/values.yaml \
  -n airbyte --create-namespace --wait --timeout 10m

# 3. Dagster (orchestration - includes embedded PostgreSQL)
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n dagster --create-namespace --wait --timeout 10m

# 4. Trino (query engine)
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n trino --create-namespace --wait --timeout 10m
```

### Teardown

**Refer users to:** [TEARDOWN.md](TEARDOWN.md) for complete teardown process.

Quick reference:
```bash
# Uninstall Helm releases
helm uninstall dagster -n dagster
helm uninstall trino -n trino
helm uninstall airbyte -n airbyte
helm uninstall garage -n garage

# Delete namespaces
kubectl delete namespace airbyte dagster trino garage
```

### Check Status

```bash
# All pods across lakehouse namespaces
kubectl get pods --all-namespaces | grep -E 'garage|airbyte|dagster|trino'

# All services
kubectl get svc --all-namespaces | grep -E 'garage|airbyte|dagster|trino'

# Helm releases
helm list --all-namespaces

# Pod logs
kubectl logs -n <namespace> <pod-name> --tail=100 -f
```

### Port-Forward Services

**Note:** Port-forward blocks the terminal. Open separate terminals for each service.

```bash
# Airbyte UI (separate terminal)
# Note: In Airbyte V2, the UI is served by airbyte-server
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001

# Dagster UI (separate terminal)
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80

# Trino UI (separate terminal)
kubectl port-forward -n trino svc/trino 8080:8080
# Note: Conflicts with Airbyte on 8080 - use 8081 instead:
kubectl port-forward -n trino svc/trino 8081:8080

# Garage S3 API (separate terminal)
kubectl port-forward -n garage svc/garage 3900:3900
```

Access:
- Airbyte: http://localhost:8080
- Dagster: http://localhost:3000
- Trino: http://localhost:8081

### Garage S3 Operations

**Critical:** Garage requires cluster initialization after deployment (not automatic).

```bash
# Get Garage pod name
POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# Check cluster status
kubectl exec -n garage $POD -- /garage status

# Initialize cluster (first-time setup only)
# 1. Get node ID
NODE_ID=$(kubectl exec -n garage $POD -- /garage status 2>/dev/null | grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $1}')

# 2. Assign storage role with capacity
kubectl exec -n garage $POD -- /garage layout assign -z garage-dc -c 10G $NODE_ID

# 3. Apply layout (version 1 for first setup)
kubectl exec -n garage $POD -- /garage layout apply --version 1

# 4. Verify initialization
kubectl exec -n garage $POD -- /garage status

# Create S3 bucket and access key
kubectl exec -n garage $POD -- /garage bucket create lakehouse
kubectl exec -n garage $POD -- /garage key create lakehouse-access
kubectl exec -n garage $POD -- /garage bucket allow --read --write lakehouse --key lakehouse-access

# List buckets
kubectl exec -n garage $POD -- /garage bucket list

# List keys
kubectl exec -n garage $POD -- /garage key list
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
1. Airbyte data sources configured
2. Raw Iceberg tables created in Garage S3
3. `sources.yml` updated with actual table names

## Key Architectural Decisions

### Terminology: "Lakehouse" vs "Data Lake"

**Use "lakehouse" in naming** (databases, profiles, project names):
- `database: lakehouse` in Trino connections
- `profile: lakehouse` in DBT profiles
- `project: lakehouse_analytics` in DBT

**Why?** Reflects the vision - governance (Phase 3 with Apache Polaris) will transform the data lake into a true lakehouse with unified catalog, RBAC, and audit trails.

### Cross-Namespace Service Communication

Services communicate via Kubernetes DNS:

**Pattern:** `<service-name>.<namespace>.svc.cluster.local:<port>`

**Examples:**
- Garage S3 API: `garage.garage.svc.cluster.local:3900`
- Trino: `trino.trino.svc.cluster.local:8080`
- Airbyte PostgreSQL (embedded): `airbyte-airbyte-postgresql.airbyte.svc.cluster.local:5432`
- Dagster PostgreSQL (embedded): `dagster-postgresql.dagster.svc.cluster.local:5432`

**Usage:**
- Airbyte connects to Garage: `s3.endpoint=http://garage.garage.svc.cluster.local:3900`
- Trino connects to Garage: `s3.endpoint=http://garage.garage.svc.cluster.local:3900`
- DBT connects to Trino: `host=trino.trino.svc.cluster.local`

### Secret Management

**All secrets externalized** to `secrets.yaml` files (gitignored via `**/*/secrets.yaml` pattern):
- `infrastructure/kubernetes/garage/secrets.yaml` - Auto-generates RPC secret (handled by Helm)
- `infrastructure/kubernetes/airbyte/airbyte-storage-secrets.yaml` - Garage S3 credentials for Airbyte storage

**Note:** PostgreSQL credentials for Airbyte and Dagster are configured in their respective `values.yaml` files (embedded databases).

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
  namespace: <namespace>
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
1. Airbyte data sources configured
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

### Garage S3 Configuration (for Trino/DBT)

```yaml
# In Trino catalog properties or DBT profiles
s3:
  endpoint: http://garage.garage.svc.cluster.local:3900
  path-style-access: true  # Required for Garage
  aws-access-key-id: <from-garage-key-create>
  aws-secret-access-key: <from-garage-key-create>
  region: garage  # Can be any value for Garage
```

## Iceberg Table Format Strategy

**Iceberg is configured in phases:**

### Phase 2: Airbyte Native Iceberg Destination
- **Approach**: Use Airbyte's built-in Iceberg S3 destination
- **Catalog**: Airbyte manages catalog internally (Hadoop or JDBC catalog)
- **Setup**: Configure Iceberg destination in Airbyte UI pointing to Garage S3
- **Output**: Raw Iceberg tables written to `s3://lakehouse/warehouse/`
- **Access**: Trino will connect to same catalog to query tables

**Key Configuration**:
```yaml
# Airbyte Iceberg Destination Settings
S3 Endpoint: http://garage.garage.svc.cluster.local:3900
Bucket: lakehouse
Warehouse Path: warehouse/
Catalog Type: HADOOP (or JDBC for more features)
```

### Phase 3: Apache Polaris Catalog (Upgrade)
- **Approach**: Deploy Polaris REST catalog for unified table management
- **Benefits**:
  - Centralized catalog governance
  - Multi-engine support (Trino, Spark, Flink)
  - RBAC and access control
  - Better metadata management
- **Migration**: Update Airbyte and Trino to use Polaris REST catalog
- **Trino Config**: Switch from Hadoop to REST catalog type

**Why Not Hive Metastore?**
- Adds complexity (extra PostgreSQL, Hive service)
- Harder to configure for S3-compatible storage
- Polaris is cloud-native and designed for modern lakehouses

## Current Phase Status

**Phase 1 (Foundation):** Complete
- ✅ Kubernetes infrastructure
- ✅ Garage S3 storage
- ✅ Airbyte deployment
- ✅ Dagster deployment
- ✅ Trino deployment
- ✅ Secret externalization
- ✅ Documentation (SETUP_GUIDE.md, TEARDOWN.md)

**Phase 2 (Analytics):** Ready to Start
- ✅ DBT project structure (templates)
- ✅ Star schema examples
- ✅ Trino deployed and accessible
- ⏳ Airbyte data source configuration
- ⏳ Configure Airbyte Iceberg destination (S3 + Garage)
- ⏳ Raw data ingestion to Garage as Iceberg tables
- ⏳ Configure Trino to read Airbyte's Iceberg catalog
- ⏳ DBT model implementation
- ⏳ Superset deployment (optional)

**Phase 3 (Governance):** Planned
- Deploy Apache Polaris REST catalog
- Migrate Airbyte + Trino to Polaris catalog
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

1. Create namespace: `infrastructure/kubernetes/namespaces/<service>.yaml`
2. Create Helm values: `infrastructure/kubernetes/<service>/values.yaml`
3. Create secrets file: `infrastructure/kubernetes/<service>/secrets.yaml` (gitignored)
4. Add deployment section to `infrastructure/README.md`
5. Add deployment phase to `SETUP_GUIDE.md` with:
   - Prerequisites
   - Deployment commands
   - Initialization steps
   - Verification commands
   - Access instructions

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
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace>

# View logs
kubectl logs <pod-name> -n <namespace> --tail=100 -f

# Check service endpoints
kubectl get svc -n <namespace>
kubectl get endpoints -n <namespace>

# Check persistent volumes
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -n <namespace> -- nslookup <service>.<target-namespace>.svc.cluster.local

# Check resource constraints
kubectl top pods -n <namespace>
kubectl top nodes
```

## Learning Path

**Recommended order for new developers:**

1. **Week 1**: Deploy infrastructure following SETUP_GUIDE.md, understand Garage S3 initialization
2. **Week 2**: Configure Airbyte sources, understand Iceberg table format
3. **Week 3**: Learn DBT, create Bronze layer models
4. **Week 4**: Build Silver layer dimensions (star schema, SCD Type 2)
5. **Week 5**: Build Gold layer facts (dimensional joins, metrics)
6. **Week 6**: Deploy Trino, query Iceberg tables, understand query optimization
7. **Week 7**: Create Superset dashboards (Phase 2)
8. **Week 8+**: Explore governance (Phase 3) or MLOps (Phase 4)

## Troubleshooting

### Garage Pod Not Starting

**Check:** Persistent volume binding
```bash
kubectl get pvc -n garage
kubectl describe pvc data-garage-0 -n garage
```

### Airbyte Pods CrashLooping

**Common causes:**
1. Embedded PostgreSQL not ready: Check `kubectl get pods -n airbyte | grep postgresql`
2. Storage secret errors: Verify `airbyte-storage-secrets` applied
3. Resource constraints: Check `kubectl top pods -n airbyte`

### DBT Cannot Connect to Trino

**Check:**
1. Port-forward active: `kubectl port-forward -n trino svc/trino 8080:8080`
2. `profiles.yml` host: Should be `localhost` (if using port-forward) or `trino.trino.svc.cluster.local` (from within cluster)
3. Trino catalog exists: `SHOW CATALOGS;` in Trino CLI

### Trino Cannot Access Garage S3

**Check:**
1. Garage S3 service: `kubectl get svc -n garage garage`
2. Catalog properties: S3 endpoint should be `http://garage.garage.svc.cluster.local:3900`
3. Access keys: Match output from `garage key create lakehouse-access`
4. Path style access: Must be `true` for Garage

## References

- **Setup Guide**: Complete deployment walkthrough - see [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Teardown Guide**: Clean cluster teardown - see [TEARDOWN.md](TEARDOWN.md)
- **Infrastructure**: Component documentation - see [infrastructure/README.md](infrastructure/README.md)
- **Architecture**: Technical deep dive - see [ARCHITECTURE.md](ARCHITECTURE.md)
- **Iceberg**: ACID table format with schema evolution
- **Star Schema**: Dimensional modeling in Gold layer (fact + dimension tables)
- **Medallion Architecture**: Bronze → Silver → Gold data quality progression
- **SCD Type 2**: Historical tracking with `valid_from`/`valid_to`/`is_current` columns

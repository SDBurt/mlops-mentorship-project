# Airbyte - Data Ingestion Platform

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Airbyte concepts and this project's architecture, please verify critical details against official Airbyte documentation and your specific use cases.

## Overview

Airbyte is an open-source data ingestion platform that extracts data from sources (databases, APIs, SaaS tools) and loads it into destinations (data warehouses, data lakes). It provides 300+ pre-built connectors and handles incremental syncs, schema changes, and error recovery automatically.

In this lakehouse platform, Airbyte is the primary ingestion tool: it extracts data from various sources and writes it to [Garage](garage.md) S3 as Parquet files, ready for transformation by [DBT](dbt.md) and querying by [Trino](trino.md).

## Why Airbyte for This Platform?

**300+ Connectors**: Pre-built connectors for databases (Postgres, MySQL, MongoDB), APIs (Stripe, Salesforce, GitHub), and files (CSV, JSON).

**ELT Pattern**: Extract and Load raw data first, transform later with [DBT](dbt.md) - modern data engineering approach.

**Incremental Syncs**: Automatically detects and syncs only new/changed data (not full table every time).

**Schema Management**: Handles schema changes automatically (new columns, type changes).

**Open Source**: Self-hosted, no vendor lock-in, active community.

## Key Concepts

### 1. Sources and Destinations

**Source**: Where data comes from (input)
- Databases: PostgreSQL, MySQL, MongoDB, SQL Server
- APIs: Stripe, Salesforce, GitHub, Google Analytics
- Files: CSV, JSON, Parquet on S3/GCS
- Applications: HubSpot, Zendesk, Shopify

**Destination**: Where data goes (output)
- Data warehouses: Snowflake, BigQuery, Redshift
- Data lakes: S3 (Parquet), GCS, Azure Blob
- Databases: PostgreSQL, MySQL
- Vector databases: Pinecone, Weaviate

**In this platform**:
```
Sources → Airbyte → Destination (Garage S3 as Parquet)
          ↓
    [Garage](garage.md)
          ↓
    [Trino](trino.md) queries Parquet files
          ↓
    [DBT](dbt.md) transforms into Bronze/Silver/Gold
```

### 2. Connections and Sync Modes

**Connection**: Configuration linking source + destination
- Which tables/streams to sync
- Sync frequency (hourly, daily, manual)
- Sync mode (full refresh vs incremental)

**Sync Modes**:

**Full Refresh - Overwrite**:
- Deletes destination data
- Copies entire source table
- Use case: Small reference tables, daily snapshots

**Full Refresh - Append**:
- Keeps existing destination data
- Appends entire source table
- Use case: Historical logs, immutable data

**Incremental - Append**:
- Syncs only new records (based on cursor field like `updated_at`)
- Appends to destination
- Use case: Event logs, transactions (append-only)

**Incremental - Deduped History**:
- Syncs only new/changed records
- Maintains one record per primary key (deduplicated)
- Use case: Dimension tables (customers, products)

**Example Configuration**:
```yaml
Connection: "Postgres Customers → S3"
- Tables: customers, orders, products
- Sync mode: Incremental - Deduped History
- Cursor field: updated_at
- Primary key: customer_id
- Schedule: Every 6 hours
```

### 3. Normalization

**What it is**: Optional step that transforms raw JSON into relational tables

**Raw sync output** (JSON):
```json
{
  "customer_id": 123,
  "name": "John Doe",
  "orders": [
    {"order_id": 1, "amount": 50},
    {"order_id": 2, "amount": 75}
  ]
}
```

**After normalization** (flattened tables):
```
customers:
  customer_id | name
  123         | John Doe

orders:
  order_id | customer_id | amount
  1        | 123         | 50
  2        | 123         | 75
```

**In this platform**: Normalization disabled - raw JSON/Parquet stored, transformed later with [DBT](dbt.md).

### 4. Metadata Storage

Airbyte stores its own metadata in embedded [PostgreSQL](postgresql.md):
- Connection configurations
- Sync history and status
- Connector versions
- Internal state (for incremental syncs)

**Deployed in this platform**:
```bash
kubectl get pods -n airbyte | grep postgresql
# airbyte-airbyte-postgresql-0  1/1  Running
```

**Connection string** (internal):
```
postgresql://airbyte:password@airbyte-airbyte-postgresql.airbyte.svc.cluster.local:5432/airbyte
```

## Deployment in Kubernetes

### Architecture

Airbyte deployed as multiple components:

**Core Services**:
- **airbyte-server**: REST API and business logic
- **airbyte-webapp**: UI (served by server in v2)
- **airbyte-worker**: Runs connector sync jobs
- **airbyte-temporal**: Workflow orchestration (manages job state)
- **airbyte-cron**: Scheduled tasks
- **airbyte-postgresql**: Metadata database

**Storage**:
- **Internal storage** ([Garage](garage.md) S3): Airbyte logs, state, configs
- **Destination storage** ([Garage](garage.md) S3): User data (synced Parquet files)

### Helm Deployment

**Chart**: `airbyte-v2/airbyte`

**Deployment command**:
```bash
helm upgrade --install airbyte airbyte-v2/airbyte \
  --version 2.0.18 \
  -f infrastructure/kubernetes/airbyte/values.yaml \
  -n airbyte --create-namespace --wait --timeout 10m
```

**Key configuration** (`values.yaml`):
```yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://garage.garage.svc.cluster.local:3900
      bucketName: lakehouse
      accessKeyId: <from-garage-key-create>
      secretAccessKey: <from-garage-key-create>

postgresql:
  enabled: true  # Embedded PostgreSQL
  postgresqlUsername: airbyte
  postgresqlPassword: <secret>
  postgresqlDatabase: airbyte
```

### Accessing Airbyte UI

**Port-forward**:
```bash
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001
```

**Access**: http://localhost:8080

**Default credentials** (first time):
- Email: admin@example.com
- Password: password

## Common Operations

### Create Source Connection

**Via UI**:
1. Sources → New Source
2. Select connector (e.g., PostgreSQL)
3. Configure connection:
   - Host: `postgres.mycompany.com`
   - Port: 5432
   - Database: production
   - Username/Password
4. Test connection
5. Save

**Via API** (for automation):
```bash
curl -X POST http://localhost:8080/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "sourceDefinitionId": "<postgres-connector-id>",
    "name": "Production Postgres",
    "connectionConfiguration": {
      "host": "postgres.mycompany.com",
      "port": 5432,
      "database": "production",
      "username": "airbyte",
      "password": "secret"
    }
  }'
```

### Create Destination (Garage S3)

**Via UI**:
1. Destinations → New Destination
2. Select "S3"
3. Configure:
   - S3 Bucket Name: `lakehouse`
   - S3 Endpoint: `http://garage.garage.svc.cluster.local:3900`
   - Access Key ID: `<from-garage-key-create>`
   - Secret Access Key: `<secret>`
   - Format: Parquet
   - Path: `raw/{schema}/{table}/`
4. Test connection
5. Save

### Create Connection

**Via UI**:
1. Connections → New Connection
2. Select source: "Production Postgres"
3. Select destination: "Garage S3"
4. Configure tables:
   - Select tables: customers, orders, products
   - Sync mode: Incremental - Deduped History
   - Cursor field: `updated_at`
   - Primary key: `id`
5. Schedule: Every 6 hours
6. Save

### Trigger Manual Sync

**Via UI**:
1. Connections → Select connection
2. Click "Sync Now"
3. Monitor progress in UI

**Via API**:
```bash
curl -X POST http://localhost:8080/api/v1/connections/sync \
  -H "Content-Type: application/json" \
  -d '{"connectionId": "<connection-id>"}'
```

### Monitor Sync Status

**Via UI**:
- Connections → View sync history
- Status: Succeeded, Failed, Running
- Duration, records synced, errors

**Via Logs**:
```bash
# View worker logs (where syncs run)
kubectl logs -n airbyte -l app.kubernetes.io/name=worker --tail=100 -f

# View server logs
kubectl logs -n airbyte -l app.kubernetes.io/name=server --tail=100 -f
```

## Integration with Lakehouse

### Data Flow

```
1. Airbyte extracts from source (e.g., Postgres)
2. Airbyte writes Parquet to Garage S3:
   s3://lakehouse/raw/customers/2025/01/20/data-001.parquet
3. [DBT](dbt.md) Bronze layer creates view over raw Parquet
4. [DBT](dbt.md) Silver layer transforms into clean dimensions
5. [Trino](trino.md) queries transformed tables
```

### File Layout in Garage

**Airbyte writes**:
```
s3://lakehouse/raw/
├── postgres_customers/
│   ├── 2025/01/20/data-001.parquet
│   ├── 2025/01/20/data-002.parquet
│   └── 2025/01/21/data-003.parquet
├── postgres_orders/
│   └── 2025/01/20/data-001.parquet
└── _airbyte_internal/
    ├── state/
    └── logs/
```

**DBT references**:
```sql
-- Bronze layer view
CREATE VIEW bronze.stg_customers AS
SELECT *
FROM iceberg.raw.postgres_customers;
```

## Troubleshooting

### Sync Fails with Connection Error

**Check**:
```bash
# Test Garage S3 connectivity
kubectl exec -n airbyte <worker-pod> -- curl -I http://garage.garage.svc.cluster.local:3900
```

**Verify**:
- Garage service running: `kubectl get svc -n garage`
- Access keys correct: `kubectl exec -n garage garage-0 -- /garage key list`
- Bucket exists: `kubectl exec -n garage garage-0 -- /garage bucket list`

### PostgreSQL Connection Refused

**Check**:
```bash
kubectl get pods -n airbyte | grep postgresql
# Verify pod is Running

kubectl logs -n airbyte airbyte-airbyte-postgresql-0
# Check for startup errors
```

### Sync Runs But No Data Appears

**Check destination**:
```bash
# List objects in Garage bucket
kubectl exec -n garage garage-0 -- aws s3 ls s3://lakehouse/raw/ --endpoint-url http://localhost:3900 --profile garage
```

**Verify**:
- Sync completed successfully (UI shows green checkmark)
- Files written to correct path
- File format correct (Parquet not JSON)

## Best Practices

### 1. Use Incremental Syncs

**Good**: Incremental (fast, efficient)
```yaml
sync_mode: incremental
cursor_field: updated_at
```

**Bad**: Full refresh on large tables (slow, expensive)
```yaml
sync_mode: full_refresh_overwrite
```

### 2. Set Appropriate Sync Frequency

**High-volume sources**: Every 6-12 hours
**Low-volume sources**: Daily or weekly
**Real-time needs**: Use CDC connectors (Change Data Capture)

### 3. Monitor Sync Duration

Set up alerts if sync duration exceeds threshold:
```
If sync_duration > 2 hours → Alert
If sync fails → Alert
```

### 4. Use Namespace Prefix

Organize synced data by source:
```
s3://lakehouse/raw/postgres_prod/customers/
s3://lakehouse/raw/mongodb_analytics/events/
s3://lakehouse/raw/stripe_api/charges/
```

### 5. Version Control Connector Configs

Export connections as code (Terraform, YAML) for reproducibility:
```bash
# Export connection config via API
curl http://localhost:8080/api/v1/connections/<id> > connection-config.json
```

## Integration with Other Components

- **[Garage](garage.md)**: Airbyte writes data to Garage S3
- **[DBT](dbt.md)**: Transforms raw Airbyte data
- **[Trino](trino.md)**: Queries Airbyte-synced Parquet files
- **[Medallion Architecture](medallion-architecture.md)**: Airbyte populates Bronze layer
- **[PostgreSQL](postgresql.md)**: Stores Airbyte metadata

## References

- [Official Airbyte Documentation](https://docs.airbyte.com/)
- [Airbyte Connectors](https://docs.airbyte.com/integrations/)
- [Airbyte API Reference](https://airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs.html)
- [Airbyte Helm Chart](https://github.com/airbytehq/helm-charts)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

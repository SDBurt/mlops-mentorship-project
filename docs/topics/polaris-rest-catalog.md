# Polaris REST Catalog - Modern Iceberg Catalog

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Polaris concepts and this project's architecture, please verify critical details against official Polaris documentation and your specific use cases.

## Overview

Polaris is a modern, cloud-native catalog for [Apache Iceberg](apache-iceberg.md) tables. Developed by Snowflake and donated to Apache Iceberg, it provides REST API access, fine-grained access control (RBAC), audit logging, and multi-table transactions - features missing from [Hive Metastore](hive-metastore.md).

In this lakehouse platform (Phase 3, planned), Polaris replaces Hive Metastore to add governance features: RBAC, audit trails, and lineage tracking - transforming the data lake into a true "lakehouse."

## Why Polaris vs Hive Metastore?

**Modern API**: REST instead of Thrift - cloud-native, language-agnostic.

**Fine-Grained RBAC**: Table, column, row-level access control.

**Audit Logging**: Track who accessed/modified what, when.

**Multi-Table Transactions**: Atomic operations across multiple tables.

**Better Performance**: Optimized for cloud object storage patterns.

**OAuth 2.0 Integration**: Enterprise-grade authentication.

## Key Concepts

### 1. REST Catalog Protocol

**Traditional** (Hive Metastore):
```
Client → Thrift RPC (port 9083) → Hive Metastore
```

**Modern** (Polaris):
```
Client → HTTP REST API (port 8181) → Polaris Catalog
```

**Example API calls**:
```bash
# List namespaces
GET /v1/namespaces

# Get table metadata
GET /v1/namespaces/analytics/tables/dim_customer

# Create table
POST /v1/namespaces/analytics/tables
```

**Trino configuration**:
```properties
# Old (Phase 2)
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083

# New (Phase 3)
iceberg.catalog.type=rest
iceberg.rest.uri=http://polaris.governance.svc.cluster.local:8181
iceberg.rest.auth.type=oauth2
iceberg.rest.auth.oauth2.token=<jwt-token>
```

### 2. Namespaces and Hierarchies

**Polaris supports nested namespaces**:
```
catalog
├── lakehouse              # Top-level namespace
│   ├── analytics          # Sub-namespace
│   │   ├── dim_customer
│   │   └── fct_orders
│   ├── raw                # Sub-namespace
│   │   └── customers
│   └── staging            # Sub-namespace
```

**Benefits**:
- Organize tables by domain/team
- Apply RBAC at namespace level
- Isolate development/staging/production

### 3. Fine-Grained Access Control

**Principal types**:
- **Users**: Individual people
- **Service accounts**: Applications (Trino, DBT, Dagster)
- **Groups**: Collections of users

**Permissions**:
- **Table**: CREATE, DROP, SELECT, INSERT, UPDATE, DELETE
- **Column**: SELECT specific columns
- **Row**: Filter rows by predicate

**Example RBAC policy**:
```yaml
# Analytics team can read/write analytics schema
principals:
  - type: group
    name: analytics_team

grants:
  - namespace: lakehouse.analytics
    privileges:
      - TABLE_CREATE
      - TABLE_DROP
      - TABLE_READ_DATA
      - TABLE_WRITE_DATA

# Viewer role can only read gold layer
principals:
  - type: group
    name: viewers

grants:
  - namespace: lakehouse.gold
    privileges:
      - TABLE_READ_DATA
    row_filter: "is_public = TRUE"  # Row-level security
```

### 4. Audit Logging

**Every API call logged**:
- Who: User/service account
- What: Operation (CREATE TABLE, SELECT, etc.)
- When: Timestamp
- Where: Table/schema
- How: Success/failure
- Why: Request metadata

**Example audit log entry**:
```json
{
  "timestamp": "2025-01-20T10:30:00Z",
  "principal": "user:alice@company.com",
  "operation": "TABLE_READ_DATA",
  "resource": "lakehouse.analytics.dim_customer",
  "result": "SUCCESS",
  "metadata": {
    "query_engine": "trino",
    "ip_address": "10.244.0.10"
  }
}
```

**Use cases**:
- Compliance (GDPR, SOC 2)
- Security investigations
- Usage analytics

### 5. Multi-Catalog Support

**Single Polaris instance can manage multiple catalogs**:
```
Polaris
├── lakehouse_prod       # Production catalog
├── lakehouse_staging    # Staging catalog
└── lakehouse_dev        # Development catalog
```

**Benefits**:
- Environment isolation
- Single governance layer
- Centralized audit trail

## Phase 3 Migration Plan

### Step 1: Deploy Polaris

**Namespace**: `governance`

**Deployment**:
```bash
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n governance --create-namespace
```

**Components**:
- `polaris` pod: REST API server
- `polaris-postgresql`: Metadata backend
- `polaris` service: ClusterIP on port 8181

### Step 2: Import Hive Metastore Tables

**Polaris CLI**:
```bash
# Export from Hive Metastore
polaris migrate export \
  --source hive \
  --uri thrift://hive-metastore.database.svc.cluster.local:9083 \
  --output hive-tables.json

# Import to Polaris
polaris migrate import \
  --catalog lakehouse \
  --input hive-tables.json
```

### Step 3: Update Trino Configuration

**Old** (values.yaml):
```yaml
coordinator:
  additionalCatalogs:
    iceberg: |
      connector.name=iceberg
      iceberg.catalog.type=hive_metastore
      hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
```

**New** (values.yaml):
```yaml
coordinator:
  additionalCatalogs:
    iceberg: |
      connector.name=iceberg
      iceberg.catalog.type=rest
      iceberg.rest.uri=http://polaris.governance.svc.cluster.local:8181
      iceberg.rest.auth.type=oauth2
      iceberg.rest.auth.oauth2.token-endpoint=http://polaris.governance.svc.cluster.local:8181/oauth/token
      iceberg.rest.auth.oauth2.client-id=trino-service
      iceberg.rest.auth.oauth2.client-secret=<secret>
```

### Step 4: Configure RBAC

**Create principals**:
```bash
# Analytics team
polaris admin create-principal --name analytics_team --type group

# Trino service account
polaris admin create-principal --name trino-service --type service_account
```

**Grant permissions**:
```bash
# Analytics team can manage analytics schema
polaris admin grant \
  --principal analytics_team \
  --namespace lakehouse.analytics \
  --privilege TABLE_CREATE,TABLE_READ_DATA,TABLE_WRITE_DATA

# Trino service account (full access)
polaris admin grant \
  --principal trino-service \
  --namespace lakehouse \
  --privilege CATALOG_MANAGE_CONTENT
```

### Step 5: Enable Audit Logging

**Configure audit sink** (values.yaml):
```yaml
polaris:
  audit:
    enabled: true
    sink: s3
    s3:
      bucket: lakehouse
      prefix: audit-logs/
      endpoint: http://garage.garage.svc.cluster.local:3900
```

### Step 6: Decommission Hive Metastore

**After validating Polaris works**:
```bash
# Stop using Hive Metastore
kubectl scale deployment -n database hive-metastore --replicas=0

# After grace period, uninstall
kubectl delete namespace database
```

## Best Practices

### 1. Use Service Accounts for Applications

**Good**:
```yaml
# Trino uses service account
iceberg.rest.auth.oauth2.client-id=trino-service
```

**Bad**:
```yaml
# Sharing user credentials
iceberg.rest.auth.oauth2.client-id=alice@company.com
```

### 2. Apply Principle of Least Privilege

Grant minimum permissions required:
```bash
# Good: Read-only for BI tool
polaris admin grant --principal bi-tool --privilege TABLE_READ_DATA

# Bad: Full access
polaris admin grant --principal bi-tool --privilege CATALOG_MANAGE_CONTENT
```

### 3. Organize Namespaces by Domain

```
lakehouse
├── sales/        # Sales team
├── marketing/    # Marketing team
├── finance/      # Finance team (restricted)
└── shared/       # Cross-functional
```

### 4. Monitor Audit Logs

Set up alerts for:
- Failed authentication attempts
- Unauthorized access attempts
- DROP TABLE operations
- Bulk data exports

### 5. Regular Permission Reviews

Audit who has access to what quarterly:
```bash
polaris admin list-grants --namespace lakehouse.finance
```

## Integration with Other Components

- **[Trino](trino.md)**: Queries Iceberg via Polaris REST catalog
- **[Apache Iceberg](apache-iceberg.md)**: Polaris is Iceberg-native catalog
- **[Hive Metastore](hive-metastore.md)**: Replaced by Polaris in Phase 3
- **[Garage](garage.md)**: Stores data and audit logs

## References

- [Polaris Catalog GitHub](https://github.com/apache/polaris)
- [Iceberg REST Catalog Spec](https://iceberg.apache.org/docs/latest/rest-catalog/)
- [Polaris Documentation](https://polaris.apache.org/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Phase 3 details

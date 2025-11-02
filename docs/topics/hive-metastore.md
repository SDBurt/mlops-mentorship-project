# Hive Metastore - Traditional Metadata Catalog

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Hive Metastore concepts and this project's architecture, please verify critical details against official documentation and your specific use cases.

## Overview

Hive Metastore is a centralized metadata repository originally designed for Apache Hive. It stores table schemas, partition information, and file locations for data lake tables. Today it's used by many engines ([Trino](trino.md), Spark, Presto) as a catalog for [Apache Iceberg](apache-iceberg.md) tables.

In this lakehouse platform (Phase 2), Hive Metastore catalogs Iceberg tables stored in [MinIO](minio.md) S3, allowing [Trino](trino.md) and [DBT](dbt.md) to discover and query tables.

## Why Hive Metastore?

**Wide Compatibility**: Supported by Trino, Spark, Presto, Flink - battle-tested.

**Simple Setup**: Single process with database backend - easy for learning/development.

**Iceberg Support**: Stores Iceberg table metadata (schema, snapshots, manifest locations).

**Phase 2 Starting Point**: Good foundation before migrating to [Polaris REST Catalog](polaris-rest-catalog.md) (Phase 3).

## Key Concepts

### 1. Metadata Storage

**What Hive Metastore stores**:
- **Databases/Schemas**: Namespaces for tables (e.g., `lakehouse.analytics`)
- **Tables**: Schema definitions (columns, types, partitions)
- **Partitions**: Directory structure for partitioned tables
- **Iceberg metadata**: Pointers to Iceberg metadata files in S3

**What it doesn't store**: Actual data (stored in [MinIO](minio.md) S3 as Parquet files)

### 2. Architecture

```
[Trino] → Thrift Protocol (port 9083) → [Hive Metastore] → [PostgreSQL]
                                                                    ↓
                                                          (Stores metadata)
```

**Components**:
- **Hive Metastore Service**: Thrift server exposing metadata API
- **Backend Database**: PostgreSQL/MySQL storing metadata tables
- **Clients**: Trino, Spark, etc. connect via Thrift protocol

### 3. Iceberg Integration

**When you create Iceberg table** via Trino:
```sql
CREATE TABLE lakehouse.analytics.dim_customer (
    customer_key BIGINT,
    email VARCHAR
)
WITH (
    format = 'PARQUET',
    location = 's3://lakehouse/warehouse/analytics/dim_customer/'
);
```

**Hive Metastore stores**:
- Database: `lakehouse`
- Schema: `analytics`
- Table: `dim_customer`
- Location: `s3://lakehouse/warehouse/analytics/dim_customer/`
- Table type: `ICEBERG`
- Pointer to Iceberg metadata file: `s3://.../metadata/v1.metadata.json`

**Hive Metastore does NOT store**:
- Actual Parquet data files
- Iceberg snapshots (stored in S3 metadata/)
- Column statistics (stored in Iceberg manifests)

### 4. Thrift Protocol

**What it is**: RPC protocol for Hive Metastore communication

**Connection string**:
```
thrift://hive-metastore.database.svc.cluster.local:9083
```

**Trino configuration**:
```properties
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
```

## Deployment in Kubernetes

**Namespace**: `database`

**Deployment** (Deployment, not StatefulSet):
```bash
kubectl apply -f infrastructure/kubernetes/database/hive-metastore/
```

**Components**:
- **hive-metastore** pod: Runs Hive Metastore service
- **hive-metastore-postgresql**: Backend database (StatefulSet)
- **hive-metastore** service: ClusterIP on port 9083

**Environment variables** (configuration):
```yaml
env:
- name: DATABASE_TYPE
  value: postgres
- name: DATABASE_DRIVER
  value: org.postgresql.Driver
- name: DATABASE_HOST
  value: hive-metastore-postgresql.database.svc.cluster.local
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_DB
  value: metastore
- name: DATABASE_USER
  valueFrom:
    secretKeyRef:
      name: hive-metastore-postgresql
      key: username
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: hive-metastore-postgresql
      key: password
```

## Common Operations

### Create Database

```sql
-- Via Trino
CREATE SCHEMA lakehouse.analytics
WITH (location = 's3://lakehouse/warehouse/analytics/');
```

### List Databases

```sql
SHOW SCHEMAS FROM lakehouse;
```

### List Tables

```sql
SHOW TABLES FROM lakehouse.analytics;
```

### View Table Metadata

```sql
DESCRIBE lakehouse.analytics.dim_customer;
```

### Drop Table

```sql
DROP TABLE lakehouse.analytics.dim_customer;
```

**Note**: Drops metadata only - data files in S3 remain (must clean up manually).

## Limitations

### 1. No Multi-Table Transactions

Each table operation is isolated - can't atomically update multiple tables.

### 2. No Fine-Grained Access Control

Basic table-level permissions only - no column/row-level security.

### 3. Single Point of Failure

No built-in high availability - single metastore instance.

**Production mitigation**:
- Deploy multiple metastore instances behind load balancer
- Use managed service (AWS Glue, Azure Purview)

### 4. Performance at Scale

**Problem**: Single Thrift server can become bottleneck with many concurrent queries.

**Solution**: Use [Polaris REST Catalog](polaris-rest-catalog.md) (Phase 3) for better scalability.

### 5. Limited Audit Trail

No built-in audit logging for who accessed/modified tables.

## Phase 2 vs Phase 3

**Phase 2** (Current - Hive Metastore):
```
[Trino] → Thrift → [Hive Metastore] → [PostgreSQL]
```

**Pros**:
- Simple setup
- Wide compatibility
- Good for learning

**Cons**:
- No RBAC
- Limited scalability
- No audit trail

**Phase 3** (Future - Polaris REST Catalog):
```
[Trino] → REST API → [Polaris Catalog] → [PostgreSQL]
```

**Pros**:
- Fine-grained RBAC (table/column/row level)
- REST API (modern, cloud-native)
- Audit logging
- Multi-table transactions
- Better performance at scale

**Migration path**: Polaris can import existing Hive Metastore tables.

## Best Practices

### 1. Use External Tables

Always specify `location` - data stored in S3, not managed by Hive.

```sql
-- Good: External table
CREATE TABLE dim_customer (...) WITH (location = 's3://lakehouse/...');

-- Bad: Managed table (Hive controls lifecycle)
CREATE TABLE dim_customer (...);
```

### 2. Regular Backups

Backup Hive Metastore PostgreSQL database:
```bash
kubectl exec -n lakehouse hive-metastore-postgresql-0 -- \
  pg_dump -U metastore metastore > hive-metastore-backup.sql
```

### 3. Monitor Metastore Health

```bash
# Check metastore logs
kubectl logs -n lakehouse -l app=hive-metastore

# Check connection from Trino
kubectl exec -n lakehouse $TRINO_POD -- curl -I http://hive-metastore.database.svc.cluster.local:9083
```

### 4. Plan for Phase 3 Migration

Design schemas with Polaris in mind:
- Use namespaces (databases/schemas)
- Avoid Hive-specific features
- Document table ownership

## Troubleshooting

### Trino Cannot Connect to Hive Metastore

**Check service**:
```bash
kubectl get svc -n lakehouse hive-metastore
```

**Test connectivity**:
```bash
kubectl exec -n lakehouse $TRINO_POD -- telnet hive-metastore.database.svc.cluster.local 9083
```

### Metadata Out of Sync

**Problem**: Metastore has stale info about Iceberg tables

**Solution**: Refresh metadata in Trino:
```sql
CALL iceberg.system.refresh_metadata('lakehouse', 'analytics', 'dim_customer');
```

### PostgreSQL Backend Full

**Check storage**:
```bash
kubectl exec -n lakehouse hive-metastore-postgresql-0 -- df -h /var/lib/postgresql
```

**Expand PVC** if needed.

## Integration with Other Components

- **[Trino](trino.md)**: Queries Iceberg tables via Hive Metastore
- **[Apache Iceberg](apache-iceberg.md)**: Metastore stores pointers to Iceberg metadata
- **[Polaris REST Catalog](polaris-rest-catalog.md)**: Modern replacement (Phase 3)
- **[MinIO](minio.md)**: Stores actual data files referenced in metastore

## References

- [Apache Hive Metastore Documentation](https://cwiki.apache.org/confluence/display/Hive/Design#Design-Metastore)
- [Trino Hive Connector](https://trino.io/docs/current/connector/hive.html)
- [Iceberg Hive Catalog](https://iceberg.apache.org/docs/latest/hive/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

# PostgreSQL - Relational Database

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established PostgreSQL concepts and this project's architecture, please verify critical details against official PostgreSQL documentation and your specific use cases.

## Overview

PostgreSQL is an open-source relational database system (RDBMS) known for reliability, robustness, and SQL compliance. It provides ACID transactions, complex queries, foreign keys, triggers, and extensive data types.

In this lakehouse platform, PostgreSQL stores metadata for [Airbyte](airbyte.md) and [Dagster](dagster.md). Each service has its own embedded PostgreSQL instance deployed as a [StatefulSet](stateful-applications.md).

## Why PostgreSQL for This Platform?

**Metadata Storage**: Reliable storage for application metadata (not analytical data).

**ACID Transactions**: Ensures consistency for connection configs, job state, schedules.

**SQL Interface**: Standard SQL for querying metadata.

**Mature Ecosystem**: Well-understood, extensive documentation, strong community support.

**Embedded Deployments**: Easy to deploy per-service via Helm charts.

## Key Concepts

### 1. Embedded vs Standalone

**Embedded** (used in this platform):
- PostgreSQL deployed alongside application (Airbyte, Dagster)
- Lifecycle tied to application
- Simple setup, no separate cluster management
- Good for development/learning

**Standalone** (production alternative):
- Separate PostgreSQL cluster (e.g., CloudSQL, RDS, CrunchyData Operator)
- Shared across multiple applications
- High availability, backups, monitoring
- Recommended for production

### 2. Deployment Pattern

Each service deploys PostgreSQL via Helm chart subchart:

**Airbyte PostgreSQL**:
```yaml
# airbyte values.yaml
postgresql:
  enabled: true
  postgresqlUsername: airbyte
  postgresqlPassword: <secret>
  postgresqlDatabase: airbyte
  persistence:
    size: 8Gi
```

**Dagster PostgreSQL**:
```yaml
# dagster values.yaml
postgresql:
  enabled: true
  postgresqlUsername: dagster
  postgresqlPassword: <secret>
  postgresqlDatabase: dagster
  persistence:
    size: 8Gi
```

**Result**:
```bash
kubectl get pods -n lakehouse | grep postgresql
# airbyte-airbyte-postgresql-0

kubectl get pods -n lakehouse | grep postgresql
# dagster-postgresql-0
```

### 3. Connection Strings

**Airbyte PostgreSQL** (from within `airbyte` namespace):
```
postgresql://airbyte:password@airbyte-airbyte-postgresql.airbyte.svc.cluster.local:5432/airbyte
```

**Dagster PostgreSQL** (from within `dagster` namespace):
```
postgresql://dagster:password@dagster-postgresql.dagster.svc.cluster.local:5432/dagster
```

### 4. Data Stored

**Airbyte metadata**:
- Connection configurations (sources, destinations)
- Sync schedules and history
- Connector versions and state
- Internal job logs

**Dagster metadata**:
- Asset definitions and lineage
- Run history and status
- Schedule and sensor state
- Event logs

**Not stored in PostgreSQL**: Analytical data (stored in [MinIO](minio.md) S3 as [Iceberg](apache-iceberg.md) tables)

## Common Operations

### Connect to PostgreSQL

**Via kubectl exec**:
```bash
# Airbyte PostgreSQL
kubectl exec -it -n lakehouse airbyte-airbyte-postgresql-0 -- psql -U airbyte -d airbyte

# Dagster PostgreSQL
kubectl exec -it -n lakehouse dagster-postgresql-0 -- psql -U dagster -d dagster
```

### Query Metadata

**Airbyte - List connections**:
```sql
SELECT id, name, status, schedule
FROM connection
ORDER BY created_at DESC
LIMIT 10;
```

**Dagster - List recent runs**:
```sql
SELECT run_id, status, start_time, end_time
FROM runs
ORDER BY start_time DESC
LIMIT 10;
```

### Backup Database

```bash
# Dump Airbyte database
kubectl exec -n lakehouse airbyte-airbyte-postgresql-0 -- \
  pg_dump -U airbyte airbyte > airbyte-backup.sql

# Restore
cat airbyte-backup.sql | kubectl exec -i -n lakehouse airbyte-airbyte-postgresql-0 -- \
  psql -U airbyte -d airbyte
```

## Best Practices

### 1. Use Secrets for Passwords

**Good**:
```yaml
postgresql:
  existingSecret: "postgres-credentials"
```

**Bad**:
```yaml
postgresql:
  postgresqlPassword: "hardcoded-password"
```

### 2. Size PVC Appropriately

Monitor usage:
```bash
kubectl exec -n lakehouse airbyte-airbyte-postgresql-0 -- df -h /var/lib/postgresql
```

Increase if needed:
```bash
kubectl edit pvc data-airbyte-airbyte-postgresql-0 -n airbyte
```

### 3. Enable Connection Pooling

For production, use PgBouncer to pool connections.

### 4. Regular Backups

Schedule automated backups (cron job or backup operator).

### 5. Monitor Performance

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('airbyte'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Check active connections
SELECT count(*) FROM pg_stat_activity;
```

## Integration with Other Components

- **[Airbyte](airbyte.md)**: Stores connection and sync metadata
- **[Dagster](dagster.md)**: Stores run history and asset catalog
- **[Stateful Applications](stateful-applications.md)**: Deployed as StatefulSet with PVC
- **[Kubernetes Storage](kubernetes-storage.md)**: Uses PersistentVolumeClaims

## References

- [Official PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostgreSQL Helm Chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

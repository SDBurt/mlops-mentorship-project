# Apache Polaris REST Catalog

Apache Polaris provides a unified REST catalog for Apache Iceberg tables, enabling centralized metadata management, access control, and multi-engine support.

## Overview

**Purpose**: Unified Iceberg table catalog with governance capabilities

**Key Features**:
- REST API for Iceberg catalog operations
- Multi-engine support (Trino, Spark, Flink)
- Centralized metadata management
- RBAC and access control
- Audit trails and data lineage

**Phase**: 3 (Governance)

## Architecture

```
┌─────────────────────────────────────────────┐
│           Query Engines                      │
│  (Trino, Spark, Flink, etc.)                │
└─────────────────┬───────────────────────────┘
                  │ REST API
                  ↓
┌─────────────────────────────────────────────┐
│         Apache Polaris Catalog               │
│  - Table metadata                            │
│  - Access control                            │
│  - Audit logging                             │
└─────────────────┬───────────────────────────┘
                  │ JDBC
                  ↓
┌─────────────────────────────────────────────┐
│      PostgreSQL (Dagster embedded)           │
│  - Catalog metadata storage                  │
└─────────────────────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────┐
│           MinIO S3 Storage                   │
│  - Iceberg table data (Parquet)              │
│  - Metadata files                            │
└─────────────────────────────────────────────┘
```

## Configuration Files

- **values.yaml**: Custom Helm overrides (edit this)
- **values-default.yaml**: Upstream defaults (reference only, do not edit)
- **secrets.yaml**: Database and storage credentials (gitignored)

## Prerequisites

1. Dagster deployed (provides PostgreSQL for metadata)
2. MinIO deployed (provides S3 storage)
3. Secrets file created from template

## Deployment

### 1. Add Helm Repository

```bash
# Note: Polaris may not have an official Helm repo yet
# The chart is available in the GitHub repository
# Check https://polaris.apache.org/helm/ for latest instructions

# For now, you can clone the repo and install from local chart:
git clone https://github.com/apache/polaris.git
helm upgrade --install polaris ./polaris/helm/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### 2. Create Secrets

```bash
# Review and update secrets.yaml with your credentials
kubectl apply -f infrastructure/kubernetes/polaris/secrets.yaml
```

### 3. Deploy Polaris

```bash
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n lakehouse -l app.kubernetes.io/name=polaris

# Check service
kubectl get svc -n lakehouse polaris

# Check logs
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris --tail=50
```

## Access

### Port-Forward (Local Development)

```bash
# REST API (port 8181)
kubectl port-forward -n lakehouse svc/polaris 8181:8181
```

Access Polaris REST API at: http://localhost:8181

### Service Endpoints (Within Cluster)

- **REST API**: `http://polaris:8181`
- **Catalog endpoint**: `http://polaris:8181/api/catalog`
- **Management**: `http://polaris:8182` (health checks, metrics)

## Configuring Trino to Use Polaris

Update Trino's Iceberg catalog configuration:

```yaml
# infrastructure/kubernetes/trino/values.yaml
additionalCatalogs:
  lakehouse: |
    connector.name=iceberg
    iceberg.catalog.type=rest
    iceberg.rest.uri=http://polaris:8181/api/catalog
    iceberg.rest.warehouse=lakehouse
    fs.native-s3.enabled=true
    s3.endpoint=http://minio:9000
    s3.path-style-access=true
    s3.region=us-east-1
    s3.aws-access-key-id=${ENV:S3_ACCESS_KEY}
    s3.aws-secret-access-key=${ENV:S3_SECRET_KEY}
```

Then update Trino:

```bash
helm upgrade trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --wait
```

## Initial Setup

### 1. Initialize Polaris Catalog

```bash
# Port-forward to Polaris
kubectl port-forward -n lakehouse svc/polaris 8181:8181

# Create catalog (using Polaris REST API)
curl -X POST http://localhost:8181/api/management/v1/catalogs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "lakehouse",
    "properties": {
      "warehouse": "s3://lakehouse/warehouse/",
      "default-base-location": "s3://lakehouse/warehouse/"
    }
  }'
```

### 2. Create Namespaces (Schemas)

```sql
-- Connect to Trino
-- Create namespaces in the lakehouse catalog
CREATE SCHEMA lakehouse.bronze;
CREATE SCHEMA lakehouse.silver;
CREATE SCHEMA lakehouse.gold;
```

### 3. Verify Catalog

```sql
-- Show catalogs
SHOW CATALOGS;

-- Show schemas
SHOW SCHEMAS IN lakehouse;

-- Show tables (should be empty initially)
SHOW TABLES IN lakehouse.bronze;
```

## Migrating from JDBC Catalog

If you have existing tables in a JDBC catalog:

1. Export table metadata from current catalog
2. Register tables in Polaris using REST API
3. Update Trino configuration to use Polaris
4. Verify table access through Polaris

## Configuration Details

### Persistence

Polaris uses **relational-jdbc** persistence with Dagster's PostgreSQL:

```yaml
persistence:
  type: relational-jdbc
  relationalJdbc:
    secret:
      name: polaris-db-secret
      username: username
      password: password
      jdbcUrl: jdbcUrl
```

Database connection string:
```
jdbc:postgresql://dagster-postgresql:5432/dagster
```

### Storage Credentials

MinIO S3 credentials are provided via secret:

```yaml
storage:
  secret:
    name: polaris-storage-secret
    awsAccessKeyId: aws-access-key-id
    awsSecretAccessKey: aws-secret-access-key
```

### Authentication

Default configuration uses **internal authentication** with RSA key pair:

```yaml
authentication:
  type: internal
  tokenBroker:
    type: rsa-key-pair
    maxTokenGeneration: PT1H
```

Keys are auto-generated if not provided. For production, create persistent keys.

## Monitoring

### Health Checks

```bash
# Liveness probe
curl http://localhost:8182/q/health/live

# Readiness probe
curl http://localhost:8182/q/health/ready
```

### Metrics

Prometheus metrics are available at:
```
http://localhost:8182/q/metrics
```

Enable ServiceMonitor if Prometheus operator is installed:

```yaml
serviceMonitor:
  enabled: true
  labels:
    release: prometheus
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n lakehouse -l app.kubernetes.io/name=polaris

# Check logs
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris --tail=100
```

Common issues:
- Database secret not found or incorrect
- Database connection failure
- Storage credentials invalid

### Cannot Connect to Database

Verify database connectivity:

```bash
# Test PostgreSQL connection from a debug pod
kubectl run -it --rm debug --image=postgres:14 --restart=Never -n lakehouse -- \
  psql -h dagster-postgresql -U dagster -d dagster -W
```

### Trino Cannot Connect to Polaris

Check:
1. Polaris service is running: `kubectl get svc -n lakehouse polaris`
2. REST API is accessible: `curl http://polaris:8181/q/health`
3. Catalog configuration in Trino is correct
4. Network policies allow communication

### View Polaris Logs

```bash
# Follow logs
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris -f

# Search for errors
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris | grep -i error
```

## Resources

- [Apache Polaris Documentation](https://polaris.apache.org/)
- [Apache Polaris GitHub](https://github.com/apache/polaris)
- [Helm Chart Documentation](https://polaris.apache.org/helm/)
- [Apache Iceberg REST Catalog Spec](https://iceberg.apache.org/spec/#catalog-api)

## Next Steps

1. Deploy Polaris following the steps above
2. Configure Trino to use Polaris catalog
3. Migrate existing tables (if any)
4. Set up RBAC and access control
5. Configure audit logging
6. Integrate with multiple query engines (Spark, Flink)

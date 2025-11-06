# Trino SQL Query Engine

Distributed SQL query engine for querying Iceberg tables in the lakehouse.

## What is Trino?

Trino is a distributed SQL query engine that allows you to query data stored in various formats and locations. In this lakehouse, Trino queries Iceberg tables stored in MinIO S3.

## Architecture

```
DBT → Trino → Iceberg Catalog → MinIO S3 Storage
```

- **DBT**: Runs SQL transformations via Trino
- **Trino**: Executes distributed queries
- **Iceberg**: Table format with ACID transactions
- **MinIO**: S3-compatible object storage

## Configuration

**Coordinator**: 1 replica (coordinates query execution)
**Workers**: 2 replicas (execute query tasks)
**Catalog**: Iceberg connector pointing to MinIO S3

See `values.yaml` for full configuration.

## Deployment

```bash
# Deploy Trino
helm upgrade --install trino trino/trino \
  -f values.yaml \
  -n trino --create-namespace --wait --timeout 10m

# Check status
kubectl get pods -n trino

# View logs
kubectl logs -n trino -l app.kubernetes.io/component=coordinator

# Access Trino web UI
kubectl port-forward svc/trino 8080:8080 -n trino
# Open http://localhost:8080
```

## Querying with Trino

### CLI Access

```bash
# Port-forward Trino service
kubectl port-forward svc/trino 8080:8080 -n trino

# Install Trino CLI
# Download from: https://trino.io/download.html

# Run queries
trino --server localhost:8080 --catalog lakehouse --schema bronze

# Example queries
SHOW SCHEMAS;
SHOW TABLES IN bronze;
SELECT * FROM bronze.raw_customers LIMIT 10;
```

### DBT Access

DBT connects to Trino which queries Iceberg tables in MinIO S3 storage.

DBT connects to Trino automatically using `profiles.yml`:

```bash
# From transformations/dbt/ directory
dbt run --select bronze.*
```

## Next Steps

1. Deploy Trino (see Deployment section above)
2. Configure Airbyte to create Iceberg tables
3. Query raw data via Trino
4. Run DBT transformations

## TODO (Phase 3 - Governance)

- [ ] Deploy Apache Polaris catalog
- [ ] Configure Trino to use Polaris REST catalog
- [ ] Enable RBAC and access control
- [ ] Add authentication for Trino web UI

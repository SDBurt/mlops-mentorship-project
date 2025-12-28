# Trino Query Engine

Trino provides distributed SQL queries over Apache Iceberg tables in the lakehouse.

## Architecture

```
Superset/DBT --> Trino --> Polaris (catalog)
                   |
                   v
              MinIO (data)
```

## Access

| Service | URL | Notes |
|---------|-----|-------|
| Trino UI | http://localhost:8080 | Query monitoring dashboard |
| JDBC | localhost:8080 | For SQL clients |

## Configuration

Trino connects to Iceberg tables via the Polaris REST catalog:

- **Catalog Type**: REST (Polaris)
- **Authentication**: OAuth2 with Polaris credentials
- **Storage**: MinIO S3

## Catalog Configuration

The `catalog/iceberg.properties` file configures the Iceberg connector:

```properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=http://polaris:8181/api/catalog/
iceberg.rest-catalog.warehouse=polariscatalog
```

## SQL Examples

```bash
# Connect to Trino
docker exec -it trino trino
```

```sql
-- List schemas
SHOW SCHEMAS FROM iceberg;

-- List tables in data schema
SHOW TABLES FROM iceberg.data;

-- Query payment events
SELECT * FROM iceberg.data.payment_events LIMIT 10;

-- Time travel query
SELECT * FROM iceberg.data.payment_events
FOR TIMESTAMP AS OF TIMESTAMP '2025-01-01 00:00:00 UTC';
```

## Files

| File | Description |
|------|-------------|
| `catalog/iceberg.properties` | Iceberg connector configuration |
| `create-payments-tables.sql` | SQL scripts for table creation |

## DBT Integration

DBT uses Trino as its execution engine for transformations:

```yaml
# dbt/profiles.yml
lakehouse_analytics:
  target: dev
  outputs:
    dev:
      type: trino
      host: trino
      port: 8080
      catalog: iceberg
      schema: data
```

## Commands

```bash
# Start Trino (with dependencies)
make datalake-up

# Connect to Trino CLI
docker exec -it trino trino
```

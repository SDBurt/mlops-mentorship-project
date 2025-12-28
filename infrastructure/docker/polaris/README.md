# Apache Polaris (Iceberg REST Catalog)

Polaris provides a REST catalog for Apache Iceberg, enabling unified metadata management across the lakehouse.

## Architecture

```
Trino/Dagster --> Polaris REST API --> MinIO (table data)
                       |
                  (metadata)
```

## Access

| Service | URL | Notes |
|---------|-----|-------|
| Polaris API | http://localhost:8181 | REST catalog endpoint |
| Health Check | http://localhost:8182/q/health | Service health |

## Configuration

Polaris is configured via docker-compose with:

- **Storage**: MinIO S3 (`s3://warehouse`)
- **Auth**: OAuth2 client credentials
- **Persistence**: Local volume for catalog metadata

## Initialization

The `polaris-init` container runs automatically on startup and:

1. Waits for Polaris to be healthy
2. Creates `polariscatalog` catalog with MinIO storage
3. Sets up RBAC roles (`catalog_admin`, `data_engineer`)
4. Creates the `data` namespace for Dagster assets

## Environment Variables

| Variable | Description |
|----------|-------------|
| `POLARIS_REALM` | Authentication realm |
| `POLARIS_USER` | OAuth client ID |
| `POLARIS_PASSWORD` | OAuth client secret |
| `AWS_ENDPOINT_URL_S3` | MinIO endpoint |

## API Examples

```bash
# Get access token
ACCESS_TOKEN=$(curl -s -X POST \
  http://localhost:8181/api/catalog/v1/oauth/tokens \
  -d "grant_type=client_credentials&client_id=root&client_secret=secret&scope=PRINCIPAL_ROLE:ALL" \
  | jq -r '.access_token')

# List catalogs
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8181/api/management/v1/catalogs

# List namespaces
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8181/api/catalog/v1/polariscatalog/namespaces
```

## Files

| File | Description |
|------|-------------|
| `init-polaris.sh` | Initialization script for catalog, roles, and namespaces |

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `data` | Dagster-managed Iceberg tables (payment_events, etc.) |

## Commands

```bash
# Start stack (includes Polaris)
make datalake-up

# Re-run initialization
make docker-polaris-init
```

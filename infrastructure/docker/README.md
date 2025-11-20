# Docker Compose - Local Lakehouse

This brings up a complete local lakehouse stack using Docker Compose.

## Services Included

- **MinIO** (S3-compatible) – ports 9000 (API), 9001 (Console)
- **Polaris** (Iceberg REST catalog) – ports 8181/8182
- **Trino** (SQL engine) – port 8080
- **Dagster** (orchestration) – port 3000 (webserver), plus daemon and user code
- **PostgreSQL** (for Dagster metadata)

References:

- Medium article one: [Build a Data Lakehouse with Apache Iceberg, Polaris, Trino & MinIO](https://medium.com/@gilles.philippart/build-a-data-lakehouse-with-apache-iceberg-polaris-trino-minio-349c534ecd98)
- Medium article two: [Build a Streaming Data Lakehouse with Apache Flink, Kafka, Iceberg and Polaris](https://medium.com/@gilles.philippart/build-a-streaming-data-lakehouse-with-apache-flink-kafka-iceberg-and-polaris-473c47e04525)
- Dagster Compose guide: [Dagster OSS Docker Compose](https://docs.dagster.io/deployment/oss/deployment-options/docker)

## Prereqs

- Docker Desktop / Docker Engine + Compose v2
- curl (and optionally jq)

## Setup Reddit Credentials

The Dagster user code container needs Reddit API credentials to fetch data. Create a `.env` file in `infrastructure/docker/`:

```bash
# Copy the example file
cp infrastructure/docker/env.example infrastructure/docker/.env

# Edit .env and add your Reddit credentials
# Get credentials from https://www.reddit.com/prefs/apps
```

The `.env` file should contain:

```bash
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=lakehouse:v1.0.0 (by /u/your_username)
```

**Note:** The `.env` file is gitignored and will not be committed to the repository.

## Bring up all services

```bash
# From repo root
cd infrastructure/docker
docker compose up -d

# Or from repo root with full path
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Validate services are healthy
docker compose -f infrastructure/docker/docker-compose.yml ps
```

**Service URLs:**

- Dagster UI: <http://localhost:3000>
- Trino UI: <http://localhost:8080>
- MinIO Console: <http://localhost:9001> (admin/password)
- Polaris: <http://localhost:8181>

## Initialize Polaris (Automatic)

**Polaris initialization is now automatic!** The `polaris-init` service runs automatically when you start the stack with `make docker-up` or `docker compose up`.

The initialization script:

- ✅ Waits for Polaris to be ready (checks OAuth endpoint)
- ✅ Creates catalog `polariscatalog` with MinIO storage (`s3://warehouse`)
- ✅ Sets up RBAC: creates `catalog_admin` and `data_engineer` roles
- ✅ Grants `root` the `data_engineer` role
- ✅ Creates the `data` namespace (required for Dagster assets)
- ✅ Idempotent: safe to run multiple times

**Note:** The script is based on the [Medium article](https://medium.com/@gilles.philippart/build-a-data-lakehouse-with-apache-iceberg-polaris-trino-minio-349c534ecd98) and uses a more reliable readiness check.

**Timestamp Format Note:** JR templates use SQL timestamp format (`2006-01-02 15:04:05.000`) for Flink compatibility. Ensure all templates follow this convention to avoid JSON deserialization errors.

Verify initialization:

```bash
# Get access token and list catalogs
ACCESS_TOKEN=$(curl -s -X POST \
  http://localhost:8181/api/catalog/v1/oauth/tokens \
  -d 'grant_type=client_credentials&client_id=root&client_secret=secret&scope=PRINCIPAL_ROLE:ALL' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

curl -s -X GET http://localhost:8181/api/management/v1/catalogs \
  -H "Authorization: Bearer $ACCESS_TOKEN" | grep -o '"name":"[^"]*"'
```

## Test with Trino

Launch a Trino shell:

```bash
docker compose -f infrastructure/docker/docker-compose.yml exec -it trino trino --server localhost:8080 --catalog iceberg
```

In Trino:

```sql
CREATE SCHEMA db;
USE db;

CREATE TABLE customers (
  customer_id BIGINT,
  first_name VARCHAR,
  last_name VARCHAR,
  email VARCHAR
);

INSERT INTO customers (customer_id, first_name, last_name, email)
VALUES (1, 'Rey', 'Skywalker', 'rey@rebelscum.org'),
       (2, 'Hermione', 'Granger', 'hermione@hogwarts.edu'),
       (3, 'Tony', 'Stark', 'tony@starkindustries.com');

SELECT * FROM customers;
```

Optional time-travel example (replace timestamp as needed):

```sql
SELECT * FROM customers FOR TIMESTAMP AS OF TIMESTAMP '2025-07-05 17:20:00.000 UTC';
```

## Teardown

```bash
docker compose -f infrastructure/docker/docker-compose.yml down -v
```

## Dagster Services

The stack includes the following Dagster components:

- **dagster-webserver** – UI at <http://localhost:3000>
- **dagster-daemon** – Background scheduler for running jobs
- **dagster-user-code** – Your pipeline code (from `orchestration-dagster/`)
- **postgres** – Metadata storage for Dagster

**Prerequisites:**

- Dockerfile must exist in `orchestration-dagster/` directory
- User code must be properly configured (see `orchestration-dagster/README.md`)

For more details, see the [Dagster OSS Docker Compose docs](https://docs.dagster.io/deployment/oss/deployment-options/docker).

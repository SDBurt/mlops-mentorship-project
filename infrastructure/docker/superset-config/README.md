# Apache Superset (BI Dashboard)

Superset provides interactive dashboards and data exploration for the lakehouse.

## Architecture

```
Users --> Superset --> Trino --> Iceberg Tables
              |
         PostgreSQL (metadata)
         Redis (cache)
```

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Superset UI | http://localhost:8089 | admin / admin |

## Configuration

Superset is configured with:

- **Metadata Store**: PostgreSQL (`superset-db`)
- **Cache**: Redis (`superset-redis`)
- **Data Source**: Trino (pre-configured as "Lakehouse")

## Components

| Container | Description |
|-----------|-------------|
| `superset` | Web application server |
| `superset-worker` | Celery worker for async tasks |
| `superset-init` | Database migrations and admin user setup |
| `superset-db` | PostgreSQL for Superset metadata |
| `superset-redis` | Redis for caching and Celery broker |

## Pre-configured Data Source

On startup, Superset is configured with a Trino connection:

- **Database Name**: Lakehouse (Trino)
- **Catalog**: iceberg
- **Schema**: data

## Available Tables

After running DBT transformations:

| Table | Description |
|-------|-------------|
| `fct_payments` | Payment fact table |
| `fct_daily_payments` | Daily aggregated payments |
| `dim_customer` | Customer dimension |
| `dim_merchant` | Merchant dimension |
| `dim_date` | Date dimension |

## Files

| File | Description |
|------|-------------|
| `Dockerfile` | Extends Superset with Trino driver |
| `docker-init.sh` | Initialization script (migrations, admin user) |
| `superset_config.py` | Superset configuration |

## Commands

```bash
# Start Superset (requires datalake)
make superset-up

# View logs
make superset-logs

# Check status
make superset-status

# Stop Superset
make superset-down
```

## Getting Started

1. Start the datalake: `make datalake-up`
2. Start Superset: `make superset-up`
3. Login at http://localhost:8089 (admin/admin)
4. Go to SQL Lab and select "Lakehouse (Trino)" database
5. Run queries against the `data` schema

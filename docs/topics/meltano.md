# Meltano - DataOps Platform for ELT Pipelines

## Overview

Meltano is an open-source DataOps platform that orchestrates ELT (Extract, Load, Transform) pipelines using the Singer ecosystem. It provides a CLI-driven, version-controlled approach to building and managing data integration workflows.

**In this lakehouse platform**, Meltano serves as the data ingestion layer: it extracts data from various sources using Singer taps and loads it into [Garage](garage.md) S3 as Parquet files, ready for transformation by [DBT](dbt.md) and querying by [Trino](trino.md).

## Why Meltano for This Platform?

**600+ Connectors**: Access to the entire Singer ecosystem via [Meltano Hub](https://hub.meltano.com) - databases, APIs, SaaS tools, and files.

**Version-Controlled Pipelines**: All configuration in YAML files - commit to Git, track changes, review with pull requests.

**CLI-First Approach**: Automate everything via command line - perfect for containerized deployments on Kubernetes.

**Extensible SDK**: Build custom Singer taps and targets using the [Meltano Singer SDK](https://sdk.meltano.com).

**Open Source**: Self-hosted, no vendor lock-in, active community maintained by Arch Data, Inc.

**Native Dagster Integration**: First-class support for orchestrating Meltano jobs with [Dagster](dagster.md).

## Key Concepts

### 1. Singer Specification

Meltano is built on the **Singer specification** - an open-source standard for data integration:

```
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│   Singer    │   JSON   │   Singer    │   JSON   │ Destination │
│     Tap     │ ────────▶│   Target    │ ────────▶│   (e.g.,    │
│  (Extract)  │  Stream  │   (Load)    │   Files  │   S3/DB)    │
└─────────────┘          └─────────────┘          └─────────────┘
```

**How it works:**
- **Taps** (extractors) read from sources and output JSON records to stdout
- **Targets** (loaders) read JSON from stdin and write to destinations
- Communication via **JSON streams** following Singer spec

### 2. Taps (Extractors)

A **tap** is a Singer-compliant extractor that pulls data from a source:

**Common taps:**
- `tap-postgres` - PostgreSQL databases
- `tap-mysql` - MySQL databases
- `tap-github` - GitHub API
- `tap-stripe` - Stripe API
- `tap-csv` - CSV files
- `tap-rest-api` - Generic REST APIs

**What a tap outputs:**
```json
{"type": "SCHEMA", "stream": "users", "schema": {...}}
{"type": "RECORD", "stream": "users", "record": {"id": 1, "name": "Alice"}}
{"type": "STATE", "value": {"bookmarks": {"users": {"updated_at": "2024-01-01"}}}}
```

### 3. Targets (Loaders)

A **target** is a Singer-compliant loader that writes data to a destination:

**Common targets for this platform:**
- `target-parquet` - Write Parquet files (for Garage S3)
- `target-s3` - Write to S3-compatible storage
- `target-postgres` - PostgreSQL databases
- `target-csv` - CSV files

**Target configuration for Garage:**
```yaml
targets:
  - name: target-parquet
    variant: meltanolabs
    pip_url: target-parquet
    config:
      filepath: s3://lakehouse/raw/
      aws_endpoint_url: http://garage.garage.svc.cluster.local:3900
      aws_access_key_id: ${AWS_ACCESS_KEY_ID}
      aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
```

### 4. Meltano Project Structure

```
meltano-project/
├── meltano.yml              # Project configuration
├── .meltano/                # Meltano internal files (gitignored)
├── extract/                 # Extractor configs
├── load/                    # Loader configs
├── transform/               # DBT project (optional)
├── orchestrate/             # Dagster definitions
├── .env                     # Environment variables (gitignored)
└── plugins/                 # Custom plugins
    ├── extractors/
    │   └── tap-custom/
    └── loaders/
        └── target-custom/
```

### 5. meltano.yml Configuration

The `meltano.yml` file defines your entire data platform:

```yaml
version: 1
project_id: lakehouse-project
default_environment: dev

plugins:
  extractors:
    - name: tap-postgres
      variant: transferwise
      pip_url: pipelinewise-tap-postgres
      config:
        host: ${PG_HOST}
        port: 5432
        user: ${PG_USER}
        password: ${PG_PASSWORD}
        dbname: production

  loaders:
    - name: target-parquet
      variant: meltanolabs
      pip_url: target-parquet
      config:
        filepath: s3://lakehouse/raw/
        aws_endpoint_url: http://garage:3900

  utilities:
    - name: dagster
      variant: meltano
      pip_url: dagster-meltano

jobs:
  - name: postgres-to-s3
    tasks:
      - tap-postgres target-parquet

schedules:
  - name: daily-sync
    job: postgres-to-s3
    interval: '@daily'
```

## Installation & Setup

### Prerequisites

```bash
# Python 3.8+
python --version

# pip package manager
pip --version
```

### Install Meltano

```bash
# Install Meltano CLI
pip install meltano

# Verify installation
meltano --version
```

### Initialize Project

```bash
# Create new Meltano project
meltano init lakehouse-ingestion
cd lakehouse-ingestion

# Project structure created:
# - meltano.yml (project config)
# - .meltano/ (plugins and state)
# - extract/, load/, transform/, orchestrate/
```

### Add Extractors and Loaders

```bash
# Search for available plugins
meltano discover extractors

# Add a tap (extractor)
meltano add extractor tap-postgres

# Add a target (loader)
meltano add loader target-parquet

# View installed plugins
meltano list plugins
```

### Configure Plugins

```bash
# Interactive configuration
meltano config tap-postgres set --interactive

# Or set individual values
meltano config tap-postgres set host localhost
meltano config tap-postgres set port 5432
meltano config tap-postgres set user myuser

# Use environment variables (recommended)
export TAP_POSTGRES_PASSWORD=secret
meltano config tap-postgres set password $TAP_POSTGRES_PASSWORD
```

### Test Extraction

```bash
# Test tap (outputs JSON to stdout)
meltano invoke tap-postgres

# Test full pipeline (tap | target)
meltano run tap-postgres target-parquet
```

## Dagster Integration

Meltano has **first-class Dagster integration** via the `dagster-meltano` library.

### Installation

```bash
# Install Dagster and Meltano integration
pip install dagster dagster-webserver dagster-meltano

# Or add to Meltano project
meltano add utility dagster
```

### Basic Integration Pattern

**Method 1: Load Jobs from Meltano Project**

```python
# dagster_defs.py
from dagster_meltano import load_jobs_from_meltano_project
from dagster import Definitions

# Automatically load all Meltano jobs as Dagster jobs
meltano_jobs = load_jobs_from_meltano_project(
    project_dir="/path/to/meltano-project"
)

defs = Definitions(jobs=meltano_jobs)
```

**Method 2: Manual Job Definition**

```python
from dagster_meltano import meltano_resource, meltano_run_op
import dagster as dg

@dg.job(resource_defs={"meltano": meltano_resource})
def postgres_ingestion_job():
    """Run Meltano ELT job: PostgreSQL → Parquet → S3"""
    meltano_run_op("tap-postgres target-parquet")()

defs = dg.Definitions(jobs=[postgres_ingestion_job])
```

### Asset-Based Pattern (Recommended)

```python
from dagster_meltano import meltano_resource
from dagster import asset, Definitions
import subprocess

@asset(
    compute_kind="meltano",
    description="Raw user data from PostgreSQL via Meltano"
)
def raw_users():
    """Extract users table from Postgres and load to S3 as Parquet"""
    result = subprocess.run(
        ["meltano", "run", "tap-postgres", "target-parquet"],
        cwd="/path/to/meltano-project",
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Meltano job failed: {result.stderr}")

    return result.stdout

defs = Definitions(
    assets=[raw_users],
    resources={"meltano": meltano_resource}
)
```

### Multi-Job Pipeline

```python
@dg.job(resource_defs={"meltano": meltano_resource})
def full_ingestion_pipeline():
    """Sequential Meltano job execution"""
    # Job 1: Extract from PostgreSQL
    postgres_done = meltano_run_op("tap-postgres target-parquet")()

    # Job 2: Extract from Stripe API (depends on Job 1)
    stripe_done = meltano_run_op("tap-stripe target-parquet")(postgres_done)

    # Job 3: Extract from GitHub API
    meltano_run_op("tap-github target-parquet")(stripe_done)

defs = Definitions(jobs=[full_ingestion_pipeline])
```

### Running in Dagster

```bash
# Start Dagster development server
dagster dev -f dagster_defs.py

# Access UI at http://localhost:3000
# Navigate to Jobs → Select job → Launch Run
```

## Common Workflows

### Add New Data Source

```bash
# 1. Discover available taps
meltano discover extractors --query="github"

# 2. Add tap
meltano add extractor tap-github

# 3. Configure
meltano config tap-github set --interactive

# 4. Test extraction
meltano invoke tap-github

# 5. Create job in meltano.yml
# jobs:
#   - name: github-to-s3
#     tasks:
#       - tap-github target-parquet

# 6. Run job
meltano run tap-github target-parquet
```

### Environment Management

```bash
# Define environments in meltano.yml
environments:
  - name: dev
    config:
      plugins:
        extractors:
          - name: tap-postgres
            config:
              host: localhost
              dbname: dev_db

  - name: prod
    config:
      plugins:
        extractors:
          - name: tap-postgres
            config:
              host: prod-db.example.com
              dbname: prod_db

# Run with specific environment
meltano --environment=prod run tap-postgres target-parquet
```

### Scheduling Jobs

**Option 1: Meltano Native Scheduling**

```yaml
# meltano.yml
schedules:
  - name: daily-postgres-sync
    job: postgres-to-s3
    interval: '@daily'
    start_date: 2024-01-01

  - name: hourly-api-sync
    job: github-to-s3
    interval: '0 * * * *'  # Cron syntax
```

```bash
# Start Meltano scheduler (uses Airflow internally)
meltano schedule list
meltano schedule run daily-postgres-sync
```

**Option 2: Dagster Scheduling (Recommended)**

```python
from dagster import schedule, ScheduleDefinition

@schedule(
    cron_schedule="0 0 * * *",  # Daily at midnight
    job=postgres_ingestion_job,
)
def daily_postgres_sync():
    return {}

defs = Definitions(
    jobs=[postgres_ingestion_job],
    schedules=[daily_postgres_sync]
)
```

### Incremental Syncs

Meltano automatically handles incremental loading via **state management**:

```bash
# First run: Full sync
meltano run tap-postgres target-parquet

# State saved to .meltano/run/logs/state.json
# {"bookmarks": {"users": {"updated_at": "2024-01-01T00:00:00Z"}}}

# Subsequent runs: Only new/changed data
meltano run tap-postgres target-parquet
```

**State file location:**
```
.meltano/
└── run/
    └── tap-postgres/
        └── target-parquet.state.json
```

## Kubernetes Deployment

### Containerize Meltano Project

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /project

# Install Meltano
RUN pip install meltano

# Copy project files
COPY meltano.yml .
COPY .meltano/ ./.meltano/
COPY plugins/ ./plugins/

# Install plugins
RUN meltano install

# Default command
CMD ["meltano", "run", "tap-postgres", "target-parquet"]
```

### Kubernetes Deployment

```yaml
# kubernetes/meltano-deployment.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: meltano-postgres-sync
  namespace: lakehouse
spec:
  schedule: "0 0 * * *"  # Daily at midnight
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: meltano
            image: lakehouse/meltano:latest
            command: ["meltano", "run", "tap-postgres", "target-parquet"]
            env:
            - name: TAP_POSTGRES_HOST
              value: "postgres.database.svc.cluster.local"
            - name: TAP_POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials
                  key: password
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: garage-credentials
                  key: access-key-id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: garage-credentials
                  key: secret-access-key
          restartPolicy: OnFailure
```

### Deploy with Dagster on Kubernetes

```yaml
# kubernetes/dagster-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dagster-webserver
  namespace: lakehouse
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dagster-webserver
  template:
    metadata:
      labels:
        app: dagster-webserver
    spec:
      containers:
      - name: dagster
        image: lakehouse/dagster-meltano:latest
        command: ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
        ports:
        - containerPort: 3000
        volumeMounts:
        - name: meltano-project
          mountPath: /meltano-project
      volumes:
      - name: meltano-project
        persistentVolumeClaim:
          claimName: meltano-project-pvc
```

## Best Practices

### 1. Version Control Everything

```bash
# Initialize Git repository
git init
git add meltano.yml
git commit -m "Initial Meltano project"

# Gitignore sensitive files
echo ".meltano/" >> .gitignore
echo ".env" >> .gitignore
echo "*.state.json" >> .gitignore
```

### 2. Use Environment Variables for Secrets

**Never hardcode secrets in meltano.yml:**

```yaml
# BAD: Hardcoded password
config:
  password: my_secret_password

# GOOD: Environment variable
config:
  password: ${TAP_POSTGRES_PASSWORD}
```

**Set via .env file:**
```bash
# .env (gitignored)
TAP_POSTGRES_PASSWORD=secret
TARGET_S3_ACCESS_KEY=GKxxxx
TARGET_S3_SECRET_KEY=xxxx
```

### 3. Pin Plugin Versions

```yaml
plugins:
  extractors:
    - name: tap-postgres
      variant: transferwise
      pip_url: pipelinewise-tap-postgres==1.8.2  # Pin version
```

### 4. Test Taps Before Production

```bash
# Test tap configuration
meltano invoke tap-postgres --discover

# Test with limited data
meltano invoke tap-postgres --catalog catalog.json --state state.json

# Validate output format
meltano invoke tap-postgres | head -n 100
```

### 5. Monitor State Files

```bash
# Check current state
cat .meltano/run/tap-postgres/target-parquet.state.json

# Backup state before major changes
cp .meltano/run/tap-postgres/target-parquet.state.json \
   state-backup-$(date +%Y%m%d).json
```

### 6. Organize Jobs by Domain

```yaml
jobs:
  # Sales data
  - name: sales-postgres-to-s3
    tasks:
      - tap-postgres-sales target-parquet

  # Marketing data
  - name: marketing-stripe-to-s3
    tasks:
      - tap-stripe target-parquet

  # Product data
  - name: product-github-to-s3
    tasks:
      - tap-github target-parquet
```

## Troubleshooting

### Tap Not Extracting Data

```bash
# Enable debug logging
meltano --log-level=debug invoke tap-postgres

# Check tap discovery (available streams)
meltano invoke tap-postgres --discover

# Validate catalog selection
meltano invoke tap-postgres --catalog catalog.json
```

### Target Write Errors

```bash
# Test target independently
echo '{"type": "RECORD", "stream": "test", "record": {"id": 1}}' | \
  meltano invoke target-parquet

# Check S3 connectivity
aws s3 ls s3://lakehouse/raw/ \
  --endpoint-url http://garage:3900
```

### State Management Issues

```bash
# Reset state (forces full sync next run)
rm .meltano/run/tap-postgres/target-parquet.state.json

# View current bookmarks
meltano state get tap-postgres target-parquet

# Set state manually
meltano state set tap-postgres target-parquet \
  '{"bookmarks": {"users": {"updated_at": "2024-01-01"}}}'
```

### Plugin Installation Failures

```bash
# Clear plugin cache
rm -rf .meltano/

# Reinstall plugins
meltano install

# Install specific plugin
meltano install extractor tap-postgres
```

## Comparison: Meltano vs dlt vs Airbyte

### When to Use Meltano

**Choose Meltano if you:**
- Want a **structured framework** with CLI and configuration files
- Need access to the **Singer ecosystem** (600+ connectors)
- Prefer **version-controlled pipelines** (GitOps approach)
- Have a team that **treats pipelines as code**
- Want **modularity without vendor lock-in**

**Strengths:**
- Singer ecosystem is mature and well-documented
- Configuration-driven (less code to write)
- Built-in environment management
- Active community and Meltano Hub

**Considerations:**
- Requires learning Meltano CLI and YAML configuration
- More opinionated than pure Python solutions
- State management can be complex for advanced use cases

### When to Use dlt

**Choose dlt if you:**
- Team is **Python-first** and comfortable writing code
- Want **minimal infrastructure overhead**
- Need **highly custom data pipelines**
- Already have orchestration (Dagster/Airflow) in place
- Want **no framework lock-in**

**Strengths:**
- Pure Python library (pip install dlt)
- Runs anywhere Python runs
- No CLI or configuration files to learn
- Fastest performance (2.8x-6x faster than alternatives)

**Comparison:**
```python
# dlt approach - pure Python
import dlt

@dlt.source
def postgres_source():
    return dlt.resource(...)

pipeline = dlt.pipeline(destination="parquet")
pipeline.run(postgres_source())
```

```yaml
# Meltano approach - configuration
extractors:
  - name: tap-postgres
loaders:
  - name: target-parquet
jobs:
  - name: sync
    tasks:
      - tap-postgres target-parquet
```

### Migration from Airbyte

**If migrating from Airbyte:**

| Airbyte Concept | Meltano Equivalent |
|-----------------|-------------------|
| Source Connector | Tap (Extractor) |
| Destination Connector | Target (Loader) |
| Connection | Job |
| Sync Schedule | Schedule |
| Workspace | Meltano Project |
| UI Configuration | meltano.yml + CLI |

**Advantages over Airbyte:**
- No need for heavy UI/database infrastructure
- Lightweight containers (Python + CLI only)
- Everything version-controlled in Git
- Easier to automate with CI/CD

**Trade-offs:**
- No graphical UI (CLI only)
- Requires comfort with terminal and YAML
- Self-service for non-technical users not possible

## Next Steps

### For This Platform

1. **Initialize Meltano project** in `ingestion/meltano/`
2. **Add taps** for your data sources (PostgreSQL, APIs, etc.)
3. **Configure target-parquet** pointing to Garage S3
4. **Integrate with Dagster** for orchestration
5. **Test locally** with `meltano run`
6. **Containerize** for Kubernetes deployment
7. **Set up schedules** in Dagster

### Learning Resources

- **Official Docs**: [docs.meltano.com](https://docs.meltano.com)
- **Meltano Hub**: [hub.meltano.com](https://hub.meltano.com) - Browse 600+ connectors
- **Singer SDK**: [sdk.meltano.com](https://sdk.meltano.com) - Build custom taps/targets
- **Dagster Integration**: [docs.dagster.io/integrations/libraries/meltano](https://docs.dagster.io/integrations/libraries/meltano)
- **Slack Community**: [meltano.com/slack](https://meltano.com/slack)

### Example Projects

Check out MeltanoLabs on GitHub for production-grade examples:
- [tap-github](https://github.com/MeltanoLabs/tap-github)
- [tap-postgres](https://github.com/MeltanoLabs/tap-postgres)
- [target-parquet](https://github.com/MeltanoLabs/target-parquet)

---

**Platform Integration**: In the next phase, we'll deploy Meltano in the `lakehouse` namespace, configure it to write to Garage S3, and orchestrate jobs with Dagster for a complete ELT pipeline.

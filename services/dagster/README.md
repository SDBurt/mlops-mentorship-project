# Orchestration - Dagster with Iceberg

Dagster orchestration for Reddit data ingestion using **dagster-iceberg** IO manager and **Nessie** REST catalog.

## Architecture

```
Reddit API (PRAW) → Dagster Assets → dagster-iceberg IO Manager → Nessie Catalog → MinIO S3
                                                                                      ↓
                                                                               Iceberg Tables
                                                                                      ↓
                                                                                   Trino
```

## Quick Start

### 1. Install Dependencies

**Using uv (recommended):**
```bash
uv sync
source .venv/bin/activate  # MacOS/Linux
# or .venv\Scripts\activate on Windows
```

**Using pip:**
```bash
python3 -m venv .venv
source .venv/bin/activate  # MacOS/Linux
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Set PyIceberg and Reddit credentials
source set_pyiceberg_env.sh

# Set your Reddit API credentials
export REDDIT_CLIENT_ID="your_client_id_here"
export REDDIT_CLIENT_SECRET="your_client_secret_here"
export REDDIT_USER_AGENT="lakehouse:v1.0.0 (by /u/your_username)"
```

**Getting Reddit API Credentials:**
1. Go to https://www.reddit.com/prefs/apps
2. Create an app (select "script" type)
3. Copy the client ID and secret

### 3. Port-Forward Services (if running locally)

```bash
# Terminal 1: Nessie
kubectl port-forward -n lakehouse svc/nessie 19120:19120

# Terminal 2: MinIO
kubectl port-forward -n lakehouse svc/minio 9000:9000
```

### 4. Run Dagster

```bash
uv run dagster dev
# or if not using uv:
# dagster dev
```

Access Dagster UI at http://localhost:3000

**Note:** Use `dagster dev` (not `dg dev`). The `dg` command is for Dagster's new code generation structure.

### 5. Materialize Assets

In Dagster UI:
1. Navigate to "Assets"
2. Select `reddit_posts` or `reddit_comments`
3. Click "Materialize"

Or via CLI:
```bash
dagster asset materialize -m orchestration_dagster.definitions -a reddit_posts
```

## Project Structure

```
orchestration-dagster/
├── src/orchestration_dagster/
│   ├── definitions.py              # Dagster asset/job definitions
│   ├── partitions.py              # Partition definitions (for future use)
│   ├── resources/
│   │   ├── iceberg.py             # Iceberg IO manager configuration
│   │   └── __init__.py
│   └── sources/
│       ├── reddit.py              # Reddit data source (PRAW)
│       └── __init__.py
├── iceberg_config.yaml            # PyIceberg catalog configuration
├── set_pyiceberg_env.sh           # Environment setup script
├── pyproject.toml                 # Python dependencies
└── README.md                      # This file
```

## Data Assets

### reddit_posts
Extracts Reddit posts from a specified subreddit.

**Parameters:**
- `subreddit`: Subreddit name (default: "dataengineering")
- `time_filter`: Time period ("day", "week", "month", "year", "all")
- `limit`: Max posts to retrieve (default: 100)

**Output Table:** `lakehouse.raw.reddit_posts`

### reddit_comments
Extracts comments from top posts in a subreddit.

**Parameters:**
- `subreddit`: Subreddit name (default: "dataengineering")
- `time_filter`: Time period for selecting posts
- `post_limit`: Number of posts to get comments from (default: 25)
- `comment_limit`: Comments per post (default: 10)

**Output Table:** `lakehouse.raw.reddit_comments`

## Iceberg IO Manager

The `dagster-iceberg` IO manager automatically handles:
- **Table Creation**: Infers schema from pandas DataFrame
- **Partitioning**: Uses `partition_expr` metadata (e.g., `created_utc`)
- **Upserts**: Merges data based on primary key (`id` column)
- **Schema Evolution**: Handles new columns automatically
- **Catalog Integration**: Writes metadata to Nessie REST catalog
- **S3 Storage**: Persists Parquet files to MinIO

## Querying Data with Trino

```sql
-- List tables
SHOW TABLES FROM lakehouse.raw;

-- Query Reddit posts
SELECT
    subreddit,
    title,
    score,
    num_comments,
    created_utc
FROM lakehouse.raw.reddit_posts
ORDER BY score DESC
LIMIT 10;

-- Join posts and comments
SELECT
    p.title,
    COUNT(c.id) as comment_count
FROM lakehouse.raw.reddit_posts p
LEFT JOIN lakehouse.raw.reddit_comments c ON p.id = c.link_id
GROUP BY p.title
ORDER BY comment_count DESC;
```

## Troubleshooting

### "Reddit credentials not found"
Set environment variables:
```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
```

### "Cannot connect to catalog"
Port-forward services:
```bash
kubectl port-forward -n lakehouse svc/nessie 19120:19120
kubectl port-forward -n lakehouse svc/minio 9000:9000
```

## Learn More

- [dagster-iceberg Documentation](https://docs.dagster.io/integrations/libraries/iceberg)
- [PRAW Documentation](https://praw.readthedocs.io/)
- [Nessie Documentation](https://projectnessie.org/)
- [Migration Summary](../MIGRATION_SUMMARY.md)

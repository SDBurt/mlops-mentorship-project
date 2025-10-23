# Architecture Deep Dive

This document provides detailed technical architecture and design decisions for the Modern Data Lakehouse Platform.

## Table of Contents

- [System Architecture](#system-architecture)
- [Data Flow](#data-flow)
- [Storage Architecture](#storage-architecture)
- [Apache Iceberg Integration](#apache-iceberg-integration)
- [Query Processing](#query-processing)
- [Orchestration](#orchestration)
- [Data Modeling](#data-modeling)
- [Real-Time Ingestion](#real-time-ingestion)
- [MLOps Workflows](#mlops-workflows)
- [Lakehouse Governance](#lakehouse-governance)
- [Configuration Details](#configuration-details)
- [Performance Optimization](#performance-optimization)
- [Security](#security)

## System Architecture

### Infrastructure Layer

**Kubernetes**
- Container orchestration platform
- Manages all service deployments
- Provides service discovery and load balancing
- Handles scaling and self-healing

**Storage**
- Garage: S3-compatible object storage for data lake
- PostgreSQL: Metadata stores for Airbyte, Dagster, and Trino catalogs
- Persistent Volumes: For stateful services

### Data Ingestion Layer

**Airbyte**
- ELT (Extract, Load, Transform) framework
- Custom source connectors for proprietary data sources
- Configurable sync schedules (batch and CDC)
- Writes raw data as Parquet files to Garage/S3
- Metadata tracking for incremental syncs

**Custom Connectors Architecture**
```
┌─────────────────────────────────────────────┐
│         Custom Airbyte Connector            │
│                                             │
│  ┌─────────────┐    ┌─────────────────┐   │
│  │   Source    │───▶│  Normalization  │   │
│  │  Connector  │    │   (Optional)    │   │
│  └─────────────┘    └─────────────────┘   │
│         │                    │              │
│         ▼                    ▼              │
│  ┌──────────────────────────────────┐     │
│  │    Parquet Writer (PyArrow)      │     │
│  └──────────────────────────────────┘     │
│                   │                         │
└───────────────────┼─────────────────────────┘
                    ▼
          Garage S3 Bucket
```

### Storage Layer

**Garage (S3-Compatible Object Storage)**
- Distributed, geo-replicated object storage
- S3 API compatibility for universal tooling support
- Local deployment for development
- Production-ready distributed architecture

**Storage Layout**
```
s3://datalake/
├── raw/                    # Raw ingested data (Bronze)
│   ├── source_name/
│   │   ├── table_name/
│   │   │   └── partition_date=2024-01-01/
│   │   │       └── data.parquet
├── processed/              # Cleaned data (Silver)
│   ├── domain/
│   │   └── table_name/
│   │       └── metadata/
│   │           └── v1.metadata.json
└── analytics/              # Aggregated data (Gold)
    ├── metrics/
    └── reports/
```

**Apache Iceberg Table Format**

Iceberg provides a table format layer on top of Parquet files:

```
Iceberg Table
├── Metadata Files
│   ├── v1.metadata.json       # Table metadata
│   ├── snap-001.avro          # Snapshot manifest
│   └── manifest-list.avro     # List of manifests
├── Manifest Files
│   └── manifest-001.avro      # File-level metadata
└── Data Files
    └── *.parquet              # Actual data
```

**Benefits:**
- ACID transactions via optimistic concurrency
- Schema evolution (add/drop/rename columns)
- Time travel queries
- Hidden partitioning (partition pruning without exposing partitions to users)
- Incremental processing
- Efficient metadata operations

## Data Flow

### Ingestion Flow

```
1. Source System
   │
   ├─▶ Airbyte Source Connector
   │   │
   │   ├─▶ Extract data (full or incremental)
   │   │
   │   └─▶ Stream to destination
   │
2. Transformation (Optional)
   │
   └─▶ Airbyte normalization (basic transformations)

3. Storage
   │
   ├─▶ Write Parquet files to Garage/S3
   │
   └─▶ Register as Iceberg table

4. Cataloging
   │
   └─▶ Update Iceberg metadata
       └─▶ New snapshot created
```

### Query Flow

```
1. User Query (SQL)
   │
   └─▶ Trino Coordinator
       │
       ├─▶ Parse and plan query
       │
       ├─▶ Query Iceberg catalog
       │   └─▶ Get latest snapshot metadata
       │
       ├─▶ Partition pruning via Iceberg metadata
       │
       └─▶ Distribute to Trino Workers
           │
           ├─▶ Read Parquet files from Garage/S3
           │
           ├─▶ Execute query fragments
           │
           └─▶ Return results
```

### Transformation Flow (DBT + Dagster)

```
1. Dagster Sensor/Schedule
   │
   └─▶ Trigger DBT job
       │
       ├─▶ Read from raw/processed Iceberg tables
       │
       ├─▶ Apply transformations (SQL)
       │   ├─▶ Data quality checks
       │   ├─▶ Business logic
       │   └─▶ Aggregations
       │
       ├─▶ Write to new Iceberg tables
       │
       └─▶ Update lineage in Dagster
```

## Apache Iceberg Integration

### Catalog Configuration

**Hive Metastore** (Phase 2)
```yaml
catalog:
  type: hive
  uri: thrift://hive-metastore:9083
  warehouse: s3://datalake/
```

**REST Catalog** (Recommended for Phase 3)
```yaml
catalog:
  type: rest
  uri: http://iceberg-rest-catalog:8181
  warehouse: s3://datalake/
  s3:
    endpoint: http://garage-s3-api:3900
    access-key-id: ${S3_ACCESS_KEY}
    secret-access-key: ${S3_SECRET_KEY}
```

### Table Schema Evolution

Iceberg supports non-breaking schema changes:

```sql
-- Add column (safe operation)
ALTER TABLE processed.users
ADD COLUMN email_verified BOOLEAN;

-- Rename column (safe operation)
ALTER TABLE processed.users
RENAME COLUMN old_name TO new_name;

-- Drop column (safe operation, data remains)
ALTER TABLE processed.users
DROP COLUMN deprecated_field;
```

### Partitioning Strategy

**Hidden Partitioning**

Iceberg uses hidden partitioning - users don't write partition values in queries:

```sql
-- Table definition
CREATE TABLE processed.events (
  event_id STRING,
  user_id STRING,
  event_time TIMESTAMP,
  event_data STRING
)
PARTITIONED BY (days(event_time));  -- Partition by day

-- Query (no partition filter needed!)
SELECT * FROM processed.events
WHERE event_time >= '2024-01-01'  -- Iceberg auto-prunes partitions
```

**Partition Evolution**

Change partitioning without rewriting data:

```sql
-- Start with hourly partitioning
CREATE TABLE events (...) PARTITIONED BY (hours(event_time));

-- Later, change to daily (no data rewrite!)
ALTER TABLE events
SET PARTITION SPEC (days(event_time));
```

### Time Travel

Query historical data snapshots:

```sql
-- Query as of timestamp
SELECT * FROM processed.users
FOR SYSTEM_TIME AS OF '2024-01-01 00:00:00';

-- Query specific snapshot
SELECT * FROM processed.users
FOR SYSTEM_VERSION AS OF 123456789;

-- View snapshot history
SELECT * FROM processed.users.snapshots;
```

## Query Processing

### Trino Architecture

**Coordinator**
- Query parsing and planning
- Metadata operations via Iceberg catalog
- Task scheduling
- Result aggregation

**Workers**
- Parallel data processing
- Direct S3 reads from Garage
- Columnar processing (Parquet)
- Vectorized execution

**Iceberg Connector Configuration**

```yaml
connector.name=iceberg
hive.metastore.uri=thrift://hive-metastore:9083
iceberg.catalog.type=hive
hive.s3.endpoint=http://garage-s3-api:3900
hive.s3.aws-access-key=${S3_ACCESS_KEY}
hive.s3.aws-secret-key=${S3_SECRET_KEY}
hive.s3.path-style-access=true
```

### Query Optimization

**Metadata-based Pruning**
- Iceberg tracks min/max values per file
- Partition pruning without scanning data
- Aggressive predicate pushdown

**Columnar Processing**
- Parquet columnar format
- Read only required columns
- Vectorized execution in Trino

**Statistics**
- Iceberg maintains column statistics
- Trino uses stats for cost-based optimization
- Automatic table statistics collection

## Orchestration

### Dagster Software-Defined Assets

Assets represent data products in the lakehouse:

```python
from dagster import asset, AssetIn
from dagster_dbt import dbt_assets

@asset(
    group_name="ingestion",
    compute_kind="airbyte"
)
def raw_users_table():
    """Raw users data ingested from production database."""
    # Trigger Airbyte sync
    trigger_airbyte_sync("users_connection")

@dbt_assets(
    manifest=dbt_manifest_path,
    project_dir=dbt_project_dir
)
def dbt_models(context, raw_users_table):
    """DBT models for data transformation."""
    yield from run_dbt_models(context)

@asset(
    ins={"users": AssetIn("dbt_users_silver")},
    group_name="analytics"
)
def user_metrics(users):
    """Aggregate user metrics for dashboards."""
    return compute_metrics(users)
```

### Dagster + DBT Integration

**Benefits:**
- DBT models as Dagster assets
- Automatic lineage from DBT DAG
- Test results integrated in Dagster UI
- Schedule DBT runs with sensors
- Version-controlled transformations

**Configuration:**

```yaml
# profiles.yml for DBT
lakehouse:
  target: dev
  outputs:
    dev:
      type: trino
      method: none
      host: trino-coordinator
      port: 8080
      database: iceberg
      schema: processed
      threads: 4
```

## Data Modeling

### Star Schema Design (Phase 2 Focus)

The lakehouse implements **dimensional modeling** using the star schema pattern in the Gold layer for optimal analytics performance.

**Why Star Schema?**

Star schema is the standard for data warehousing and BI, providing:
- Simple, intuitive structure for analysts
- Fast query performance (fewer joins)
- Easy to understand business context
- Optimal for BI tools (Superset, Tableau, Power BI)
- Denormalized for read-heavy analytics workloads

### Star Schema Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Gold Layer                             │
│              (Star Schema - Analytics-Ready)               │
└────────────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │         Fact Tables                 │
        │  (Metrics, measurements, events)    │
        └─────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┬──────────┐
       │               │               │          │
       ▼               ▼               ▼          ▼
┌──────────┐    ┌──────────┐    ┌──────────┐  ┌──────────┐
│  Dim     │    │   Dim    │    │   Dim    │  │   Dim    │
│  Date    │    │  Product │    │ Customer │  │ Location │
└──────────┘    └──────────┘    └──────────┘  └──────────┘

Central fact table surrounded by dimension tables
```

### Example E-commerce Star Schema

**Fact Table: `fct_orders`**

```sql
CREATE TABLE analytics.fct_orders (
    -- Surrogate key
    order_key BIGINT,

    -- Foreign keys to dimensions
    date_key INT,
    customer_key BIGINT,
    product_key BIGINT,
    location_key BIGINT,

    -- Degenerate dimensions (attributes that don't need separate dimension)
    order_id STRING,
    order_number STRING,

    -- Measures (metrics)
    quantity INT,
    unit_price DECIMAL(10,2),
    discount_amount DECIMAL(10,2),
    tax_amount DECIMAL(10,2),
    total_amount DECIMAL(10,2),

    -- Audit columns
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
USING iceberg
PARTITIONED BY (months(date_key))
```

**Dimension Table: `dim_customer`**

```sql
CREATE TABLE analytics.dim_customer (
    -- Surrogate key
    customer_key BIGINT,

    -- Natural key
    customer_id STRING,

    -- Type 2 SCD attributes (track history)
    customer_name STRING,
    email STRING,
    segment STRING,  -- e.g., 'Enterprise', 'SMB', 'Individual'

    -- Demographics
    country STRING,
    state STRING,
    city STRING,

    -- Behavioral attributes
    lifetime_value DECIMAL(15,2),
    total_orders INT,
    first_order_date DATE,

    -- SCD Type 2 tracking
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN,

    -- Audit
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
USING iceberg
```

**Dimension Table: `dim_product`**

```sql
CREATE TABLE analytics.dim_product (
    -- Surrogate key
    product_key BIGINT,

    -- Natural key
    product_id STRING,
    sku STRING,

    -- Product attributes
    product_name STRING,
    description STRING,
    brand STRING,
    category STRING,
    subcategory STRING,

    -- Hierarchical attributes for drill-down
    department STRING,
    section STRING,

    -- Pricing
    list_price DECIMAL(10,2),
    cost DECIMAL(10,2),

    -- Flags
    is_active BOOLEAN,
    is_featured BOOLEAN,

    -- SCD Type 2
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN,

    -- Audit
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
USING iceberg
```

**Dimension Table: `dim_date`**

```sql
CREATE TABLE analytics.dim_date (
    -- Surrogate key
    date_key INT,  -- e.g., 20240115 for 2024-01-15

    -- Date attributes
    full_date DATE,
    day_of_week INT,
    day_name STRING,  -- 'Monday', 'Tuesday', etc.
    day_of_month INT,
    day_of_year INT,

    -- Week attributes
    week_of_year INT,
    week_start_date DATE,
    week_end_date DATE,

    -- Month attributes
    month INT,
    month_name STRING,  -- 'January', 'February', etc.
    month_start_date DATE,
    month_end_date DATE,

    -- Quarter attributes
    quarter INT,
    quarter_name STRING,  -- 'Q1', 'Q2', etc.
    quarter_start_date DATE,
    quarter_end_date DATE,

    -- Year attributes
    year INT,
    fiscal_year INT,
    fiscal_quarter INT,

    -- Flags
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name STRING,

    -- Business calendar
    is_business_day BOOLEAN,
    business_day_of_month INT,
    business_day_of_year INT
)
USING iceberg
```

### DBT Implementation of Star Schema

**Directory Structure:**

```
transformations/dbt/models/marts/
├── core/
│   ├── dim_customer.sql
│   ├── dim_product.sql
│   ├── dim_date.sql
│   └── fct_orders.sql
├── finance/
│   ├── dim_account.sql
│   └── fct_transactions.sql
└── marketing/
    ├── dim_campaign.sql
    └── fct_campaign_performance.sql
```

**Example DBT Model: `dim_customer.sql`**

```sql
{{
  config(
    materialized='incremental',
    unique_key='customer_key',
    file_format='iceberg',
    incremental_strategy='merge'
  )
}}

WITH source_customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

customers_with_metrics AS (
    SELECT
        c.*,
        COALESCE(SUM(o.total_amount), 0) AS lifetime_value,
        COUNT(DISTINCT o.order_id) AS total_orders,
        MIN(o.order_date) AS first_order_date
    FROM source_customers c
    LEFT JOIN {{ ref('stg_orders') }} o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_id, c.customer_name, c.email, ...
),

final AS (
    SELECT
        {{ dbt_utils.surrogate_key(['customer_id', 'valid_from']) }} AS customer_key,
        customer_id,
        customer_name,
        email,
        CASE
            WHEN lifetime_value > 10000 THEN 'Enterprise'
            WHEN lifetime_value > 1000 THEN 'SMB'
            ELSE 'Individual'
        END AS segment,
        country,
        state,
        city,
        lifetime_value,
        total_orders,
        first_order_date,
        updated_at AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,  -- Current record
        TRUE AS is_current,
        CURRENT_TIMESTAMP() AS created_at,
        CURRENT_TIMESTAMP() AS updated_at
    FROM customers_with_metrics
)

SELECT * FROM final

{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

**Example DBT Model: `fct_orders.sql`**

```sql
{{
  config(
    materialized='incremental',
    unique_key='order_key',
    file_format='iceberg',
    incremental_strategy='append'
  )
}}

WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),

orders_aggregated AS (
    SELECT
        o.order_id,
        o.order_date,
        o.customer_id,
        oi.product_id,
        o.location_id,
        SUM(oi.quantity) AS quantity,
        AVG(oi.unit_price) AS unit_price,
        SUM(oi.discount_amount) AS discount_amount,
        SUM(oi.tax_amount) AS tax_amount,
        SUM(oi.line_total) AS total_amount,
        o.created_at,
        o.updated_at
    FROM orders o
    INNER JOIN order_items oi
        ON o.order_id = oi.order_id
    GROUP BY
        o.order_id,
        o.order_date,
        o.customer_id,
        oi.product_id,
        o.location_id,
        o.created_at,
        o.updated_at
),

final AS (
    SELECT
        {{ dbt_utils.surrogate_key(['o.order_id', 'o.product_id']) }} AS order_key,

        -- Foreign keys (lookup in dimension tables)
        CAST(TO_CHAR(o.order_date, 'YYYYMMDD') AS INT) AS date_key,
        c.customer_key,
        p.product_key,
        l.location_key,

        -- Degenerate dimensions
        o.order_id,
        o.order_number,

        -- Measures
        o.quantity,
        o.unit_price,
        o.discount_amount,
        o.tax_amount,
        o.total_amount,

        -- Audit
        o.created_at,
        o.updated_at
    FROM orders_aggregated o
    LEFT JOIN {{ ref('dim_customer') }} c
        ON o.customer_id = c.customer_id AND c.is_current = TRUE
    LEFT JOIN {{ ref('dim_product') }} p
        ON o.product_id = p.product_id AND p.is_current = TRUE
    LEFT JOIN {{ ref('dim_location') }} l
        ON o.location_id = l.location_id
)

SELECT * FROM final

{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

### Slowly Changing Dimensions (SCD)

**Type 1 (Overwrite)**: No history tracking, simple updates

```sql
-- Example: Update product price (losing history)
UPDATE analytics.dim_product
SET list_price = 99.99, updated_at = CURRENT_TIMESTAMP()
WHERE product_id = 'PROD-123' AND is_current = TRUE;
```

**Type 2 (History Tracking)**: Full history preserved with validity dates

```sql
-- Example DBT macro for Type 2 SCD
{% snapshot customers_snapshot %}

{{
    config(
      target_schema='analytics',
      unique_key='customer_id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

SELECT * FROM {{ source('raw', 'customers') }}

{% endsnapshot %}
```

**Type 3 (Previous Value)**: Track one previous value

```sql
-- Dimension table with previous value columns
CREATE TABLE analytics.dim_product (
    product_key BIGINT,
    product_id STRING,
    current_price DECIMAL(10,2),
    previous_price DECIMAL(10,2),
    price_changed_date DATE
)
```

### Query Examples

**Simple Aggregation:**

```sql
-- Total sales by month and product category
SELECT
    d.month_name,
    d.year,
    p.category,
    SUM(f.total_amount) AS total_sales,
    COUNT(DISTINCT f.order_id) AS order_count,
    AVG(f.total_amount) AS avg_order_value
FROM analytics.fct_orders f
INNER JOIN analytics.dim_date d
    ON f.date_key = d.date_key
INNER JOIN analytics.dim_product p
    ON f.product_key = p.product_key
WHERE d.year = 2024
GROUP BY d.month_name, d.year, p.category
ORDER BY d.year, d.month, total_sales DESC;
```

**Customer Segmentation Analysis:**

```sql
-- Sales performance by customer segment
SELECT
    c.segment,
    COUNT(DISTINCT f.customer_key) AS customer_count,
    SUM(f.total_amount) AS total_sales,
    AVG(f.total_amount) AS avg_order_value,
    SUM(f.quantity) AS total_units_sold
FROM analytics.fct_orders f
INNER JOIN analytics.dim_customer c
    ON f.customer_key = c.customer_key
WHERE c.is_current = TRUE
GROUP BY c.segment
ORDER BY total_sales DESC;
```

**Time Series Analysis:**

```sql
-- Year-over-year comparison
WITH sales_2023 AS (
    SELECT
        d.month,
        SUM(f.total_amount) AS sales_2023
    FROM analytics.fct_orders f
    INNER JOIN analytics.dim_date d
        ON f.date_key = d.date_key
    WHERE d.year = 2023
    GROUP BY d.month
),
sales_2024 AS (
    SELECT
        d.month,
        SUM(f.total_amount) AS sales_2024
    FROM analytics.fct_orders f
    INNER JOIN analytics.dim_date d
        ON f.date_key = d.date_key
    WHERE d.year = 2024
    GROUP BY d.month
)
SELECT
    s23.month,
    s23.sales_2023,
    s24.sales_2024,
    s24.sales_2024 - s23.sales_2023 AS sales_change,
    ROUND((s24.sales_2024 - s23.sales_2023) / s23.sales_2023 * 100, 2) AS pct_change
FROM sales_2023 s23
INNER JOIN sales_2024 s24
    ON s23.month = s24.month
ORDER BY s23.month;
```

### Star Schema Best Practices

**1. Use Surrogate Keys**
- Auto-generated integers for dimension primary keys
- Protects against source system changes
- Improves join performance

**2. Denormalize for Performance**
- Flatten hierarchies in dimensions when possible
- Accept some data duplication for query speed
- Gold layer optimized for reads, not writes

**3. Pre-compute Aggregates**
- Create aggregate fact tables for common queries
- Example: `fct_daily_sales_summary`, `fct_monthly_kpis`
- Trade storage for query performance

**4. Implement Slowly Changing Dimensions**
- Use Type 2 SCD for important historical tracking
- Type 1 for attributes that don't need history
- Type 3 rarely (limited previous value tracking)

**5. Maintain Date Dimension**
- Pre-populate for several years
- Include all calendar and fiscal attributes
- Essential for time-based analysis

## Real-Time Ingestion (Phase 5 - Learning Focus)

### Overview

Real-time ingestion enables the lakehouse to process streaming data with low latency, complementing the batch processing foundation built in earlier phases.

**Learning Goals for Phase 5:**
- Understand event streaming fundamentals
- Master Kafka (or alternative) deployment and operations
- Learn stream processing patterns and windowing
- Integrate real-time data with batch lakehouse
- Handle late-arriving and out-of-order events

### Architectural Options

**Option 1: Apache Kafka** (Industry standard)

```
┌─────────────────────────────────────────────────────┐
│              Data Sources (Real-time)               │
│  Clickstreams, IoT sensors, CDC, Application logs   │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              Apache Kafka Cluster                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  Broker 1  │  │  Broker 2  │  │  Broker 3  │   │
│  └────────────┘  └────────────┘  └────────────┘   │
│                                                     │
│  Topics: events, clickstream, sensor_data, cdc     │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐    ┌───────────────────────┐
│  Kafka Connect   │    │  Stream Processing    │
│  (Sources)       │    │  (Flink or Streams)   │
└──────────────────┘    └──────────┬────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Iceberg Sink        │
                        │  (Real-time writes)  │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   Garage S3 Bucket   │
                        │  (Bronze Layer)      │
                        └──────────────────────┘
```

**Pros:**
- Industry standard, battle-tested
- Rich ecosystem (Connect, Streams, KSQL)
- Excellent documentation and community
- Mature tooling and monitoring

**Cons:**
- Complex to operate (ZooKeeper management - though KRaft mode eliminates this)
- Resource intensive (requires dedicated infrastructure)
- Steeper learning curve

**Option 2: Redpanda** (Kafka-compatible alternative)

```
┌─────────────────────────────────────────────────────┐
│              Redpanda Cluster                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  Node 1    │  │  Node 2    │  │  Node 3    │   │
│  │  (C++)     │  │  (C++)     │  │  (C++)     │   │
│  └────────────┘  └────────────┘  └────────────┘   │
│                                                     │
│  - No ZooKeeper needed                             │
│  - Kafka API compatible                            │
│  - Lower resource usage                            │
└─────────────────────────────────────────────────────┘
```

**Pros:**
- Kafka API compatible (drop-in replacement)
- No ZooKeeper dependency
- Lower operational complexity
- Better performance per node
- Easier for learning

**Cons:**
- Smaller ecosystem
- Less mature than Kafka
- Fewer community resources

### Kafka Deployment on Kubernetes

**Namespace:** `streaming`

```yaml
# Kafka StatefulSet (simplified)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
  namespace: streaming
spec:
  serviceName: kafka-headless
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
      - name: kafka
        image: confluentinc/cp-kafka:7.5.0
        ports:
        - containerPort: 9092
          name: client
        - containerPort: 9093
          name: internal
        env:
        - name: KAFKA_BROKER_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: KAFKA_ZOOKEEPER_CONNECT
          value: "zookeeper:2181"
        - name: KAFKA_ADVERTISED_LISTENERS
          value: "PLAINTEXT://$(POD_NAME).kafka-headless:9092"
        volumeMounts:
        - name: kafka-data
          mountPath: /var/lib/kafka/data
  volumeClaimTemplates:
  - metadata:
      name: kafka-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi
```

### Stream Processing Patterns

**Pattern 1: Kafka → Flink → Iceberg**

```python
# PyFlink example: Real-time aggregation
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

# Setup
env = StreamExecutionEnvironment.get_execution_environment()
table_env = StreamTableEnvironment.create(env)

# Source: Kafka topic
table_env.execute_sql("""
    CREATE TABLE clickstream (
        user_id STRING,
        event_time TIMESTAMP(3),
        page_url STRING,
        event_type STRING,
        WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'clickstream',
        'properties.bootstrap.servers' = 'kafka:9092',
        'format' = 'json'
    )
""")

# Sink: Iceberg table
table_env.execute_sql("""
    CREATE TABLE analytics.realtime_page_views (
        page_url STRING,
        hour_window TIMESTAMP(3),
        view_count BIGINT,
        unique_users BIGINT
    ) WITH (
        'connector' = 'iceberg',
        'catalog-name' = 'lakehouse',
        'warehouse' = 's3://datalake/'
    )
""")

# Streaming aggregation
table_env.execute_sql("""
    INSERT INTO analytics.realtime_page_views
    SELECT
        page_url,
        TUMBLE_START(event_time, INTERVAL '1' HOUR) AS hour_window,
        COUNT(*) AS view_count,
        COUNT(DISTINCT user_id) AS unique_users
    FROM clickstream
    GROUP BY
        page_url,
        TUMBLE(event_time, INTERVAL '1' HOUR)
""")
```

**Pattern 2: Kafka Streams → Iceberg**

```java
// Kafka Streams example
StreamsBuilder builder = new StreamsBuilder();

// Source stream
KStream<String, ClickEvent> clicks = builder.stream("clickstream");

// Windowed aggregation
KTable<Windowed<String>, PageViewCount> pageViews = clicks
    .groupBy((key, click) -> click.getPageUrl())
    .windowedBy(TimeWindows.of(Duration.ofHours(1)))
    .aggregate(
        PageViewCount::new,
        (key, click, count) -> count.increment(),
        Materialized.with(Serdes.String(), pageViewCountSerde)
    );

// Sink to Iceberg (custom connector)
pageViews.toStream()
    .to("iceberg-sink", Produced.with(windowedSerde, pageViewCountSerde));
```

**Pattern 3: Lambda Architecture (Batch + Stream)**

```
Real-time Layer (Speed):
Kafka → Flink → Iceberg (bronze_realtime/)
↓ (1-hour latency)
Covers last 24-48 hours

Batch Layer (Precision):
Airbyte → Iceberg (bronze/)
↓
DBT transformations
↓
Gold layer (star schema)

Serving Layer:
UNION of real-time + batch data
Trino query automatically merges both
```

### Change Data Capture (CDC) Integration

**Debezium + Kafka Connect:**

```yaml
# Kafka Connect deployment with Debezium
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-connect
  namespace: streaming
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: kafka-connect
        image: debezium/connect:2.5
        ports:
        - containerPort: 8083
        env:
        - name: BOOTSTRAP_SERVERS
          value: "kafka:9092"
        - name: GROUP_ID
          value: "connect-cluster"
        - name: CONFIG_STORAGE_TOPIC
          value: "connect-configs"
```

**CDC Connector Configuration:**

```json
{
  "name": "postgres-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "${DB_PASSWORD}",
    "database.dbname": "production",
    "database.server.name": "prod-db",
    "table.include.list": "public.orders,public.customers",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "([^.]+)\\.([^.]+)\\.([^.]+)",
    "transforms.route.replacement": "cdc.$3"
  }
}
```

### Real-Time → Iceberg Integration

**Flink Iceberg Sink:**

```python
# Flink job: Stream CDC events to Iceberg
table_env.execute_sql("""
    CREATE TABLE bronze_realtime.orders (
        order_id STRING,
        customer_id STRING,
        order_date TIMESTAMP(3),
        total_amount DECIMAL(10,2),
        status STRING,
        created_at TIMESTAMP(3),
        updated_at TIMESTAMP(3)
    ) PARTITIONED BY (status)
    WITH (
        'connector' = 'iceberg',
        'catalog-name' = 'lakehouse',
        'warehouse' = 's3://datalake/',
        'format-version' = '2',
        'write.upsert.enabled' = 'true'
    )
""")

# Stream from Kafka CDC topic
table_env.execute_sql("""
    INSERT INTO bronze_realtime.orders
    SELECT
        CAST(after['order_id'] AS STRING),
        CAST(after['customer_id'] AS STRING),
        CAST(after['order_date'] AS TIMESTAMP(3)),
        CAST(after['total_amount'] AS DECIMAL(10,2)),
        CAST(after['status'] AS STRING),
        CAST(ts_ms AS TIMESTAMP(3)) AS created_at,
        CAST(ts_ms AS TIMESTAMP(3)) AS updated_at
    FROM kafka_cdc_orders
    WHERE op IN ('c', 'u')  -- Create and Update operations
""")
```

### Handling Late Data and Watermarks

```python
# Define watermark strategy
table_env.execute_sql("""
    CREATE TABLE clickstream (
        event_id STRING,
        user_id STRING,
        event_time TIMESTAMP(3),
        page_url STRING,
        -- Watermark: Allow 10 seconds of lateness
        WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'clickstream',
        'properties.bootstrap.servers' = 'kafka:9092',
        'format' = 'json',
        'scan.startup.mode' = 'earliest-offset'
    )
""")

# Windowed aggregation with late data handling
table_env.execute_sql("""
    INSERT INTO analytics.realtime_metrics
    SELECT
        window_start,
        window_end,
        page_url,
        COUNT(*) AS event_count,
        COUNT(DISTINCT user_id) AS unique_users
    FROM TABLE(
        TUMBLE(TABLE clickstream, DESCRIPTOR(event_time), INTERVAL '1' MINUTE)
    )
    GROUP BY window_start, window_end, page_url
""")
```

### Monitoring Real-Time Pipelines

**Key Metrics:**
- **Consumer Lag**: How far behind consumers are from latest messages
- **Throughput**: Messages/sec processed
- **Latency**: End-to-end event processing time
- **Error Rate**: Failed message processing
- **Watermark Delay**: How far watermark lags behind real-time

**Kafka Metrics (via Prometheus):**

```yaml
# ServiceMonitor for Kafka metrics
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kafka-metrics
  namespace: streaming
spec:
  selector:
    matchLabels:
      app: kafka
  endpoints:
  - port: metrics
    interval: 30s
```

### Learning Path for Real-Time

**Week 1-2: Kafka Fundamentals**
- Deploy Kafka on Kubernetes
- Understand topics, partitions, replicas
- Practice producers and consumers
- Learn consumer groups

**Week 3-4: Stream Processing**
- Deploy Flink or Kafka Streams
- Implement windowed aggregations
- Handle late data with watermarks
- Practice stateful transformations

**Week 5-6: Integration**
- Kafka → Iceberg integration
- CDC with Debezium
- Lambda architecture (batch + real-time)
- Query unified batch + streaming data

**Week 7-8: Production Operations**
- Monitoring and alerting
- Performance tuning
- Backpressure handling
- Disaster recovery

## MLOps Workflows (Phase 4)

This section describes the planned ML integration architecture with Kubeflow, Feast, and DVC.

### ML Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                 Data Lakehouse (Iceberg + Garage)                 │
│                   Bronze → Silver → Gold Layers                   │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│            Feature Engineering (Dagster + DBT)                    │
│      Aggregations, transformations, feature computation           │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                  Feast Feature Store                              │
│  ┌──────────────────────┐      ┌──────────────────────────────┐  │
│  │   Offline Store      │      │      Online Store            │  │
│  │  (Iceberg/Parquet)   │      │      (Redis)                 │  │
│  │  Training datasets   │      │  Low-latency serving (<10ms) │  │
│  └──────────────────────┘      └──────────────────────────────┘  │
└──────────┬────────────────────────────┬───────────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────────────┐  ┌──────────────────────────────────┐
│   Kubeflow Pipelines     │  │      Model Serving (KServe)      │
│  - Training workflows    │  │  - Online predictions            │
│  - Hyperparameter tuning │  │  - A/B testing                   │
│  - Model evaluation      │  │  - Canary deployments            │
└──────────┬───────────────┘  └──────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────────────────┐
│           DVC (Data Version Control)                              │
│  - Dataset versioning (Garage S3 backend)                        │
│  - Model registry                                                 │
│  - Experiment tracking                                            │
└───────────────────────────────────────────────────────────────────┘
```

### Feast Feature Store Integration

**Purpose:**

Feast provides a dual-store architecture for ML feature management, bridging the gap between batch feature engineering and low-latency model serving.

**Offline Store (Iceberg on Garage):**
- Historical feature data for training
- Point-in-time correct feature retrieval
- Backfills and batch feature computation
- Integrated with Iceberg for versioning and time travel

**Online Store (Redis):**
- Low-latency feature serving (<10ms)
- Real-time model inference
- Feature caching with TTL
- Supports high-throughput serving

**Configuration Example:**

```yaml
# feast/feature_store.yaml
project: lakehouse_ml
provider: local
registry: s3://datalake/feast/registry.db

offline_store:
  type: file
  path: s3://datalake/feast/offline

online_store:
  type: redis
  connection_string: redis-feast:6379
  key_ttl: 86400  # 24 hours

entity_key_serialization_version: 2
```

**Feature Definition:**

```python
# feast/features.py
from feast import Entity, FeatureView, Field
from feast.types import Float32, Int64
from feast.data_source import FileSource

# Define entity
user = Entity(
    name="user_id",
    join_keys=["user_id"],
    description="User entity"
)

# Define feature view from Iceberg table
user_features_source = FileSource(
    path="s3://datalake/feast/user_features.parquet",
    timestamp_field="event_timestamp",
)

user_features = FeatureView(
    name="user_features",
    entities=[user],
    schema=[
        Field(name="total_purchases", dtype=Int64),
        Field(name="avg_order_value", dtype=Float32),
        Field(name="days_since_last_order", dtype=Int64),
        Field(name="lifetime_value", dtype=Float32),
    ],
    source=user_features_source,
    ttl=timedelta(days=365),
    tags={"layer": "gold", "domain": "ecommerce"}
)
```

**Dagster Integration for Feature Materialization:**

```python
from dagster import asset, AssetIn
import subprocess

@asset(
    ins={"gold_users": AssetIn("gold_user_metrics")},
    group_name="ml_features"
)
def feast_user_features(gold_users):
    """Materialize features to Feast offline store."""
    # Read from Iceberg gold layer
    features_df = spark.read.format("iceberg") \
        .load("analytics.user_metrics")

    # Transform for Feast format (add entity and timestamp)
    feast_features = features_df.select(
        col("user_id"),
        col("updated_at").alias("event_timestamp"),
        col("total_purchases"),
        col("avg_order_value"),
        col("days_since_last_order"),
        col("lifetime_value")
    )

    # Write to offline store (Parquet in Garage)
    feast_features.write \
        .mode("overwrite") \
        .parquet("s3://datalake/feast/user_features.parquet")

    # Materialize to online store (Redis)
    subprocess.run([
        "feast", "materialize-incremental",
        datetime.now().isoformat()
    ], check=True)

    return feast_features

@asset(
    ins={"feast_features": AssetIn("feast_user_features")},
    group_name="ml_training"
)
def training_dataset(feast_features):
    """Generate training dataset with point-in-time correct features."""
    from feast import FeatureStore
    import pandas as pd

    store = FeatureStore(repo_path="/feast")

    # Entity dataframe with labels and timestamps
    entity_df = pd.read_parquet("s3://datalake/ml/labels/churn_labels.parquet")

    # Get historical features (point-in-time correct)
    training_df = store.get_historical_features(
        entity_df=entity_df,
        features=[
            "user_features:total_purchases",
            "user_features:avg_order_value",
            "user_features:days_since_last_order",
            "user_features:lifetime_value"
        ]
    ).to_df()

    # Save as Iceberg table for versioning
    spark.createDataFrame(training_df) \
        .writeTo("ml.training_datasets") \
        .using("iceberg") \
        .append()

    return training_df
```

### Kubeflow Integration

**Components on Kubernetes:**

Kubeflow provides a complete ML platform running on the same Kubernetes cluster:

1. **Kubeflow Pipelines** - DAG-based training workflow orchestration
2. **JupyterHub** - Multi-user Jupyter notebook environment for data scientists
3. **KServe** - Model serving infrastructure with autoscaling
4. **Katib** - Hyperparameter tuning and neural architecture search
5. **Training Operators** - Distributed training for TensorFlow, PyTorch, XGBoost

**Namespace Architecture:**

```
ml-platform
├── kubeflow-pipelines
│   ├── ml-pipeline (API server)
│   ├── ml-pipeline-ui
│   ├── metadata-store (PostgreSQL)
│   └── minio (artifact storage - can use Garage)
├── jupyter
│   ├── jupyterhub
│   └── notebook-controller
├── training
│   ├── training-operator
│   └── pytorch-operator
└── kserve
    ├── kserve-controller
    └── inference-services
```

**Training Pipeline Example:**

```python
# kubeflow_pipeline.py
from kfp import dsl, compiler
from kfp.dsl import component, Output, Dataset, Model

@component(
    packages_to_install=["feast", "pyarrow", "pandas"],
    base_image="python:3.9"
)
def load_features(
    feature_store_path: str,
    output_dataset: Output[Dataset]
):
    """Load training features from Feast."""
    from feast import FeatureStore
    import pandas as pd

    store = FeatureStore(repo_path=feature_store_path)

    # Load entity dataframe
    entity_df = pd.read_parquet("s3://datalake/ml/labels/train_labels.parquet")

    # Fetch historical features
    training_data = store.get_historical_features(
        entity_df=entity_df,
        features=["user_features:*"]
    ).to_df()

    # Save to output
    training_data.to_parquet(output_dataset.path)

@component(
    packages_to_install=["scikit-learn", "pandas", "pyarrow"],
    base_image="python:3.9"
)
def train_model(
    training_dataset: Dataset,
    n_estimators: int,
    max_depth: int,
    output_model: Output[Model]
):
    """Train RandomForest model."""
    import pandas as pd
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    # Load data
    df = pd.read_parquet(training_dataset.path)
    X = df.drop("label", axis=1)
    y = df["label"]

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluate
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)

    print(f"Train accuracy: {train_score}")
    print(f"Test accuracy: {test_score}")

    # Save model
    joblib.dump(model, output_model.path)
    output_model.metadata["train_accuracy"] = float(train_score)
    output_model.metadata["test_accuracy"] = float(test_score)

@component(
    packages_to_install=["boto3"],
    base_image="python:3.9"
)
def upload_to_garage(
    model: Model,
    s3_path: str
):
    """Upload model to Garage S3."""
    import boto3

    s3 = boto3.client(
        's3',
        endpoint_url='http://garage-s3-api.garage.svc.cluster.local:3900',
        aws_access_key_id='ACCESS_KEY',
        aws_secret_access_key='SECRET_KEY'
    )

    with open(model.path, 'rb') as f:
        s3.upload_fileobj(f, 'datalake', s3_path)

    print(f"Model uploaded to s3://datalake/{s3_path}")

@dsl.pipeline(name='user-churn-training')
def training_pipeline(
    feature_store_path: str = "/feast",
    n_estimators: int = 100,
    max_depth: int = 10
):
    """Complete training pipeline."""
    # Load features from Feast
    load_task = load_features(feature_store_path=feature_store_path)

    # Train model
    train_task = train_model(
        training_dataset=load_task.outputs["output_dataset"],
        n_estimators=n_estimators,
        max_depth=max_depth
    )

    # Upload to Garage
    upload_to_garage(
        model=train_task.outputs["output_model"],
        s3_path="ml/models/churn_model_v1.pkl"
    )

# Compile pipeline
compiler.Compiler().compile(training_pipeline, 'pipeline.yaml')
```

**Integration with Lakehouse:**
- Read training data from Iceberg tables (versioned snapshots)
- Store models in Garage S3 with metadata
- Track experiments with MLflow (logs stored in Garage)
- Deploy models via KServe for low-latency serving

### DVC (Data Version Control) Integration

**Purpose:**

DVC provides git-like versioning for ML datasets and models, using Garage S3 as the remote storage backend.

**Benefits:**
- Version control for large datasets without storing in git
- Track model artifacts with metadata
- Ensure experiment reproducibility
- Lightweight alternative to Kubeflow for simple workflows

**Configuration:**

```yaml
# .dvc/config
[core]
    remote = garage

[remote "garage"]
    url = s3://datalake/dvc
    endpointurl = http://garage-s3-api.garage.svc.cluster.local:3900
    access_key_id = ${S3_ACCESS_KEY}
    secret_access_key = ${S3_SECRET_KEY}
    region = garage
```

**Workflow Example:**

```bash
# Initialize DVC in your ML project
dvc init

# Track training dataset
dvc add data/training_set.parquet
git add data/training_set.parquet.dvc .gitignore
git commit -m "Add training dataset v1"

# Push data to Garage
dvc push

# Track trained model
dvc add models/rf_classifier.pkl
git add models/rf_classifier.pkl.dvc
git commit -m "Add trained model v1"
dvc push

# Create a tag for this experiment
git tag -a "exp-v1.0" -m "Baseline RandomForest model"
git push --tags

# Later, reproduce experiment from any commit
git checkout exp-v1.0
dvc pull  # Downloads exact dataset and model from Garage
python evaluate.py  # Reproduce results
```

**DVC Pipeline (Alternative to Kubeflow):**

```yaml
# dvc.yaml - Define ML pipeline
stages:
  prepare_features:
    cmd: python scripts/prepare_features.py
    deps:
      - scripts/prepare_features.py
      - data/raw/
    params:
      - prepare.feature_window_days
    outs:
      - data/features.parquet

  train:
    cmd: python scripts/train.py
    deps:
      - scripts/train.py
      - data/features.parquet
    params:
      - train.learning_rate
      - train.n_estimators
      - train.max_depth
    outs:
      - models/model.pkl
    metrics:
      - metrics/train_metrics.json:
          cache: false

  evaluate:
    cmd: python scripts/evaluate.py
    deps:
      - scripts/evaluate.py
      - models/model.pkl
      - data/test.parquet
    metrics:
      - metrics/eval_metrics.json:
          cache: false
    plots:
      - plots/confusion_matrix.png
      - plots/roc_curve.png
```

**Run DVC Pipeline:**

```bash
# Run entire pipeline
dvc repro

# View metrics across experiments
dvc metrics show

# Compare experiments
dvc metrics diff exp-v1.0 exp-v2.0

# Visualize plots
dvc plots show
```

### Model Training Data Versioning with Iceberg

Iceberg snapshots provide built-in data versioning for reproducible training:

```python
# Train model on specific data snapshot
training_data = spark.read.format("iceberg") \
    .option("snapshot-id", "1234567890") \
    .load("ml.training_data")

model = train_model(training_data)

# Store model artifact with snapshot metadata
model_metadata = {
    "snapshot_id": "1234567890",
    "training_date": "2024-01-15",
    "features": ["total_purchases", "avg_order_value"],
    "iceberg_table": "ml.training_data"
}

# Save to Garage with metadata
import joblib
import json

joblib.dump(model, "s3://datalake/ml/models/model_v1.pkl")
with open("s3://datalake/ml/models/model_v1_metadata.json", "w") as f:
    json.dump(model_metadata, f)
```

**Query Historical Training Data:**

```python
# Reproduce training from specific timestamp
training_data = spark.read.format("iceberg") \
    .option("as-of-timestamp", "2024-01-15 00:00:00") \
    .load("ml.training_data")

# Or use specific snapshot
training_data = spark.read.format("iceberg") \
    .option("snapshot-id", "1234567890") \
    .load("ml.training_data")
```

### Complete ML Pipeline Flow

```
1. Feature Engineering (Dagster + DBT)
   │
   ├─▶ Transform raw data (Bronze → Silver → Gold)
   ├─▶ Compute features (aggregations, transformations)
   └─▶ Write to Iceberg Gold layer
       │
       ▼
2. Feature Store (Feast)
   │
   ├─▶ Materialize to offline store (Iceberg/Parquet in Garage)
   ├─▶ Materialize to online store (Redis) for serving
   └─▶ Feature registry updated with schemas
       │
       ▼
3. Training (Kubeflow Pipelines or DVC)
   │
   ├─▶ Fetch historical features from Feast (point-in-time correct)
   ├─▶ Train model on Kubernetes (GPU optional)
   ├─▶ Log metrics and artifacts to MLflow
   └─▶ Save model to Garage S3
       │
       ▼
4. Version Control (DVC)
   │
   ├─▶ Track dataset versions (via DVC)
   ├─▶ Track model versions (via DVC)
   ├─▶ Store metadata (Iceberg snapshot IDs, metrics)
   └─▶ Commit to git for reproducibility
       │
       ▼
5. Model Serving (KServe)
   │
   ├─▶ Load model from Garage S3
   ├─▶ Fetch online features from Feast/Redis (<10ms)
   ├─▶ Serve predictions via REST/gRPC API
   └─▶ Monitor model performance and drift
```

### Kubernetes Deployment Considerations

**Namespace Organization:**

```
lakehouse               # Core data platform
├── garage              # S3 storage
├── airbyte             # Data ingestion
├── dagster             # Orchestration
├── trino               # Query engine
└── superset            # BI/Analytics

ml-platform             # ML workloads
├── feast
│   ├── feast-jobservice
│   └── redis-feast (online store)
├── kubeflow
│   ├── kubeflow-pipelines
│   ├── jupyterhub
│   ├── training-operator
│   └── kserve-controller
└── mlflow              # Experiment tracking
```

**Resource Requirements:**

| Component | CPU | Memory | Storage | Notes |
|-----------|-----|--------|---------|-------|
| Feast Job Service | 500m | 1Gi | - | Batch jobs |
| Redis (Online Store) | 1 | 4Gi | 10Gi | In-memory cache |
| Kubeflow Pipelines | 2 | 4Gi | 20Gi | API + UI + metadata |
| JupyterHub | 1 | 2Gi | - | Notebook spawner |
| Training Jobs | Variable | Variable | - | GPU support optional |
| KServe Models | 500m-2 | 1-4Gi | - | Per model instance |

**Storage Architecture:**

```
Garage S3 (s3://datalake/)
├── feast/
│   ├── registry.db                    # Feature registry
│   ├── offline/                       # Parquet files
│   │   └── user_features.parquet
│   └── backfills/                     # Historical materializations
├── ml/
│   ├── datasets/                      # Training/test datasets
│   │   └── train_v1.parquet
│   ├── models/                        # Model artifacts
│   │   ├── churn_model_v1.pkl
│   │   └── churn_model_v1_metadata.json
│   ├── experiments/                   # MLflow artifacts
│   └── labels/                        # Ground truth labels
└── dvc/                               # DVC remote storage
    └── cache/                         # DVC cached files
```

## Lakehouse Governance: Unifying Data Lake and Data Warehouse

This section explains how governance transforms a data lake into a true lakehouse by providing warehouse-like capabilities.

### The Lakehouse Concept

A **lakehouse** combines the best aspects of data lakes and data warehouses:

| Aspect | Data Lake | Data Warehouse | Lakehouse |
|--------|-----------|----------------|-----------|
| Storage Format | Files (Parquet, CSV) | Proprietary tables | Open formats (Iceberg) |
| ACID Transactions | ❌ No | ✅ Yes | ✅ Yes (via Iceberg) |
| Schema Evolution | Limited | Complex migrations | ✅ Non-breaking changes |
| Query Performance | Slow (full scans) | Fast (optimized) | ✅ Fast (metadata pruning) |
| Data Governance | Manual/External | Built-in | ✅ Catalog-based |
| Time Travel | ❌ No | Limited | ✅ Yes (Iceberg snapshots) |
| Cost | Low | High | Low (object storage) |
| Open Ecosystem | ✅ Yes | ❌ No | ✅ Yes |

**The Key Insight:** A lakehouse is NOT just storage + catalog. It's **governed unified access** to data through a centralized catalog layer that provides:

1. **Unified metadata** across all tools (Trino, Spark, Dagster, ML frameworks)
2. **Access control** at table/column/row level
3. **Data lineage** from source → consumption
4. **Schema management** with versioning
5. **Audit trails** for compliance

### How Governance Unifies Lake + Warehouse

**Without Governance (Traditional Data Lake):**

```
┌────────────────────────────────────────────────┐
│           S3 / Garage (Raw Files)              │
│  - users/2024/01/data.parquet                  │
│  - orders/2024/01/data.parquet                 │
│  - No schema enforcement                       │
│  - No access control                           │
│  - Manual metadata tracking                    │
└────────────────────────────────────────────────┘
          │           │            │
          ▼           ▼            ▼
    Trino Query   Spark Job   ML Training
    (different    (different  (different
     schemas)      schemas)    schemas)

Problems:
- Schema drift across consumers
- No centralized access control
- Manual data discovery
- No audit trail
- Performance issues (full table scans)
```

**With Governance (Lakehouse Architecture):**

```
┌────────────────────────────────────────────────┐
│         Apache Polaris Catalog                 │
│      (Unified Governance Layer)                │
│                                                │
│  - Single source of truth for schemas          │
│  - RBAC: who can access what                   │
│  - Audit logs: who accessed when               │
│  - Lineage: data flow tracking                 │
│  - Metadata: statistics, partitions            │
└────────────────┬───────────────────────────────┘
                 │ Iceberg REST API
                 │
┌────────────────┴───────────────────────────────┐
│         Apache Iceberg (Table Format)          │
│  - ACID transactions                           │
│  - Schema evolution                            │
│  - Time travel                                 │
│  - Hidden partitioning                         │
└────────────────┬───────────────────────────────┘
                 │
┌────────────────┴───────────────────────────────┐
│           S3 / Garage (Parquet Files)          │
│  - Immutable data files                        │
│  - Columnar format                             │
│  - Compressed and efficient                    │
└────────────────┬───────────────────────────────┘
                 │
        ┌────────┴───────┬────────────┐
        ▼                ▼            ▼
   Trino Query      Spark Job    ML Training
   (same schema)    (same schema) (same schema)

Benefits:
✅ Consistent schemas across all consumers
✅ Centralized access control via catalog
✅ Automatic metadata and statistics
✅ Complete audit trail
✅ Optimized query performance
```

### Governance Stack (Phase 3)

**Layer 1: Storage (Garage/S3)**
- Object storage for data files
- Encryption at rest
- Bucket policies

**Layer 2: Table Format (Apache Iceberg)**
- ACID transactions
- Schema versioning
- Snapshot management
- Metadata optimization

**Layer 3: Catalog (Apache Polaris)**
- **Unified schema registry** - Single source of truth
- **RBAC** - Role-based access control
- **Authentication** - Integration with identity providers
- **Authorization** - Table/column/row-level security
- **Audit logging** - Track all data access
- **Lineage** - Data provenance tracking

**Layer 4: Compute Engines**
- Trino (SQL queries)
- Spark (batch processing)
- Dagster (orchestration)
- Kubeflow (ML training)
- All use Polaris catalog via Iceberg REST API

### Apache Polaris: The Governance Engine

**Why Polaris for Governance?**

Apache Polaris is an open-source Iceberg catalog with built-in governance capabilities:

```yaml
# Polaris Configuration
catalog:
  type: rest
  uri: http://polaris-catalog:8181/api/catalog
  warehouse: s3://datalake/
  s3:
    endpoint: http://garage-s3-api:3900

# RBAC Configuration
principals:
  - name: data_engineer
    type: user
    grants:
      - catalog: lakehouse
        namespace: raw.*
        permissions: [CREATE, READ, WRITE]
      - catalog: lakehouse
        namespace: processed.*
        permissions: [CREATE, READ, WRITE]

  - name: data_analyst
    type: user
    grants:
      - catalog: lakehouse
        namespace: analytics.*
        permissions: [READ]  # Read-only access to gold layer

  - name: ml_engineer
    type: user
    grants:
      - catalog: lakehouse
        namespace: ml.*
        permissions: [CREATE, READ, WRITE]
      - catalog: lakehouse
        namespace: processed.*
        permissions: [READ]
```

**Access Control Example:**

```python
# Data Engineer - Can create and modify tables
spark.sql("""
    CREATE TABLE processed.users (
        user_id STRING,
        email STRING,
        created_at TIMESTAMP
    ) USING iceberg
""")  # ✅ Allowed

# Data Analyst - Read-only on gold layer
df = spark.read.table("analytics.user_metrics")  # ✅ Allowed

df.write.mode("overwrite").saveAsTable("analytics.user_metrics")  # ❌ Denied
# Error: Principal 'data_analyst' does not have WRITE permission

# ML Engineer - Access to ML namespace and read from processed
features = spark.read.table("processed.user_features")  # ✅ Allowed
features.write.saveAsTable("ml.training_data")  # ✅ Allowed
```

### Data Lineage in the Lakehouse

Governance enables end-to-end lineage tracking:

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Lineage Flow                         │
└──────────────────────────────────────────────────────────────┘

1. Ingestion (Airbyte)
   Source: postgres.public.users
   │
   ├─▶ Created: raw.ecommerce.users (Iceberg snapshot #1)
   │   Timestamp: 2024-01-15 08:00:00
   │   Rows: 10,000
   │   User: airbyte-service-account
   │
   ▼

2. Transformation (DBT → Dagster)
   DBT Model: stg_users.sql
   │
   ├─▶ Read: raw.ecommerce.users (snapshot #1)
   ├─▶ Created: processed.ecommerce.users (snapshot #42)
   │   Timestamp: 2024-01-15 09:00:00
   │   Rows: 9,850 (150 filtered)
   │   User: dagster-service-account
   │   Lineage: Derived from raw.ecommerce.users#1
   │
   ▼

3. Aggregation (DBT → Dagster)
   DBT Model: fct_user_metrics.sql
   │
   ├─▶ Read: processed.ecommerce.users (snapshot #42)
   ├─▶ Read: processed.ecommerce.orders (snapshot #89)
   ├─▶ Created: analytics.user_metrics (snapshot #15)
   │   Timestamp: 2024-01-15 10:00:00
   │   Rows: 9,850
   │   User: dagster-service-account
   │   Lineage: Joined from processed.ecommerce.users#42 + orders#89
   │
   ▼

4. Feature Engineering (Dagster → Feast)
   Asset: feast_user_features
   │
   ├─▶ Read: analytics.user_metrics (snapshot #15)
   ├─▶ Created: ml.features.user_features (Feast offline store)
   │   Timestamp: 2024-01-15 11:00:00
   │   Features: 12
   │   User: dagster-service-account
   │
   ▼

5. Model Training (Kubeflow)
   Pipeline: churn-prediction-v1
   │
   ├─▶ Read: ml.features.user_features (Feast)
   ├─▶ Created: ml.models.churn_v1.pkl
   │   Timestamp: 2024-01-15 12:00:00
   │   Accuracy: 0.87
   │   User: ml-engineer@company.com
   │   Training Snapshot: ml.training_datasets#5
   │
   ▼

6. Model Serving (KServe)
   Inference Service: churn-predictor
   │
   ├─▶ Load: ml.models.churn_v1.pkl
   ├─▶ Features from: Feast online store (Redis)
   │   Predictions/sec: 1,200
   │   Latency p99: 8ms
```

**Query Lineage via Polaris:**

```sql
-- View table lineage
SELECT
    table_name,
    snapshot_id,
    parent_snapshot_id,
    operation,
    summary
FROM lakehouse.processed.users.history
ORDER BY committed_at DESC;

-- Audit access logs
SELECT
    principal,
    action,
    resource,
    timestamp,
    success
FROM polaris.audit_logs
WHERE resource LIKE 'analytics.%'
  AND timestamp > NOW() - INTERVAL '7 days';
```

### Row-Level Security (Future)

**Scenario:** Different teams need different data visibility

```python
# Define row-level policies in Polaris/Trino
CREATE ROW ACCESS POLICY region_policy ON analytics.sales
AS (
    CASE
        WHEN CURRENT_USER = 'us_analyst' THEN region = 'US'
        WHEN CURRENT_USER = 'eu_analyst' THEN region = 'EU'
        WHEN CURRENT_USER = 'global_manager' THEN true
        ELSE false
    END
);

# Queries automatically filtered
# us_analyst runs:
SELECT * FROM analytics.sales;
# → Only sees US rows

# eu_analyst runs:
SELECT * FROM analytics.sales;
# → Only sees EU rows

# global_manager runs:
SELECT * FROM analytics.sales;
# → Sees all rows
```

### Column-Level Security (Future)

**Scenario:** Mask PII for non-privileged users

```sql
-- Create column mask in Trino
CREATE COLUMN MASK email_mask ON analytics.users (email)
AS (
    CASE
        WHEN CURRENT_USER IN ('admin', 'data_engineer')
        THEN email  -- Show full email
        ELSE CONCAT(SUBSTRING(email, 1, 3), '***@', SPLIT_PART(email, '@', 2))
    END
);

-- data_analyst sees:
SELECT email FROM analytics.users LIMIT 3;
-- Results: joh***@example.com, sar***@test.com

-- data_engineer sees:
SELECT email FROM analytics.users LIMIT 3;
-- Results: john@example.com, sarah@test.com
```

### Governance Best Practices

**1. Principle of Least Privilege**
- Grant minimum permissions needed
- Use role-based access, not user-based
- Regular access audits

**2. Data Classification**
- Tag tables with sensitivity levels (PUBLIC, INTERNAL, CONFIDENTIAL, PII)
- Automate PII detection
- Apply policies based on tags

**3. Audit Everything**
- Log all data access
- Track schema changes
- Monitor query patterns
- Alert on anomalies

**4. Lineage as Documentation**
- Automatically track data flow
- Document transformations in code
- Version control pipelines
- Maintain data dictionaries

**5. Test Data Quality**
- Validate at every layer (Bronze/Silver/Gold)
- Automated tests in DBT
- Data quality sensors in Dagster
- Block bad data early

### Migration Path: Adding Governance to Existing Lake

**Phase 1 (Current):** Raw data lake
- Files in S3/Garage
- Manual schema tracking
- No access control

**Phase 2:** Add table format
- Deploy Iceberg
- Migrate to Iceberg tables
- Schema versioning enabled

**Phase 3:** Add catalog governance
- Deploy Apache Polaris
- Configure RBAC
- Enable audit logging
- Migrate tools to use catalog

**Phase 4:** Advanced governance
- Row-level security
- Column masking
- Automated PII detection
- Compliance reporting

### Benefits of Unified Governance

**For Data Engineers:**
- ✅ Single place to manage schemas
- ✅ Automated lineage tracking
- ✅ Schema evolution without breaking changes
- ✅ Performance optimization via metadata

**For Data Analysts:**
- ✅ Self-service data discovery
- ✅ Consistent data across tools
- ✅ Trusted, governed data
- ✅ Fast queries (metadata pruning)

**For ML Engineers:**
- ✅ Reproducible training data (snapshots)
- ✅ Feature versioning
- ✅ Integration with feature stores
- ✅ Lineage from raw data → model

**For Compliance/Security:**
- ✅ Complete audit trail
- ✅ Fine-grained access control
- ✅ PII protection
- ✅ Data retention policies

**For the Business:**
- ✅ Lower infrastructure costs (object storage)
- ✅ Faster time to insights
- ✅ Data quality and trust
- ✅ Regulatory compliance

## Configuration Details

### Garage S3 Configuration

**Create Bucket:**
```bash
POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# Create bucket
kubectl exec -n garage $POD -- garage bucket create lakehouse

# Generate access key
kubectl exec -n garage $POD -- garage key new --name lakehouse-access

# Link key to bucket
kubectl exec -n garage $POD -- garage bucket allow \
  --read --write lakehouse \
  --key lakehouse-access
```

**S3 Endpoint Configuration:**
```
Endpoint: http://garage-s3-api:3900 (internal)
          http://localhost:3900 (port-forward)
Region: garage
Path Style: true
```

### DBT Project Structure

```
dbt/
├── dbt_project.yml
├── profiles.yml
├── models/
│   ├── staging/           # Bronze → Silver
│   │   ├── stg_users.sql
│   │   └── stg_events.sql
│   ├── intermediate/      # Business logic
│   │   └── int_user_sessions.sql
│   └── marts/             # Silver → Gold
│       ├── dim_users.sql
│       └── fct_events.sql
├── tests/
├── macros/
└── analyses/
```

**Example Model (Iceberg + DBT):**

```sql
-- models/staging/stg_users.sql
{{ config(
    materialized='incremental',
    file_format='iceberg',
    unique_key='user_id',
    incremental_strategy='merge'
) }}

SELECT
    user_id,
    email,
    created_at,
    updated_at
FROM {{ source('raw', 'users') }}

{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

## Performance Optimization

### Iceberg Table Maintenance

**Compact Small Files:**
```sql
-- Rewrite small files into larger files
CALL iceberg.system.rewrite_data_files(
  table => 'processed.events',
  strategy => 'binpack'
);
```

**Expire Old Snapshots:**
```sql
-- Remove snapshots older than 7 days
CALL iceberg.system.expire_snapshots(
  table => 'processed.events',
  older_than => TIMESTAMP '2024-01-01 00:00:00',
  retain_last => 5
);
```

**Remove Orphan Files:**
```sql
-- Delete files not referenced by any snapshot
CALL iceberg.system.remove_orphan_files(
  table => 'processed.events',
  older_than => TIMESTAMP '2024-01-01 00:00:00'
);
```

### Trino Optimization

**Query Patterns:**
- Use partition filters in WHERE clauses
- Select only required columns
- Leverage Iceberg statistics for joins
- Use appropriate data types

**Resource Configuration:**
```properties
# coordinator config
query.max-memory=50GB
query.max-memory-per-node=10GB

# worker config
task.concurrency=16
task.max-worker-threads=64
```

## Security

### Current (Development)

- Default credentials for local development
- No network policies
- No TLS/encryption

### Production (Phase 3)

**Authentication & Authorization:**
- Kubernetes RBAC for service access
- S3 IAM-style policies for Garage buckets
- Trino LDAP/OAuth integration
- Row-level security in Iceberg

**Network Security:**
- Network policies for pod-to-pod communication
- Traefik TLS termination
- Internal service mesh (Istio/Linkerd)

**Data Security:**
- Encryption at rest (Garage)
- Encryption in transit (TLS)
- Column-level encryption (future)
- Audit logging

**Secrets Management:**
- Kubernetes secrets (current)
- External secret management (Vault, AWS Secrets Manager)
- Key rotation policies

## Best Practices

### Data Organization

**Medallion Architecture:**
- **Bronze (raw/)**: Raw ingested data, minimal processing
- **Silver (processed/)**: Cleaned, deduplicated, validated
- **Gold (analytics/)**: Business-level aggregates, denormalized

**Naming Conventions:**
```
<environment>.<layer>.<domain>.<entity>

Examples:
- dev.raw.ecommerce.orders
- prod.processed.finance.transactions
- prod.analytics.marketing.campaign_metrics
```

### Data Quality

**DBT Tests:**
```yaml
models:
  - name: stg_users
    columns:
      - name: user_id
        tests:
          - unique
          - not_null
      - name: email
        tests:
          - unique
          - not_null
```

**Dagster Asset Checks:**
```python
@asset_check(asset=user_metrics)
def validate_user_metrics():
    assert metrics.count() > 0, "No metrics generated"
    assert metrics.filter("metric_value < 0").count() == 0
```

### Monitoring

**Key Metrics:**
- Pipeline success rate
- Data freshness (lag between source and lakehouse)
- Query performance (p95, p99 latency)
- Storage usage and growth
- Resource utilization (CPU, memory)

**Alerting:**
- Pipeline failures
- Data quality violations
- Resource exhaustion
- Unusual query patterns

## Further Reading

- [Iceberg Table Spec](https://iceberg.apache.org/spec/)
- [DBT Best Practices](https://docs.getdbt.com/guides/best-practices)
- [Dagster Asset Definitions](https://docs.dagster.io/concepts/assets/software-defined-assets)
- [Trino Query Optimization](https://trino.io/docs/current/optimizer.html)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)

# MLOps Implementation Plan (COMPLETED)

## Overview

This plan has been fully implemented, adding MLOps infrastructure to the payment pipeline platform. The mock inference service has been replaced with a production-grade ML lifecycle leveraging **Feast** for feature management and **MLflow** for model governance.

---

## Implementation Status (Current)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Foundation (MLflow, Feast, Redis) | ✅ Complete |
| Phase 2 | Model Training (Dagster, Scikit-learn) | ✅ Complete |
| Phase 3 | Model Serving (FastAPI integration) | ✅ Complete |
| Phase 4 | Monitoring & Operations (Data Quality) | ✅ Complete |

---

## Current State

**Existing Mock Inference Service:**
- 4 endpoints: `/fraud/score`, `/retry/strategy`, `/churn/predict`, `/recovery/recommend`
- Deterministic rule-based implementations
- Well-defined input/output schemas

**Available Data:**
- `payment_events` table with enrichment fields (fraud_score, churn_score, retry_strategy)
- Customer, merchant, and payment history aggregations via DBT marts
- Real-time payment events via Kafka (`payments.normalized`)

## Proposed Architecture

```
                          +------------------+
                          |   MLflow         |
                          |   Tracking       |
                          |   Server         |
                          +--------+---------+
                                   |
          +------------------------+------------------------+
          |                        |                        |
          v                        v                        v
   +-------------+          +-------------+          +-------------+
   |   Fraud     |          |   Churn     |          |   Retry     |
   |   Model     |          |   Model     |          |   Model     |
   |   Training  |          |   Training  |          |   Training  |
   +------+------+          +------+------+          +------+------+
          |                        |                        |
          +------------------------+------------------------+
                                   |
                          +--------v---------+
                          |   MLflow Model   |
                          |   Registry       |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |   Feast Feature  |
                          |   Store          |
                          +--------+---------+
                                   |
          +------------------------+------------------------+
          |                                                 |
          v                                                 v
   +-------------+                                   +-------------+
   |   Online    |<------ Real-time Features ------>|   Offline   |
   |   Store     |                                   |   Store     |
   |   (Redis)   |                                   |   (MinIO)   |
   +------+------+                                   +------+------+
          |                                                 |
          v                                                 |
   +-------------+                                          |
   |   Model     |<----- Training Data ---------------------+
   |   Serving   |
   |   (FastAPI) |
   +-------------+
          |
          v
   Temporal Workflows (existing)
```

## Service Components

### 1. Feast Feature Store

**Purpose:** Consistent feature computation for training and serving

**Services:**
- `feast-server` - Feast feature server for online serving
- `feast-redis` - Redis backend for online store

**Features to Define:**
```python
# Customer features (from int_payment_customer_metrics)
- customer_total_payments_30d
- customer_failure_rate_30d
- customer_avg_amount_cents
- customer_days_since_first_payment
- customer_payment_method_count

# Merchant features (from int_payment_merchant_metrics)
- merchant_total_volume_30d
- merchant_failure_rate_30d
- merchant_avg_transaction_amount
- merchant_customer_count

# Transaction features (real-time)
- amount_cents
- payment_method_type
- card_brand
- is_guest_checkout
```

### 2. MLflow Tracking & Registry

**Purpose:** Experiment tracking, model versioning, artifact storage

**Services:**
- `mlflow-server` - MLflow tracking server
- `mlflow-db` - PostgreSQL for MLflow backend (or use existing postgres)

**Configuration:**
- Backend store: PostgreSQL
- Artifact store: MinIO (`s3://warehouse/mlflow-artifacts`)
- Model registry for production model deployment

### 3. Model Training Pipeline

**Purpose:** Train and retrain ML models on payment data

**Approach Options:**

**Option A: Dagster Jobs (Recommended)**
- Add model training as Dagster assets/jobs
- Leverage existing Dagster infrastructure
- Schedule retraining alongside data transformations
- Unified observability in Dagster UI

**Option B: Standalone Training Containers**
- Separate `mlops-training` service
- Triggered by schedule or Dagster sensors
- More isolated but more infrastructure

**Models to Train:**
1. **Fraud Detection** - Binary classification on transaction risk
2. **Churn Prediction** - Probability of involuntary churn
3. **Retry Optimization** - Multi-class classification for retry strategy

### 4. Model Serving

**Purpose:** Replace mock inference service with real ML models

**Approach Options:**

**Option A: Enhanced FastAPI (Recommended)**
- Extend existing inference service structure
- Load models from MLflow registry
- Fetch features from Feast online store
- Minimal infrastructure changes

**Option B: MLflow Model Serving**
- Use MLflow's built-in serving
- One container per model
- More containers but simpler code

**Option C: BentoML**
- Production-grade model serving
- Built-in batching, caching
- More complex setup

### 5. Model Monitoring (Phase 2)

**Purpose:** Track model performance and data drift

**Components:**
- Evidently AI for drift detection
- Prometheus metrics for model latency/throughput
- Grafana dashboards (or Superset)

## Directory Structure

```
kubernetes/
├── mlops/                              # NEW: MLOps platform
│   ├── feature-store/
│   │   ├── feature_repo/
│   │   │   ├── feature_store.yaml      # Feast config
│   │   │   ├── entities.py             # Customer, merchant entities
│   │   │   ├── features/
│   │   │   │   ├── customer_features.py
│   │   │   │   ├── merchant_features.py
│   │   │   │   └── transaction_features.py
│   │   │   └── feature_services.py     # Feature services for models
│   │   └── Dockerfile
│   │
│   ├── training/
│   │   ├── models/
│   │   │   ├── fraud/
│   │   │   │   ├── train.py
│   │   │   │   └── config.yaml
│   │   │   ├── churn/
│   │   │   │   ├── train.py
│   │   │   │   └── config.yaml
│   │   │   └── retry/
│   │   │       ├── train.py
│   │   │       └── config.yaml
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── serving/                        # Enhanced inference service
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── models/
│   │   │   │   ├── fraud_model.py
│   │   │   │   ├── churn_model.py
│   │   │   │   └── retry_model.py
│   │   │   └── feature_client.py       # Feast client
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   └── docker-compose.mlops.yml        # MLOps services compose file
│
└── infrastructure/docker/
    └── docker-compose.yml              # Add mlops profile
```

## Docker Compose Services

```yaml
# Profile: mlops

services:
  # Feast Feature Store
  feast-redis:
    image: redis:7
    profiles: [mlops]

  feast-server:
    build: ../../mlops/feature-store
    depends_on: [feast-redis, minio]
    profiles: [mlops]

  # MLflow
  mlflow-db:
    image: postgres:14
    profiles: [mlops]

  mlflow-server:
    image: ghcr.io/mlflow/mlflow:v2.17.0
    depends_on: [mlflow-db, minio]
    profiles: [mlops]

  # Model Serving (replaces mock inference-service)
  ml-serving:
    build: ../../mlops/serving
    depends_on: [feast-server, mlflow-server]
    profiles: [mlops]
```

## Implementation Phases

### Phase 1: Foundation (Start Here)
1. Create `mlops/` directory structure
2. Add MLflow service to docker-compose (uses existing MinIO)
3. Add Feast with Redis online store
4. Create basic feature definitions

**Deliverables:**
- MLflow UI accessible at http://localhost:5001
- Feast server with customer/merchant features
- Feature materialization job in Dagster

### Phase 2: Model Training
1. Create training pipelines for fraud, churn, retry models
2. Integrate with Dagster for orchestration
3. Log experiments and models to MLflow

**Deliverables:**
- Trained models registered in MLflow
- Dagster jobs for model retraining
- Experiment tracking with metrics/artifacts

### Phase 3: Model Serving
1. Create enhanced inference service
2. Load models from MLflow registry
3. Fetch features from Feast online store
4. Replace mock inference-service

**Deliverables:**
- Real ML predictions in payment pipeline
- A/B testing capability via model versions
- Feature consistency between training and serving

### Phase 4: Monitoring & Operations
1. Add model performance tracking
2. Implement data drift detection
3. Create alerting for model degradation
4. Add Grafana/Superset dashboards

**Deliverables:**
- Model monitoring dashboard
- Automated retraining triggers
- Production-ready MLOps lifecycle

## Environment Variables

Add to `.env`:
```bash
# MLflow
MLFLOW_DB_USER=mlflow
MLFLOW_DB_PASSWORD=mlflow
MLFLOW_DB_NAME=mlflow
MLFLOW_TRACKING_URI=http://mlflow-server:5000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000

# Feast
FEAST_REDIS_HOST=feast-redis
FEAST_REDIS_PORT=6379
FEAST_OFFLINE_STORE_PATH=s3://warehouse/feast-offline
```

## Makefile Commands

```makefile
# MLOps Commands
mlops-up:
    docker compose --profile mlops up -d

mlops-down:
    docker compose --profile mlops down

mlops-logs:
    docker compose --profile mlops logs -f

feast-apply:
    docker compose exec feast-server feast apply

mlflow-ui:
    @echo "MLflow UI: http://localhost:5001"

train-models:
    docker compose exec dagster-user-code dagster job launch -j train_all_models
```

## Integration Points

### With Existing Payment Pipeline
- Temporal workflows call `ml-serving` instead of `inference-service`
- Same API contract (endpoints, request/response schemas)
- Environment variable: `ORCHESTRATOR_INFERENCE_SERVICE_URL=http://ml-serving:8002`

### With Dagster
- Add feature materialization as Dagster asset
- Add model training jobs
- Schedule retraining after DBT transformations complete

### With DBT Marts
- Feature definitions reference DBT mart tables
- `dim_customer` -> customer features
- `dim_merchant` -> merchant features
- `fct_payments` -> transaction history features

## Trade-off Analysis

| Aspect | Option A (Dagster-centric) | Option B (Standalone) |
|--------|---------------------------|----------------------|
| Complexity | Lower | Higher |
| Observability | Unified in Dagster | Distributed |
| Scalability | Dagster workers | Independent scaling |
| Learning curve | Leverages existing | New patterns |

**Recommendation:** Start with Dagster-centric approach (Option A) for Phase 1-3, then evaluate standalone components for Phase 4 based on scale requirements.

## Success Criteria

1. **Feature Store:** Features available within 100ms for online serving
2. **Model Training:** End-to-end training pipeline completes in < 30 minutes
3. **Model Serving:** P99 latency < 50ms for predictions
4. **Model Registry:** Models versioned with full lineage
5. **Monitoring:** Alerts trigger on >10% accuracy degradation

## Next Steps

1. Create `mlops/` directory structure
2. Add MLflow and Feast services to docker-compose.yml
3. Define initial feature set based on payment_events schema
4. Create first training pipeline for fraud detection model

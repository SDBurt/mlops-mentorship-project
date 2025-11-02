# MLOps - Machine Learning Operations (Phase 4)

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established MLOps concepts and this project's planned architecture, please verify critical details against official documentation and your specific use cases.

## Overview

MLOps (Machine Learning Operations) brings DevOps practices to machine learning: version control for models, CI/CD pipelines for training, automated deployment, monitoring in production, and reproducible experiments.

In this lakehouse platform (Phase 4, planned), MLOps extends the data pipeline with: Feast feature store for consistent features, Kubeflow for ML pipelines, DVC for data/model versioning, and integration with the existing [Medallion Architecture](medallion-architecture.md).

## Why MLOps for This Platform?

**Reproducibility**: Version control for data, features, models, and code.

**Collaboration**: Data scientists, ML engineers, and analysts work from same feature definitions.

**Production Ready**: Automated model training, testing, and deployment pipelines.

**Monitoring**: Track model performance degradation, data drift, concept drift.

**Governance**: Model lineage, experiment tracking, compliance (extends [Polaris REST Catalog](polaris-rest-catalog.md)).

## Phase 4 Components

### 1. Feast - Feature Store

**What it is**: Centralized repository for ML features with online/offline serving.

**Why Feast?**
- Define features once, use for training and inference
- Consistent feature computation (no train/serve skew)
- Time-travel for point-in-time correct features
- Low-latency online serving (<10ms)

**Architecture**:
```
[DBT Gold Tables] → [Feast Feature Repository] → Online Store (Redis)
                                                → Offline Store (MinIO S3)
```

**Example feature definition** (`features/customer_features.py`):
```python
from feast import Entity, Feature, FeatureView, ValueType
from feast.data_source import FileSource

# Entity: What features describe
customer = Entity(
    name="customer_id",
    value_type=ValueType.STRING,
    description="Customer identifier"
)

# Data source: Where features come from
customer_source = FileSource(
    path="s3://lakehouse/gold/customer_features/",
    event_timestamp_column="timestamp",
    created_timestamp_column="created"
)

# Feature view: Feature definitions
customer_features = FeatureView(
    name="customer_features",
    entities=["customer_id"],
    ttl=timedelta(days=365),  # Feature freshness
    features=[
        Feature(name="lifetime_value", dtype=ValueType.FLOAT),
        Feature(name="order_count_30d", dtype=ValueType.INT64),
        Feature(name="avg_order_value", dtype=ValueType.FLOAT),
        Feature(name="customer_segment", dtype=ValueType.STRING),
    ],
    online=True,  # Enable online serving
    source=customer_source,
)
```

**Training features** (offline, historical):
```python
from feast import FeatureStore

store = FeatureStore(repo_path="ml/feast_repo")

# Get historical features for training
training_df = store.get_historical_features(
    entity_df=customers_df,  # customer_id, timestamp
    features=[
        "customer_features:lifetime_value",
        "customer_features:order_count_30d",
        "customer_features:avg_order_value",
    ],
).to_df()

# Train model
model.fit(training_df[features], training_df[target])
```

**Inference features** (online, real-time):
```python
# Get online features for real-time prediction
features = store.get_online_features(
    entity_rows=[{"customer_id": "CUST-12345"}],
    features=[
        "customer_features:lifetime_value",
        "customer_features:order_count_30d",
    ],
).to_dict()

# Make prediction
prediction = model.predict(features)
```

**Integration with lakehouse**:
```
[DBT] creates fct_customer_features (Gold layer)
   ↓
[Feast] materializes features from Gold tables
   ↓
[Offline Store] S3/MinIO (historical features for training)
[Online Store] Redis/DynamoDB (low-latency features for inference)
```

### 2. Kubeflow - ML Platform

**What it is**: Kubernetes-native platform for ML workflows (training, tuning, deployment).

**Why Kubeflow?**
- Runs on same Kubernetes cluster as data platform
- Jupyter notebooks for exploration
- Pipelines for reproducible workflows
- Model serving with KServe
- Experiment tracking with Katib

**Components**:
- **Kubeflow Pipelines**: Define multi-step ML workflows as DAGs
- **Notebook Servers**: Jupyter environments with GPUs
- **Katib**: Hyperparameter tuning
- **KServe**: Model serving (REST/gRPC)
- **Training Operators**: Distributed training (TensorFlow, PyTorch)

**Example pipeline** (`ml/kubeflow/training_pipeline.py`):
```python
from kfp import dsl

@dsl.component
def load_data(output_path: dsl.OutputPath(str)):
    """Load features from Feast offline store"""
    from feast import FeatureStore
    store = FeatureStore(repo_path="/feast_repo")
    df = store.get_historical_features(...).to_df()
    df.to_parquet(output_path)

@dsl.component
def train_model(data_path: dsl.InputPath(str), model_path: dsl.OutputPath(str)):
    """Train ML model"""
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    df = pd.read_parquet(data_path)
    model = RandomForestClassifier()
    model.fit(df[features], df[target])
    joblib.dump(model, model_path)

@dsl.component
def evaluate_model(model_path: dsl.InputPath(str), metrics: dsl.Output[Metrics]):
    """Evaluate model performance"""
    model = joblib.load(model_path)
    accuracy = evaluate(model, test_data)
    metrics.log_metric("accuracy", accuracy)

@dsl.pipeline(name="Customer Churn Prediction")
def churn_pipeline():
    load_data_task = load_data()
    train_task = train_model(data_path=load_data_task.output)
    evaluate_task = evaluate_model(model_path=train_task.output)

# Compile and run
from kfp import compiler
compiler.Compiler().compile(churn_pipeline, 'pipeline.yaml')
```

**Model serving** with KServe:
```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: churn-predictor
  namespace: ml
spec:
  predictor:
    sklearn:
      storageUri: s3://lakehouse/models/churn/v1/
      resources:
        requests:
          cpu: "1"
          memory: "2Gi"
        limits:
          cpu: "2"
          memory: "4Gi"
```

**Invoke model**:
```bash
curl -X POST http://churn-predictor.ml.svc.cluster.local/v1/models/churn-predictor:predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [{"customer_id": "CUST-12345"}]}'
```

### 3. DVC - Data Version Control

**What it is**: Git for data and models - version control for ML artifacts.

**Why DVC?**
- Track datasets, models, metrics in Git
- Reproducible experiments
- Share models across team
- Time-travel to previous model versions

**Setup**:
```bash
cd ml/
dvc init

# Configure remote storage (MinIO S3)
dvc remote add -d minio s3://lakehouse/dvc
dvc remote modify minio endpointurl http://minio:3900
```

**Track data**:
```bash
# Add dataset to DVC
dvc add data/train.parquet

# Commit to Git
git add data/train.parquet.dvc data/.gitignore
git commit -m "Add training dataset v1"

# Push data to MinIO
dvc push
```

**Track model**:
```bash
# Train model
python train.py

# Track model with DVC
dvc add models/churn_v1.pkl

# Track metrics
cat metrics.json
# {"accuracy": 0.92, "f1": 0.89}

git add models/churn_v1.pkl.dvc metrics.json
git commit -m "Train churn model v1 - accuracy 0.92"

dvc push
```

**Reproduce experiment**:
```bash
# Clone repo
git clone <repo-url>
cd ml/

# Pull data and models
dvc pull

# Run training pipeline
dvc repro
```

**DVC pipeline** (`dvc.yaml`):
```yaml
stages:
  load_data:
    cmd: python load_data.py
    deps:
      - load_data.py
    outs:
      - data/train.parquet

  train:
    cmd: python train.py
    deps:
      - data/train.parquet
      - train.py
    outs:
      - models/churn_v1.pkl
    metrics:
      - metrics.json:
          cache: false

  evaluate:
    cmd: python evaluate.py
    deps:
      - models/churn_v1.pkl
      - data/test.parquet
    metrics:
      - eval_metrics.json:
          cache: false
```

### 4. ML Monitoring

**What to monitor**:
- **Model performance**: Accuracy, F1, AUC over time
- **Data drift**: Input feature distributions change
- **Concept drift**: Relationship between features and target changes
- **Prediction drift**: Output distributions change

**Example monitoring** with [Dagster](dagster.md):
```python
from dagster import asset, AssetMaterialization

@asset
def model_performance_metrics(context):
    """Monitor model predictions vs actual outcomes"""
    query = """
    SELECT
        DATE(prediction_timestamp) as date,
        AVG(CASE WHEN actual = prediction THEN 1 ELSE 0 END) as accuracy,
        COUNT(*) as prediction_count
    FROM ml.churn_predictions
    WHERE prediction_timestamp >= CURRENT_DATE - INTERVAL '7' DAY
    GROUP BY DATE(prediction_timestamp)
    """

    metrics = context.resources.trino.execute(query)

    # Check for performance degradation
    if metrics['accuracy'] < 0.80:
        context.log.warning(f"Model accuracy dropped to {metrics['accuracy']}")

    yield AssetMaterialization(
        asset_key="model_performance",
        metadata={
            "accuracy": metrics['accuracy'],
            "prediction_count": metrics['prediction_count']
        }
    )
```

## MLOps Workflow

```
1. Feature Engineering (DBT)
   ↓
   Gold layer: fct_customer_features

2. Feature Store (Feast)
   ↓
   Register features from Gold tables

3. Model Training (Kubeflow)
   ↓
   Load features from Feast offline store
   Train model with hyperparameter tuning (Katib)
   Evaluate model performance
   Version model with DVC

4. Model Registry
   ↓
   Store model in S3 (MinIO)
   Track metadata (accuracy, F1, training date)

5. Model Deployment (KServe)
   ↓
   Deploy model to Kubernetes
   Load features from Feast online store
   Serve predictions via REST API

6. Monitoring (Dagster + Trino)
   ↓
   Track predictions in Iceberg table
   Compare predictions vs actuals
   Alert on performance degradation
   Trigger retraining pipeline
```

## Integration with Lakehouse

### Data Flow

```
[Airbyte] → Raw data
   ↓
[DBT Bronze] → Staging
   ↓
[DBT Silver] → Clean dimensions
   ↓
[DBT Gold] → Feature tables
   ↓
[Feast] → Feature store (offline + online)
   ↓
[Kubeflow] → Model training
   ↓
[KServe] → Model serving
   ↓
[Trino] → Query predictions (stored as Iceberg table)
```

### Unified Governance (Phase 3 + Phase 4)

**[Polaris REST Catalog](polaris-rest-catalog.md)** governs both data and ML assets:
- Data tables (Bronze/Silver/Gold)
- Feature tables (Feast definitions)
- Prediction tables (model outputs)
- Model registry metadata

**Example**: RBAC for ML features
```bash
# Data scientists can read all features
polaris admin grant \
  --principal data-scientists \
  --namespace lakehouse.features \
  --privilege TABLE_READ_DATA

# Only ML engineers can deploy models
polaris admin grant \
  --principal ml-engineers \
  --namespace lakehouse.models \
  --privilege TABLE_WRITE_DATA
```

## Best Practices

### 1. Feature Store as Single Source of Truth

**Good**: Define feature in Feast, use everywhere
```python
# Training
features = feast.get_historical_features(...)

# Serving
features = feast.get_online_features(...)
```

**Bad**: Recompute features in training and serving (train/serve skew)

### 2. Version Everything

- Code (Git)
- Data (DVC)
- Models (DVC + Model Registry)
- Features (Feast + Git)
- Pipelines (Kubeflow + Git)

### 3. Automate Model Retraining

**Dagster schedule**:
```python
@schedule(cron_schedule="0 2 * * 0")  # Weekly at 2 AM Sunday
def weekly_model_retrain(context):
    return RunRequest(job=train_churn_model)
```

### 4. Monitor in Production

Track every prediction:
```sql
CREATE TABLE ml.churn_predictions (
    prediction_id UUID,
    customer_id VARCHAR,
    prediction BOOLEAN,
    confidence FLOAT,
    model_version VARCHAR,
    prediction_timestamp TIMESTAMP,
    actual BOOLEAN,  -- Backfilled later
    actual_timestamp TIMESTAMP
);
```

### 5. A/B Test Models

Deploy multiple model versions:
```yaml
# 90% traffic to v1, 10% to v2
canaryTrafficPercent: 10
```

## References

- [Feast Feature Store](https://docs.feast.dev/)
- [Kubeflow Documentation](https://www.kubeflow.org/docs/)
- [DVC Documentation](https://dvc.org/doc)
- [KServe Model Serving](https://kserve.github.io/website/)
- [MLOps Principles](https://ml-ops.org/)
- Project Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md) - Phase 4 details

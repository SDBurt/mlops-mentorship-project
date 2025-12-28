# MLflow Tracking Server

MLflow provides experiment tracking, model versioning, and model registry for the ML pipeline.

## Architecture

```
Training Jobs --> MLflow Server --> PostgreSQL (metadata)
                       |
                       v
                 MinIO (artifacts)
```

## Access

| Service | URL | Notes |
|---------|-----|-------|
| MLflow UI | http://localhost:5001 | Experiment tracking dashboard |

## Configuration

The MLflow server is configured via docker-compose with:

- **Backend Store**: PostgreSQL (`mlflow-db`) for experiment metadata
- **Artifact Store**: MinIO S3 (`s3://warehouse/mlflow-artifacts`)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MLFLOW_BACKEND_STORE_URI` | PostgreSQL connection string |
| `MLFLOW_S3_ENDPOINT_URL` | MinIO endpoint for artifacts |
| `AWS_ACCESS_KEY_ID` | MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | MinIO secret key |

## Usage from Python

```python
import mlflow

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5001")

# Start experiment
mlflow.set_experiment("fraud-detection")

with mlflow.start_run():
    mlflow.log_param("model_type", "xgboost")
    mlflow.log_metric("accuracy", 0.95)
    mlflow.sklearn.log_model(model, "model")
```

## Docker Container Usage

For training containers running in Docker:

```python
mlflow.set_tracking_uri("http://mlflow-server:5000")
```

## Files

| File | Description |
|------|-------------|
| `Dockerfile` | Extends official MLflow image with PostgreSQL and S3 drivers |

## Commands

```bash
# Start MLflow (with dependencies)
make mlops-up

# View status
make mlops-status

# Access UI info
make mlflow-ui
```

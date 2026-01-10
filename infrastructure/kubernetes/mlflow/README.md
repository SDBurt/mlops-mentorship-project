# MLflow Tracking Server

MLflow for experiment tracking and model registry. Uses PostgreSQL for metadata and MinIO for artifact storage.

## Deployment Options

### Option 1: Custom Deployment (Recommended for simplicity)

```bash
# Create secrets first
cp secrets.yaml.example secrets.yaml
kubectl apply -f secrets.yaml -n lakehouse

# Deploy MLflow
kubectl apply -f deployment.yaml -n lakehouse

# Wait for ready
kubectl wait --for=condition=ready pod -l app=mlflow -n lakehouse --timeout=300s
```

### Option 2: Helm Chart

```bash
# Add community charts repo
helm repo add community-charts https://community-charts.github.io/helm-charts
helm repo update

# Create secrets
cp secrets.yaml.example secrets.yaml
kubectl apply -f secrets.yaml -n lakehouse

# Install MLflow
helm install mlflow community-charts/mlflow -n lakehouse -f values.yaml
```

## Service Access

### Internal (Kubernetes)

```
http://mlflow.lakehouse.svc.cluster.local:5000
```

Or within lakehouse namespace:
```
http://mlflow:5000
```

### External (Port-Forward)

```bash
kubectl port-forward svc/mlflow 5000:5000 -n lakehouse
```

Then open: http://localhost:5000

## Usage

### Log Experiments

```python
import mlflow

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud-detection")

with mlflow.start_run():
    mlflow.log_param("learning_rate", 0.01)
    mlflow.log_metric("accuracy", 0.95)
    mlflow.sklearn.log_model(model, "model")
```

### Register Models

```python
# Register model in registry
mlflow.register_model(
    "runs:/<run-id>/model",
    "fraud-detection-model"
)

# Transition to production
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name="fraud-detection-model",
    version=1,
    stage="Production"
)
```

### Load Models (Inference Service)

```python
# Load production model
model = mlflow.pyfunc.load_model("models:/fraud-detection-model/Production")
predictions = model.predict(data)
```

## Environment Variables for Services

```yaml
env:
  MLFLOW_TRACKING_URI: "http://mlflow:5000"
  # For artifact access
  MLFLOW_S3_ENDPOINT_URL: "http://minio:9000"
  AWS_ACCESS_KEY_ID:
    valueFrom:
      secretKeyRef:
        name: mlflow-s3-secret
        key: access-key
  AWS_SECRET_ACCESS_KEY:
    valueFrom:
      secretKeyRef:
        name: mlflow-s3-secret
        key: secret-key
```

## Artifact Storage

Artifacts are stored in MinIO:
- Bucket: `warehouse`
- Path: `mlflow-artifacts/`

Ensure MinIO is deployed and the bucket exists before using MLflow.

## Verification

```bash
# Check pods
kubectl get pods -n lakehouse -l app=mlflow

# Check logs
kubectl logs -n lakehouse -l app=mlflow

# Test API (with port-forward)
curl http://localhost:5000/health
curl http://localhost:5000/api/2.0/mlflow/experiments/list
```

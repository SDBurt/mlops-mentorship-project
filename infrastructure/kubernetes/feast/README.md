# Feast Feature Store

Feast feature server for online feature serving. Uses Redis for online store and PostgreSQL for registry.

## Components

- **Feast Server**: HTTP feature server (port 6566)
- **Redis**: Online feature store (low-latency lookups)
- **PostgreSQL**: Feature registry (metadata)

## Deployment

```bash
# Create secrets first
cp secrets.yaml.example secrets.yaml
kubectl apply -f secrets.yaml -n lakehouse

# Deploy Redis (online store)
helm install feast-redis bitnami/redis -n lakehouse -f redis-values.yaml

# Wait for Redis
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n lakehouse --timeout=300s

# Deploy Feast server + PostgreSQL registry
kubectl apply -f deployment.yaml -n lakehouse

# Wait for ready
kubectl wait --for=condition=ready pod -l app=feast-server -n lakehouse --timeout=300s
```

## Service Access

### Feast Server

Internal:
```
http://feast-server.lakehouse.svc.cluster.local:6566
```

Or within lakehouse namespace:
```
http://feast-server:6566
```

### Redis

Internal:
```
feast-redis-master.lakehouse.svc.cluster.local:6379
```

Or within namespace:
```
feast-redis-master:6379
```

## Feature Definitions

Apply feature definitions from the feast service:

```bash
# Port-forward to Feast server
kubectl port-forward svc/feast-server 6566:6566 -n lakehouse

# From services/feast directory
cd services/feast
feast apply
```

## Usage in Inference Service

```python
from feast import FeatureStore

# Connect to Feast
fs = FeatureStore(repo_path="/feature_repo")

# Get online features
features = fs.get_online_features(
    features=[
        "customer_features:total_transactions",
        "customer_features:avg_transaction_amount",
        "merchant_features:fraud_rate",
    ],
    entity_rows=[
        {"customer_id": "cust_123", "merchant_id": "merch_456"}
    ]
).to_dict()
```

## Environment Variables for Services

```yaml
env:
  FEAST_REPO_PATH: "/feature_repo"
  FEAST_REDIS_HOST: "feast-redis-master"
  FEAST_REDIS_PORT: "6379"
  FEAST_REDIS_PASSWORD:
    valueFrom:
      secretKeyRef:
        name: feast-redis-secret
        key: password
```

## Verification

```bash
# Check pods
kubectl get pods -n lakehouse -l app=feast-server
kubectl get pods -n lakehouse -l app.kubernetes.io/name=redis

# Check Feast health
kubectl port-forward svc/feast-server 6566:6566 -n lakehouse
curl http://localhost:6566/health

# Test Redis connection
kubectl exec -it feast-redis-master-0 -n lakehouse -- redis-cli -a <password> ping
```

## Feature Materialization

To materialize features from offline to online store:

```bash
# From services/feast directory
feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")
```

Or schedule materialization in Dagster.

## Architecture Notes

- **Online Store (Redis)**: Sub-millisecond feature lookups
- **Registry (PostgreSQL)**: Feature definitions and metadata
- **Offline Store**: Uses Parquet files in MinIO (configured separately)
- **2 Replicas**: For high availability of feature server

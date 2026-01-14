# Temporal Server

Temporal workflow orchestration server for durable payment processing workflows.

## Deployment

```bash
# Add Temporal Helm repo
helm repo add temporalio https://charts.temporal.io
helm repo update

# Create secrets first
cp secrets.yaml.example secrets.yaml
# Edit secrets.yaml with your password
kubectl apply -f secrets.yaml -n lakehouse

# Install Temporal
helm install temporal temporalio/temporal -n lakehouse -f values.yaml

# Wait for ready (this takes a few minutes)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=temporal -n lakehouse --timeout=600s
```

## Service Access

### gRPC Frontend (for workers)

Internal:
```
temporal-frontend.lakehouse.svc.cluster.local:7233
```

Or within lakehouse namespace:
```
temporal-frontend:7233
```

### Web UI

```bash
kubectl port-forward svc/temporal-web 8088:8080 -n lakehouse
```

Then open: http://localhost:8088

## Payment Pipeline Integration

The Temporal Worker connects to this server:

```yaml
env:
  TEMPORAL_WORKER_TEMPORAL_HOST: temporal-frontend
  TEMPORAL_WORKER_TEMPORAL_PORT: "7233"
  TEMPORAL_WORKER_TEMPORAL_NAMESPACE: default
  TEMPORAL_WORKER_TEMPORAL_TASK_QUEUE: payment-processing
```

## Namespaces

Create the payment-processing namespace (if not using default):

```bash
kubectl exec -n lakehouse temporal-admintools-0 -- \
  temporal operator namespace create payment-processing
```

## Verification

```bash
# Check pods
kubectl get pods -n lakehouse -l app.kubernetes.io/name=temporal

# Check services
kubectl get svc -n lakehouse | grep temporal

# Test connection (from admintools)
kubectl exec -n lakehouse temporal-admintools-0 -- \
  temporal workflow list --namespace default
```

## Architecture

Components deployed:
- **Frontend**: gRPC API (port 7233)
- **History**: Workflow state management
- **Matching**: Task queue routing
- **Worker**: Internal system workflows
- **Web**: UI dashboard
- **PostgreSQL**: Persistence backend

## Troubleshooting

### Schema setup fails

Check logs:
```bash
kubectl logs -n lakehouse -l app.kubernetes.io/component=schema-setup
```

### Workflows not starting

Verify frontend is reachable:
```bash
kubectl exec -n lakehouse temporal-admintools-0 -- \
  temporal operator cluster health
```

### Worker not connecting

Check worker logs and verify:
1. Temporal frontend service is running
2. Namespace exists
3. Task queue name matches

# Local Docker Registry

In-cluster Docker registry for development. Avoids need for external registry authentication.

## Deployment

```bash
# Add Helm repo
helm repo add twuni https://helm.twun.io

# Install registry
helm install registry twuni/docker-registry -n lakehouse -f values.yaml
```

## Usage

### Port-Forward for Local Access

```bash
kubectl port-forward svc/registry-docker-registry 5000:5000 -n lakehouse &
```

### Build and Push Images

```bash
# Build image
docker build -t localhost:5000/payment-gateway:latest ./services/gateway

# Push to registry
docker push localhost:5000/payment-gateway:latest
```

### Use in Kubernetes Deployments

```yaml
containers:
  - name: gateway
    image: registry-docker-registry.lakehouse.svc.cluster.local:5000/payment-gateway:latest
```

Or with port-forward active:

```yaml
containers:
  - name: gateway
    image: localhost:5000/payment-gateway:latest
```

## Verification

```bash
# Check registry is running
kubectl get pods -n lakehouse -l app=docker-registry

# List images in registry (with port-forward active)
curl -s http://localhost:5000/v2/_catalog
```

## Notes

- No authentication configured (development only)
- 10Gi persistent volume for image storage
- Images survive pod restarts
- For production, use ghcr.io or similar with proper auth

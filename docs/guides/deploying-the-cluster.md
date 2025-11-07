# Deploying the Cluster

This guide provides step-by-step instructions for deploying the complete lakehouse platform to a Kubernetes cluster.

## Overview

The lakehouse platform consists of:
- **MinIO**: S3-compatible object storage
- **Dagster**: Data orchestration and workflow management
- **Trino**: Distributed SQL query engine
- **Polaris**: Apache Iceberg REST catalog

All services are deployed to the `lakehouse` namespace.

## Prerequisites

### Required Tools

```bash
# Verify prerequisites are installed
kubectl version --client    # Kubernetes CLI (v1.24+)
helm version               # Helm package manager (v3.8+)
docker --version          # Docker (for local development)
```

### Cluster Access

Ensure you have access to a Kubernetes cluster:

```bash
# Check cluster connection
kubectl cluster-info

# Verify current context
kubectl config current-context

# List nodes (optional verification)
kubectl get nodes
```

### Required Permissions

Your Kubernetes user/service account needs:
- `create`, `get`, `list`, `update`, `delete` on namespaces
- `create`, `get`, `list`, `update`, `delete` on pods, services, deployments, secrets, configmaps
- `create`, `get`, `list`, `update`, `delete` on persistentvolumeclaims

## Quick Start (Using Makefile)

The fastest way to deploy everything:

```bash
# 1. Verify prerequisites
make check

# 2. Setup Helm repositories
make setup

# 3. Deploy all services
make deploy

# 4. Start port-forwards (in background)
make port-forward-start

# 5. Verify deployment
make status
```

## Step-by-Step Deployment

### Step 1: Verify Prerequisites

```bash
make check
```

This verifies:
- `kubectl` is installed and connected to a cluster
- `helm` is installed
- Cluster is accessible

**Expected Output**:
```
✓ kubectl: Client Version: v1.28.0
✓ helm: v3.12.0
✓ cluster: my-cluster-context
Prerequisites check passed!
```

### Step 2: Setup Helm Repositories

```bash
make setup
```

This adds and updates the required Helm repositories:
- `dagster/dagster` - Dagster orchestration platform
- `trino/trino` - Trino query engine
- `polaris/polaris` - Apache Polaris REST catalog

**Expected Output**:
```
✓ Helm repositories configured
```

### Step 3: Create Namespace

The deployment creates the `lakehouse` namespace automatically, but you can verify:

```bash
kubectl get namespace lakehouse
```

If it doesn't exist, create it manually:

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml
```

### Step 4: Deploy Services

#### Option A: Deploy All Services (Recommended)

```bash
make deploy
```

This deploys services in the correct order:
1. Namespace creation
2. MinIO (S3 storage)
3. Dagster (orchestration)
4. Trino (query engine)
5. Polaris (REST catalog)

**Expected Output**:
```
Deploying lakehouse platform...

Step 1/4: Creating lakehouse namespace...
Step 2/4: Deploying MinIO (S3 storage)...
✓ MinIO deployed
Step 3/4: Deploying Dagster (orchestration)...
✓ Dagster deployed
Step 4/5: Deploying Trino (query engine)...
✓ Trino deployed
Step 5/5: Deploying Polaris (Apache Iceberg REST catalog)...
✓ Polaris deployed

Deployment complete! MinIO is ready with default bucket 'lakehouse'.
Polaris REST catalog is available for unified Iceberg table management.
```

#### Option B: Manual Deployment

If you prefer manual control, deploy services individually:

**1. Deploy MinIO:**
```bash
kubectl apply -f infrastructure/kubernetes/minio/minio-standalone.yaml -n lakehouse
kubectl wait --for=condition=ready pod -l app=minio -n lakehouse --timeout=120s
```

**2. Deploy Dagster:**
```bash
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n lakehouse --wait --timeout 10m

# Scale down default user code deployment (we'll deploy our own)
kubectl scale deployment -n lakehouse \
  dagster-dagster-user-deployments-dagster-user-code --replicas=0
```

**3. Deploy Trino:**
```bash
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --wait --timeout 10m
```

**4. Deploy Polaris:**
```bash
# Apply secrets first (if not already applied)
kubectl apply -f infrastructure/kubernetes/polaris/secrets.yaml

# Deploy Polaris
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### Step 5: Verify Deployment

Check that all services are running:

```bash
make status
```

**Expected Output**:
```
Lakehouse Cluster Status
=======================

Namespace:
NAME       STATUS   AGE
lakehouse  Active   5m

Helm Releases:
NAME     NAMESPACE  REVISION  STATUS    CHART
dagster  lakehouse  1         deployed  dagster-1.5.0
polaris  lakehouse  1         deployed  polaris-0.1.0
trino    lakehouse  1         deployed  trino-0.15.0

Pods:
NAME                                    READY   STATUS    RESTARTS   AGE
dagster-dagster-webserver-xxx          1/1     Running   0          4m
dagster-dagster-daemon-xxx              1/1     Running   0          4m
minio-xxx                               1/1     Running   0          5m
polaris-xxx                             1/1     Running   0          3m
trino-coordinator-xxx                   1/1     Running   0          4m
trino-worker-xxx                        1/1     Running   0          4m

Services:
NAME                    TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)
dagster-dagster-webserver  ClusterIP   10.x.x.x      <none>        80/TCP
minio                    ClusterIP   10.x.x.x      <none>        9000/TCP,9001/TCP
polaris                  ClusterIP   10.x.x.x      <none>        8181/TCP
trino                    ClusterIP   10.x.x.x      <none>        8080/TCP
```

### Step 6: Setup Port-Forwarding

To access services locally, start port-forwards:

```bash
make port-forward-start
```

This starts background port-forwards for:
- **Dagster**: http://localhost:3001
- **Trino**: http://localhost:8080
- **MinIO API**: http://localhost:9000
- **MinIO Console**: http://localhost:9001
- **Polaris**: http://localhost:8181

**Check active port-forwards:**
```bash
make port-forward-status
```

**Stop port-forwards:**
```bash
make port-forward-stop
```

## Post-Deployment Setup

### 1. Initialize Polaris RBAC

After deployment, set up Polaris RBAC:

```bash
# Set bootstrap credentials
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"  # pragma: allowlist secret

# Initialize Polaris
make init-polaris
```

See [Setting Up Polaris](setup-polaris.md) for detailed instructions.

### 2. Deploy Dagster User Code

Deploy your orchestration code:

```bash
make deploy-dagster-code
```

See [Deploying Dagster User Code](deploying-dagster-user-code.md) for detailed instructions.

### 3. Verify End-to-End

Test that everything works together:

```bash
# Test Polaris connectivity
make polaris-test

# Check Dagster UI (should show your assets)
# Open http://localhost:3001 in browser

# Test Trino connectivity
curl http://localhost:8080/v1/info
```

## Troubleshooting

### Services Not Starting

**Check pod status:**
```bash
kubectl get pods -n lakehouse
kubectl describe pod <pod-name> -n lakehouse
kubectl logs <pod-name> -n lakehouse --tail=100
```

**Common Issues:**
- **Image pull errors**: Check image names and registry access
- **Resource constraints**: Increase resource limits in values.yaml
- **Secret not found**: Ensure secrets are created before deployment
- **Database connection**: Verify database is accessible

### MinIO Not Ready

```bash
# Check MinIO pod
kubectl get pods -n lakehouse -l app=minio
kubectl logs -n lakehouse -l app=minio --tail=50

# Verify bucket creation job
kubectl get jobs -n lakehouse
kubectl logs -n lakehouse job/minio-create-bucket
```

### Dagster Not Accessible

```bash
# Check Dagster pods
kubectl get pods -n lakehouse -l app.kubernetes.io/instance=dagster

# Check webserver logs
kubectl logs -n lakehouse -l app.kubernetes.io/instance=dagster,component=webserver --tail=50

# Verify service
kubectl get svc -n lakehouse dagster-dagster-webserver
```

### Trino Not Starting

```bash
# Check Trino pods
kubectl get pods -n lakehouse -l app=trino

# Check coordinator logs
kubectl logs -n lakehouse -l app=trino,component=coordinator --tail=50

# Verify catalog configuration
kubectl exec -n lakehouse deployment/trino-coordinator -- cat /etc/trino/catalog/lakehouse.properties
```

### Polaris Not Accessible

```bash
# Check Polaris pod
kubectl get pods -n lakehouse -l app.kubernetes.io/name=polaris
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris --tail=50

# Test connectivity
make polaris-status
make polaris-test
```

## Cleanup

To completely remove the deployment:

```bash
# Complete reset (destroys everything)
make nuke

# Or individual teardown
make destroy
```

## Next Steps

After successful deployment:

1. **Set up Polaris RBAC**: [Setting Up Polaris](setup-polaris.md)
2. **Deploy Dagster user code**: [Deploying Dagster User Code](deploying-dagster-user-code.md)
3. **Configure data sources**: Set up Reddit API credentials and other data sources
4. **Run first pipeline**: Materialize assets in Dagster UI

## Related Guides

- [Setting Up Polaris](setup-polaris.md) - Configure Polaris RBAC after deployment
- [Deploying Dagster User Code](deploying-dagster-user-code.md) - Deploy orchestration code
- [Updating Polaris](update-polaris.md) - Update Polaris configuration and versions

## Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Project CLAUDE.md](../../CLAUDE.md) - Project architecture and patterns

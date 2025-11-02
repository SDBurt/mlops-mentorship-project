# Infrastructure Documentation

This directory contains Kubernetes manifests, Helm configurations, and documentation for deploying the lakehouse platform.

## Directory Structure

```
infrastructure/
├── helm/                   # Local Helm charts
│   └── garage/            # Garage S3 Helm chart (fetched during setup)
├── kubernetes/            # Kubernetes manifests and Helm values
│   ├── namespace.yaml    # Single lakehouse namespace for all services
│   ├── minio/            # MinIO S3 configuration
│   ├── dagster/          # Dagster configuration
│   ├── trino/            # Trino configuration
│   └── polaris/          # Polaris REST catalog configuration (Phase 3)
└── README.md             # This file
```

**Note:** All services deploy to the single `lakehouse` namespace following Kubernetes best practices - services that communicate should live together.

## Getting Started

Follow the comprehensive step-by-step guide:

**See: [SETUP_GUIDE.md](../docs/SETUP_GUIDE.md)**

This guide walks you through every command with explanations, verification steps, and troubleshooting tips.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Data Sources                       │
│        (APIs, Databases, Files)                 │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│            DLT (Python / Dagster)               │
│         Ingestion: Sources → S3                 │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│          MinIO S3 (lakehouse namespace)         │
│       Object Storage: Parquet/Iceberg           │
└───────────┬─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│   Apache Polaris (lakehouse - Phase 3)          │
│   REST Catalog: Unified Iceberg Metadata        │
└───────────┬─────────────────────────────────────┘
            │
    ┌───────┴────────┬──────────────┐
    ▼                ▼              ▼
┌────────┐    ┌──────────┐    ┌─────────┐
│ Trino  │    │ Dagster  │    │   DBT   │
│Query   │    │Orchestr. │    │Transform│
└────────┘    └──────────┘    └─────────┘
    │              │              │
    └──────────────┴──────────────┘
                   ▼
        ┌──────────────────┐
        │    PostgreSQL    │
        │  (Dagster embed) │
        │   Metadata DB    │
        └──────────────────┘
```

## Components

### Garage (garage namespace)

**Purpose:** S3-compatible object storage for data lake files

**Resources:**
- StatefulSet: `garage-0`
- Services: `garage-s3-api` (3900), `garage-admin-api` (3903)
- PVCs: `data-garage-0` (10Gi), `meta-garage-0` (1Gi)

**Configuration:**
- Helm chart: `helm/garage/` (local)
- Values: `kubernetes/garage/values.yaml`

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/namespaces/garage.yaml
helm upgrade --install garage helm/garage \
  -f kubernetes/garage/values.yaml \
  -n garage --create-namespace --wait

# Initialize cluster
POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')
NODE_ID=$(kubectl exec -n garage $POD -- /garage status 2>/dev/null | grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $1}')
kubectl exec -n garage $POD -- /garage layout assign -z garage-dc -c 10G $NODE_ID
kubectl exec -n garage $POD -- /garage layout apply --version 1

# Create bucket
kubectl exec -n garage $POD -- /garage bucket create lakehouse
kubectl exec -n garage $POD -- /garage key create lakehouse-access
kubectl exec -n garage $POD -- /garage bucket allow --read --write lakehouse --key lakehouse-access

# Access UI
kubectl port-forward -n garage svc/garage-s3-api 3900:3900
```

**Troubleshooting:**
- If cluster not initializing: Check node status with `/garage status`
- If layout apply fails: Ensure version number is correct (increment from current)

---

### PostgreSQL (database namespace)

**Purpose:** Metadata database for Airbyte and Dagster

**Resources:**
- StatefulSet: `postgres-0`
- Service: `postgres.database.svc.cluster.local:5432`
- PVC: `postgres-storage-postgres-0` (20Gi)

**Configuration:**
- Secrets: `kubernetes/database/postgres-secret.yaml` (gitignored)
- StatefulSet: `kubernetes/database/postgres-statefulset.yaml`
- Service: `kubernetes/database/postgres-service.yaml`

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/namespaces/database.yaml
kubectl apply -f kubernetes/database/postgres-secret.yaml
kubectl apply -f kubernetes/database/postgres-statefulset.yaml
kubectl apply -f kubernetes/database/postgres-service.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgres -n database --timeout=300s

# Verify
kubectl exec -n database postgres-0 -- pg_isready -U postgres
kubectl exec -it -n database postgres-0 -- psql -U postgres -c "\l"

# Connect
kubectl exec -it -n database postgres-0 -- psql -U airbyte -d airbyte
```

**Connection Details:**
- Host: `postgres.database.svc.cluster.local`
- Port: `5432`
- Databases: `airbyte`, `dagster`
- Users: `airbyte`, `dagster`
- Passwords: Stored in `postgres-secret.yaml`

---

### Airbyte (airbyte namespace)

**Purpose:** Data ingestion from sources to Garage S3

**Resources:**
- Deployments: server, webapp, worker, temporal, connector-builder
- StatefulSet: minio (internal state storage)
- Services: webapp (80), server (8001)

**Configuration:**
- Helm chart: `airbyte/airbyte` (v1.8.5)
- Values: `kubernetes/airbyte/values.yaml`
- Secrets: `kubernetes/airbyte/secrets.yaml` (gitignored)

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/namespaces/airbyte.yaml
kubectl apply -f kubernetes/airbyte/secrets.yaml
helm upgrade --install airbyte airbyte/airbyte \
  --version 1.8.5 \
  -f kubernetes/airbyte/values.yaml \
  -n airbyte --create-namespace --wait --timeout 10m

# Verify
kubectl get pods -n airbyte

# Access UI
# Note: In Airbyte V2, the UI is served by airbyte-server
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001
# Open: http://localhost:8080
```

**Default Credentials:**
- Email: admin@example.com
- Password: password

**Troubleshooting:**
- CrashLoopBackOff: Check database connection in secrets
- MinIO errors: Verify MinIO credentials in secrets.yaml
- Logs: `kubectl logs -n airbyte <pod-name>`

---

### Dagster (dagster namespace)

**Purpose:** Workflow orchestration for DBT and data pipelines

**Resources:**
- Deployments: webserver, daemon
- StatefulSet: postgresql (Dagster metadata)
- Services: webserver (80)

**Configuration:**
- Helm chart: `dagster/dagster`
- Values: `kubernetes/dagster/values.yaml`
- Secrets: `kubernetes/dagster/secrets.yaml` (gitignored)

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/namespaces/dagster.yaml
kubectl apply -f kubernetes/dagster/secrets.yaml
helm upgrade --install dagster dagster/dagster \
  -f kubernetes/dagster/values.yaml \
  -n dagster --create-namespace --wait --timeout 10m

# Verify
kubectl get pods -n dagster

# Access UI
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80
# Open: http://localhost:3000
```

**User Code Deployment:**
- Located in: `../orchestration/dagster/`
- Configure in: `values.yaml` under `dagster-user-deployments`

---

### Trino (trino namespace)

**Purpose:** Distributed SQL query engine for Iceberg tables

**Resources:**
- Deployment: coordinator
- StatefulSet: worker
- Service: `trino:8080`

**Configuration:**
- Helm chart: `trino/trino`
- Values: `kubernetes/trino/values.yaml`
- Catalogs: Iceberg (Garage S3)

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/namespaces/trino.yaml
helm upgrade --install trino trino/trino \
  -f kubernetes/trino/values.yaml \
  -n trino --create-namespace --wait --timeout 10m

# Verify
kubectl get pods -n trino

# Access UI
kubectl port-forward -n trino svc/trino 8080:8080
# Open: http://localhost:8080

# Connect to CLI
POD=$(kubectl get pods -n trino -l app.kubernetes.io/component=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n trino $POD -- trino
```

**Iceberg Configuration:**
- Catalog: `iceberg`
- Warehouse: `s3://lakehouse/warehouse/`
- S3 Endpoint: `http://garage-s3-api.garage.svc.cluster.local:3900`

---

## Secret Management

All secrets are **gitignored** via pattern: `**/*/secrets.yaml`

### Creating Secrets

```bash
# Generate random password
openssl rand -base64 32

# Encode for Kubernetes
echo -n "your-password" | base64

# Decode (for verification)
echo "base64-string" | base64 -d
```

### Required Secrets Files

1. **database/postgres-secret.yaml**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: postgres-secret
     namespace: database
   type: Opaque
   data:
     postgres-password: <base64>
     airbyte-password: <base64>
   ```

2. **airbyte/secrets.yaml**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: airbyte-secrets
     namespace: airbyte
   type: Opaque
   stringData:
     DATABASE_HOST: postgres.database.svc.cluster.local
     DATABASE_PORT: "5432"
     DATABASE_DB: airbyte
     DATABASE_USER: airbyte
     DATABASE_PASSWORD: <plaintext>
     MINIO_ROOT_USER: minioadmin
     MINIO_ROOT_PASSWORD: <plaintext>
   ```

3. **dagster/secrets.yaml**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: dagster-postgresql-secret
     namespace: dagster
   type: Opaque
   stringData:
     postgresql-password: <plaintext>
   ```

---

## Common Operations

### Deploy Everything (Manual)

```bash
# 1. Prerequisites
helm repo add airbyte https://airbytehq.github.io/helm-charts
helm repo add dagster https://dagster-io.github.io/helm
helm repo add trino https://trinodb.github.io/charts
helm repo update

# 2. Fetch Garage chart
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo
cp -r /tmp/garage-repo/script/helm/garage helm/garage
rm -rf /tmp/garage-repo

# 3. Deploy in order
# See docs/SETUP_GUIDE.md for detailed steps

# Create lakehouse namespace
kubectl apply -f kubernetes/namespace.yaml

# Garage
kubectl apply -f kubernetes/garage/secrets.yaml  # If needed
helm upgrade --install garage helm/garage -f kubernetes/garage/values.yaml -n lakehouse --wait

# PostgreSQL
kubectl apply -f kubernetes/database/postgres-secret.yaml
kubectl apply -f kubernetes/database/postgres-statefulset.yaml
kubectl apply -f kubernetes/database/postgres-service.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n lakehouse --timeout=300s

# Airbyte
kubectl apply -f kubernetes/airbyte/secrets.yaml
helm upgrade --install airbyte airbyte/airbyte --version 1.8.5 -f kubernetes/airbyte/values.yaml -n lakehouse --wait --timeout 10m

# Dagster
kubectl apply -f kubernetes/dagster/secrets.yaml
helm upgrade --install dagster dagster/dagster -f kubernetes/dagster/values.yaml -n lakehouse --wait --timeout 10m

# Trino
kubectl apply -f kubernetes/trino/secrets.yaml
helm upgrade --install trino trino/trino -f kubernetes/trino/values.yaml -n lakehouse --wait --timeout 10m
```

### Teardown Everything

```bash
# Uninstall Helm releases
helm uninstall dagster -n lakehouse
helm uninstall trino -n lakehouse
helm uninstall airbyte -n lakehouse
helm uninstall garage -n lakehouse

# Delete namespace (deletes all resources)
kubectl delete namespace lakehouse --wait=true
```

See [TEARDOWN.md](../docs/TEARDOWN.md) for detailed teardown steps with verification.

### Check Status

```bash
# Lakehouse namespace
kubectl get namespace lakehouse

# All pods in lakehouse namespace
kubectl get pods -n lakehouse

# All services in lakehouse namespace
kubectl get svc -n lakehouse

# All PVCs in lakehouse namespace
kubectl get pvc -n lakehouse

# Helm releases in lakehouse namespace
helm list -n lakehouse
```

### Port-Forward All Services

Open multiple terminals:

```bash
# Terminal 1: Airbyte
# Note: In Airbyte V2, the UI is served by airbyte-server
kubectl port-forward -n lakehouse svc/airbyte-airbyte-server-svc 8080:8001

# Terminal 2: Dagster
kubectl port-forward -n lakehouse svc/dagster-dagster-webserver 3000:80

# Terminal 3: Trino
kubectl port-forward -n lakehouse svc/trino 8081:8080

# Terminal 4: Garage S3
kubectl port-forward -n lakehouse svc/garage-s3-api 3900:3900
```

Access:
- Airbyte: http://localhost:8080
- Dagster: http://localhost:3000
- Trino: http://localhost:8081

### View Logs

```bash
# Garage
kubectl logs -n lakehouse -l app.kubernetes.io/name=garage --tail=100 -f

# PostgreSQL
kubectl logs -n lakehouse -l app=postgres --tail=100 -f

# Airbyte (server)
kubectl logs -n lakehouse -l app.kubernetes.io/name=server --tail=100 -f

# Dagster (webserver)
kubectl logs -n lakehouse -l component=dagster-webserver --tail=100 -f

# Trino (coordinator)
kubectl logs -n lakehouse -l app.kubernetes.io/component=coordinator --tail=100 -f
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n <namespace>

# Describe pod for events
kubectl describe pod <pod-name> -n <namespace>

# View logs
kubectl logs <pod-name> -n <namespace> --tail=100

# Check resource usage
kubectl top pods -n <namespace>
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n <namespace>

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup <service>.<namespace>.svc.cluster.local

# Check network policies
kubectl get networkpolicies -n <namespace>
```

### Database Connection Issues

```bash
# Test PostgreSQL from another pod
kubectl exec -it -n database postgres-0 -- psql -U postgres -c "\conninfo"

# Test from Airbyte namespace
kubectl run -it --rm pg-test --image=postgres:17 --restart=Never -n airbyte -- psql -h postgres.database.svc.cluster.local -U airbyte -d airbyte
```

### Helm Deployment Failed

```bash
# Check release status
helm status <release-name> -n <namespace>

# View release history
helm history <release-name> -n <namespace>

# Get values used
helm get values <release-name> -n <namespace>

# Rollback
helm rollback <release-name> -n <namespace>

# Force delete and redeploy
helm uninstall <release-name> -n <namespace> --no-hooks
# Then redeploy
```

### PVC Not Binding

```bash
# Check PVC status
kubectl describe pvc <pvc-name> -n <namespace>

# Check storage class
kubectl get storageclass

# Check available PVs
kubectl get pv

# For hostpath (local development)
# Ensure /tmp/hostpath-provisioner exists on node
```

---

## Best Practices

### Development Workflow

1. **Start Small**: Deploy one component at a time
2. **Verify Each Step**: Check pods/services before moving on
3. **Read Logs**: Understand what each component is doing
4. **Use Port-Forward**: Test services locally before exposing

### Configuration Management

1. **Keep values.yaml Minimal**: Only override what's necessary
2. **Externalize Secrets**: Never commit secrets to git
3. **Document Changes**: Add comments explaining custom config
4. **Version Control**: Track Helm chart versions in values files

### Troubleshooting Approach

1. **Check Pod Status**: `kubectl get pods -n <namespace>`
2. **Read Events**: `kubectl describe pod <pod-name> -n <namespace>`
3. **Check Logs**: `kubectl logs <pod-name> -n <namespace>`
4. **Test Connectivity**: Use debug pods to test service connections
5. **Verify Secrets**: Ensure all secrets are created and correct

---

## Additional Resources

- **Main Setup Guide**: [../docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md)
- **Teardown Guide**: [../docs/TEARDOWN.md](../docs/TEARDOWN.md)
- **Architecture**: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- **Project Guide**: [../CLAUDE.md](../CLAUDE.md)

---

## Quick Reference

### Service Mapping (All in `lakehouse` Namespace)

| Service | Component | Ports | DNS (Same Namespace) |
|---------|-----------|-------|---------------------|
| garage | S3 storage | 3900, 3903 | `garage:3900` |
| postgres | Metadata DB | 5432 | `postgres:5432` |
| airbyte-airbyte-server-svc | Ingestion | 8001 | `airbyte-airbyte-server-svc:8001` |
| dagster-dagster-webserver | Orchestration | 80 | `dagster-dagster-webserver:80` |
| trino | Query engine | 8080 | `trino:8080` |

### Storage Usage

| Component | PVC | Size | Purpose |
|-----------|-----|------|---------|
| Garage | data-garage-0 | 10Gi | Object data |
| Garage | meta-garage-0 | 1Gi | Metadata |
| PostgreSQL | postgres-storage-postgres-0 | 20Gi | All databases |
| Dagster | data-dagster-postgresql-0 | 5Gi | Dagster metadata |
| Airbyte | airbyte-minio-pv-claim | 500Mi | Airbyte state |

### Helm Charts (All in `lakehouse` Namespace)

| Release | Chart | Version | Namespace |
|---------|-------|---------|-----------|
| garage | local/garage | 0.7.2 | lakehouse |
| airbyte | airbyte/airbyte | 1.8.5 | lakehouse |
| dagster | dagster/dagster | 1.11.15 | lakehouse |
| trino | trino/trino | 1.41.0 | lakehouse |

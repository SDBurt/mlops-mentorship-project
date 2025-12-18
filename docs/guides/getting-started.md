# Getting Started - Complete Setup Guide

This guide will walk you through setting up the complete MLOps Lakehouse Platform from scratch. Follow these steps carefully for a smooth setup experience.

## What You'll Build

By the end of this guide, you'll have:
- A running Kubernetes-based data lakehouse platform
- MinIO S3 storage with Iceberg tables
- Apache Polaris REST catalog with RBAC
- Dagster for data orchestration and ML training
- Trino for distributed SQL queries
- **Feast** feature store for real-time ML features
- **MLflow** for model tracking and registration
- All services configured and ready to use

## Prerequisites

### Required Tools

Install these tools before beginning:

```bash
# Kubernetes CLI (v1.24+)
kubectl version --client

# Helm package manager (v3.8+)
helm version

# Docker (for local Kubernetes cluster)
docker --version
```

**Installation Help**:
- **kubectl**: https://kubernetes.io/docs/tasks/tools/
- **Helm**: https://helm.sh/docs/intro/install/
- **Docker Desktop**: https://www.docker.com/products/docker-desktop/

### Kubernetes Cluster

You need a running Kubernetes cluster. Options:

**Docker Desktop** (Recommended for local development):
1. Install Docker Desktop
2. Go to Settings → Kubernetes → Enable Kubernetes
3. Wait for it to start (green indicator)

**Alternative Options**:
- **minikube**: `minikube start`
- **kind**: `kind create cluster`
- **Cloud** (GKE, EKS, AKS): Follow provider documentation

### Verify Setup

```bash
# Check kubectl can connect to your cluster
kubectl cluster-info

# Verify current context
kubectl config current-context

# List nodes (should show at least 1 node)
kubectl get nodes
```

Expected output:
```
Kubernetes control plane is running at https://...
CoreDNS is running at https://...

NAME             STATUS   ROLES           AGE   VERSION
docker-desktop   Ready    control-plane   5d    v1.28.0
```

## Step 1: Clean Slate (Optional but Recommended)

If you've deployed this before or want a fresh start:

```bash
# Navigate to project directory
cd /path/to/kubernetes

# Complete teardown (removes everything)
make nuke
```

**What this does**:
- Stops all port-forwards
- Uninstalls all Helm releases (Polaris, Trino, Dagster)
- Deletes all resources (MinIO, PVCs, jobs)
- Removes the `lakehouse` namespace
- Cleans local credential files

**Confirmation**: You'll be asked to confirm. This is destructive!

## Step 2: Set Up Secrets

All secrets must be configured before deployment. Let's set them up step by step.

### Security Best Practices

**⚠️ IMPORTANT**: Never commit secrets to version control. Follow these practices:

**For Local Development**:
- **Use `.env` files**: Store secrets in a `.env` file (excluded via `.gitignore`) and source it when needed
- **Use inline environment variables**: For one-off commands, pass secrets inline: `POLARIS_BOOTSTRAP_CLIENT_SECRET="..." make init-polaris`
- **Never use plain `export`**: Avoid exporting secrets to your shell environment as they persist in your session history

**For Production**:
- **Use a secret manager**: Integrate with HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, or GCP Secret Manager
- **Use Kubernetes Secrets**: Store secrets as Kubernetes Secret resources (already configured in this guide)
- **Rotate regularly**: Implement secret rotation policies

**Files to Never Commit**:
- `.env` files containing secrets
- `.credentials/` directories
- Any files with hardcoded credentials

**Example `.gitignore` patterns** (should already be configured):
```
.env
.env.*
*.secrets.yaml
.credentials/
**/secrets.yaml
```

### 2.1 Polaris Secrets

Create Polaris secrets for bootstrap admin access and MinIO storage:

```bash
# Copy the example file
cp infrastructure/kubernetes/polaris/polaris-secrets.yaml.example \
   infrastructure/kubernetes/polaris/polaris-secrets.yaml

# Edit the file and replace CHANGEME placeholders
# Use strong, random secrets (not the examples!)
nano infrastructure/kubernetes/polaris/polaris-secrets.yaml
```

**Generate secure secrets**:
```bash
# Generate random passwords
openssl rand -base64 32  # For bootstrap admin secret
openssl rand -base64 32  # For MinIO password
```

Update the file to look like this (with YOUR secrets):
```yaml
---
# Storage credentials for MinIO S3 access
apiVersion: v1
kind: Secret
metadata:
  name: polaris-storage-secret
  namespace: lakehouse
type: Opaque
stringData:
  aws-access-key-id: admin
  aws-secret-access-key: YOUR_MINIO_PASSWORD_HERE  # Generate one!

---
# Bootstrap credentials for Polaris
apiVersion: v1
kind: Secret
metadata:
  name: polaris-bootstrap-credentials
  namespace: lakehouse
type: Opaque
stringData:
  bootstrap-credentials: "lakehouse,polaris_admin,YOUR_BOOTSTRAP_SECRET_HERE"  # pragma: allowlist secret
  client-id: "polaris_admin"
  client-secret: "YOUR_BOOTSTRAP_SECRET_HERE"  # pragma: allowlist secret
```

### 2.2 MinIO Secrets

```bash
# Copy the example file
cp infrastructure/kubernetes/minio/minio-secrets.yaml.example \
   infrastructure/kubernetes/minio/minio-secrets.yaml

# Edit and set password (use same as Polaris storage secret)
nano infrastructure/kubernetes/minio/minio-secrets.yaml
```

**Important**: Use the SAME password here as in Polaris storage secret!

```yaml
stringData:
  root-user: admin
  root-password: YOUR_MINIO_PASSWORD_HERE  # Same as above!
```

### 2.3 Trino Secrets

```bash
# Copy the example file
cp infrastructure/kubernetes/trino/secrets.yaml.example \
   infrastructure/kubernetes/trino/secrets.yaml

# Edit and set credentials
nano infrastructure/kubernetes/trino/secrets.yaml
```

Replace placeholders:
- `CHANGEME_S3_ACCESS_KEY`: Use `admin`
- `CHANGEME_S3_SECRET_KEY`: Use your MinIO password
- `CHANGEME_POLARIS_CLIENT_ID`: Leave empty for now (will be generated)
- `CHANGEME_POLARIS_CLIENT_SECRET`: Leave empty for now (will be generated)

### 2.4 Dagster User Code Secrets

```bash
# Copy the example file
cp infrastructure/kubernetes/dagster/user-code-secrets.yaml.example \
   infrastructure/kubernetes/dagster/user-code-secrets.yaml

# Edit and set credentials
nano infrastructure/kubernetes/dagster/user-code-secrets.yaml
```

**Reddit API** (Optional - for Reddit data source):
1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" type application
3. Copy client ID and secret

Replace placeholders in the file.

### 2.5 Verify All Secrets Are Created

```bash
# Check all secret files exist
make validate-secrets
```

Expected output:
```
✓ MinIO secrets found
✓ Trino secrets found
✓ Polaris secrets found
✓ Dagster user code secrets found
All required secrets are configured!
```

## Step 3: Deploy the Platform

Now that secrets are configured, deploy everything with a single command:

```bash
make setup
```

**What this does** (automatically):
1. Checks prerequisites (kubectl, helm, cluster access)
2. Adds and updates Helm repositories (Dagster, Trino)
3. Clones Apache Polaris repository
4. Deploys all services in correct order:
   - Namespace creation (`lakehouse`)
   - MinIO (S3 storage)
   - Dagster (orchestration with embedded PostgreSQL)
   - Trino (query engine, without lakehouse catalog initially)
   - Polaris (REST catalog with in-memory persistence)

**Expected Duration**: 5-10 minutes

**Expected Output**:
```
==========================================
   Lakehouse Platform Setup
==========================================
Step 1/4: Checking prerequisites...
✓ kubectl found
✓ helm found
✓ cluster accessible

Step 2/4: Setting up Helm repositories...
✓ Helm repositories configured

Step 3/4: Cloning Apache Polaris repository...
✓ Polaris repository ready

Step 4/4: Deploying platform...

Deploying lakehouse platform...
Step 1/6: Creating lakehouse namespace...
✓ Namespace created

Step 2/6: Deploying MinIO...
✓ MinIO deployed

Step 3/6: Deploying secrets...
✓ Secrets applied

Step 4/6: Deploying Dagster...
✓ Dagster deployed

Step 5/6: Deploying Trino...
✓ Trino deployed (without lakehouse catalog)

Step 6/6: Deploying Polaris...
✓ Polaris deployed

==========================================
   Deployment Complete!
==========================================

Next Steps:
  1. Initialize Polaris catalog:
     make init-polaris

  2. Connect Trino to Polaris:
     make configure-trino-polaris

  3. Deploy Dagster user code:
     make deploy-dagster-code

  4. Start port-forwards:
     make port-forward-start

  5. Access services:
     - Dagster UI: http://localhost:3000
     - Trino UI: http://localhost:8080
     - MinIO Console: http://localhost:9001
```

### Verify Deployment

```bash
# Check all services are running
make status
```

Expected output shows all pods in `Running` status.

## Step 4: Initialize Polaris Catalog

Polaris needs to be initialized with RBAC (roles, permissions, and service accounts):

> **🔒 Security Note**: See [Security Best Practices](#security-best-practices) above. Instead of exporting secrets, use one of these secure methods:

**Option 1: Inline environment variables** (recommended for one-off commands):
```bash
# Pass credentials inline (not exported to shell)
POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin" \
POLARIS_BOOTSTRAP_CLIENT_SECRET="YOUR_GENERATED_SECRET_HERE" \  # pragma: allowlist secret
make init-polaris
```

**Option 2: Use a `.env` file** (for repeated use):
```bash
# Create .env file (gitignored) with:
# POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
# POLARIS_BOOTSTRAP_CLIENT_SECRET="YOUR_GENERATED_SECRET_HERE" # pragma: allowlist secret

# Source and run
source .env && make init-polaris
```

**What this does**:
1. Creates `lakehouse` catalog
2. Creates `dagster_user` service account
3. Sets up RBAC (roles and permissions)
4. Grants `CATALOG_MANAGE_CONTENT` privilege
5. Saves credentials to `infrastructure/kubernetes/polaris/.credentials/dagster_user.txt`

**Expected Output**:
```
==========================================
   Polaris Catalog Initialization
==========================================

[INFO] Checking prerequisites...
[SUCCESS] Prerequisites check passed
[INFO] Testing connectivity to Polaris...
[SUCCESS] Connected to Polaris and authenticated
[INFO] Creating catalog 'lakehouse'...
[SUCCESS] Catalog 'lakehouse' created
[INFO] Creating principal: dagster_user...
[SUCCESS] Principal 'dagster_user' created
[INFO] Client ID: abc123xyz
[INFO] Client Secret: def456uvw
[SUCCESS] Credentials saved
[INFO] Creating principal role: dagster_role...
[SUCCESS] Principal role 'dagster_role' created
[INFO] Granting catalog role to principal role...
[SUCCESS] Catalog role granted to principal role
[INFO] Granting CATALOG_MANAGE_CONTENT privilege...
[SUCCESS] CATALOG_MANAGE_CONTENT privilege granted

==========================================
   Polaris Initialization Complete!
==========================================

Credentials saved to: infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
```

**Troubleshooting**:
- If you get "Cannot connect to Polaris", start port-forwarding: `make port-forward-start`
- If credentials are wrong, check your polaris-secrets.yaml file

> **Note**: Step 6 (Deploy Dagster User Code) is optional — only required if you are deploying custom Dagster user jobs/code.

## Step 5: Configure Trino-Polaris Integration

Connect Trino to the Polaris catalog so it can query Iceberg tables:

```bash
make configure-trino-polaris
```

**What this does**:
1. Reads dagster_user credentials from Step 4
2. Updates Trino secrets with Polaris OAuth credentials
3. Restarts Trino to apply configuration
4. Trino can now query tables via Polaris catalog

> **Note**: Step 6 (Deploy Dagster User Code) is optional — only required if you are deploying custom Dagster user jobs/code.

**Expected Output**:
```
Configuring Trino-Polaris integration...
Reading Polaris credentials...
✓ Credentials found
Updating Trino secrets...
✓ Secrets updated
Restarting Trino...
✓ Trino restarted

Trino-Polaris integration configured!
Trino can now query Iceberg tables via Polaris catalog.
```

## Step 6: Deploy Dagster User Code (Optional)

Deploy the Dagster user code for data pipelines:

```bash
make deploy-dagster-code
```

This deploys Python code for orchestrating data ingestion and transformations.

> **Note**: This step is optional — only required if you are deploying custom Dagster user jobs/code. You can skip this if you're using the default bundled jobs or only evaluating the stack locally.

## Step 7: Access Services

Start port-forwarding to access services from your local machine:

```bash
make port-forward-start
```

**Services Available**:
- **Dagster UI**: http://localhost:3000 (data orchestration & ML training)
- **MLflow UI**: http://localhost:5001 (model registry)
- **Feast API**: http://localhost:6566 (feature store)
- **Trino UI**: http://localhost:8080 (SQL queries)
- **MinIO Console**: http://localhost:9001 (S3 storage, login: admin/YOUR_MINIO_PASSWORD_HERE)
- **Polaris REST API**: http://localhost:8181 (catalog API)
- **Superset**: http://localhost:8089 (dashboards)

**Check port-forward status**:
```bash
make port-forward-status
```

**Stop port-forwards** (when done):
```bash
make port-forward-stop
```

## Step 8: Verify Everything Works

### 8.1 Test Polaris Connectivity

> **🔒 Security Note**: See [Security Best Practices](#security-best-practices) above. The credentials file is gitignored, but prefer inline variables for one-off commands.

**Option 1: Inline environment variables** (recommended):
```bash
# Read credentials and use inline (credentials file is gitignored)
POLARIS_CLIENT_ID=$(grep POLARIS_CLIENT_ID infrastructure/kubernetes/polaris/.credentials/dagster_user.txt | cut -d'=' -f2 | tr -d '"')
POLARIS_CLIENT_SECRET=$(grep POLARIS_CLIENT_SECRET infrastructure/kubernetes/polaris/.credentials/dagster_user.txt | cut -d'=' -f2 | tr -d '"')

curl -s --user "${POLARIS_CLIENT_ID}:${POLARIS_CLIENT_SECRET}" \
  http://localhost:8181/api/catalog/v1/oauth/tokens \
  -d 'grant_type=client_credentials' \
  -d 'scope=PRINCIPAL_ROLE:ALL'
```

**Option 2: Source credentials file** (if file is properly gitignored):
```bash
# Source credentials (file should be in .gitignore)
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt

curl -s --user "${POLARIS_CLIENT_ID}:${POLARIS_CLIENT_SECRET}" \
  http://localhost:8181/api/catalog/v1/oauth/tokens \
  -d 'grant_type=client_credentials' \
  -d 'scope=PRINCIPAL_ROLE:ALL'
```

Expected: JSON response with `access_token`

### 8.2 Test Trino Query

```bash
# Connect to Trino via kubectl
kubectl exec -n lakehouse deployment/trino-coordinator -it -- trino

# Run these queries:
SHOW CATALOGS;
SHOW SCHEMAS FROM lakehouse;
```

Expected output:
```
trino> SHOW CATALOGS;
  Catalog
-----------
 lakehouse
 system
(2 rows)

trino> SHOW SCHEMAS FROM lakehouse;
 Schema
--------
(0 rows)
```

### 8.3 Check Dagster UI

1. Open http://localhost:3000
2. You should see the Dagster UI
3. Navigate to "Assets" to see available data assets

## Common Issues and Solutions

### Issue: Port already in use

**Symptom**: `bind: address already in use`

**Solution**:
```bash
# Kill existing port-forwards
make port-forward-stop

# Or find and kill specific port
lsof -i :3000  # Shows what's using port 3000
kill -9 <PID>  # Kill that process
```

### Issue: Pods not starting

**Symptom**: Pods stuck in `Pending` or `CrashLoopBackOff`

**Solution**:
```bash
# Check pod status
kubectl get pods -n lakehouse

# Describe problem pod
kubectl describe pod <pod-name> -n lakehouse

# Check logs
kubectl logs <pod-name> -n lakehouse --tail=50
```

Common causes:
- Insufficient resources: Increase Docker Desktop memory (Settings → Resources)
- Secret not found: Run `make validate-secrets`
- ImagePullBackOff: Check internet connection

### Issue: Cannot connect to Polaris

**Symptom**: `make init-polaris` fails with connection error

**Solution**:
```bash
# Start port-forward to Polaris
kubectl port-forward -n lakehouse svc/polaris 8181:8181 &

# Wait 2 seconds
sleep 2

# Try again
make init-polaris
```

### Issue: Trino cannot query Iceberg tables

**Symptom**: Trino shows "Catalog not found" or "Table not found"

**Solution**:
```bash
# Verify Polaris credentials are configured
kubectl get secret trino-secrets -n lakehouse -o yaml

# Restart Trino
make restart-trino

# Verify connection
kubectl exec -n lakehouse deployment/trino-coordinator -it -- \
  curl -s http://polaris:8181/api/catalog/v1/config
```

## What's Next?

Now that your platform is running, you can:

1. **Create Iceberg Tables**: Use Dagster or Trino to create tables
2. **Ingest Data**: Set up data pipelines in Dagster
3. **Run Transformations**: Use DBT for SQL transformations
4. **Query Data**: Use Trino to query tables via SQL
5. **Explore More**: Check out [deploying-the-cluster.md](deploying-the-cluster.md) for advanced topics

## Useful Commands Reference

### Deployment
```bash
make check              # Verify prerequisites
make setup              # Complete setup and deployment
make deploy             # Deploy all services
make init-polaris       # Initialize Polaris catalog
make configure-trino-polaris  # Connect Trino to Polaris
```

### Monitoring
```bash
make status             # Overall cluster status
make polaris-status     # Polaris-specific status
make polaris-logs       # View Polaris logs
```

### Port-Forwarding
```bash
make port-forward-start  # Start all port-forwards
make port-forward-stop   # Stop all port-forwards
make port-forward-status # Show active port-forwards
```

### Restarts
```bash
make restart-dagster    # Restart Dagster
make restart-trino      # Restart Trino
make restart-polaris    # Restart Polaris
make restart-all        # Restart all services
```

### Teardown
```bash
make destroy            # Remove all services (keeps namespace)
make nuke               # Complete reset (removes everything)
```

## Getting Help

- **Project Documentation**: See [README.md](../../README.md)
- **Makefile Commands**: Run `make help`
- **Component Guides**: Check [docs/guides/](.)
- **Report Issues**: https://github.com/[your-repo]/issues

## Summary

You've successfully:
- ✅ Deployed a complete Kubernetes-based lakehouse platform
- ✅ Configured MinIO S3 storage
- ✅ Set up Apache Polaris REST catalog with RBAC
- ✅ Deployed Dagster for orchestration
- ✅ Configured Trino for SQL queries
- ✅ Verified all services are working

Your platform is ready for data engineering and MLOps workloads!

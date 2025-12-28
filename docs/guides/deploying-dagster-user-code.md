# Deploying Dagster User Code

This guide covers building and deploying the Dagster user code (services/dagster) to Kubernetes using Docker.

## Overview

Dagster user code runs in a separate container that communicates with the Dagster webserver and daemon. This guide covers:
- Building the Docker image
- Creating required secrets
- Applying configuration
- Deploying and updating user code

## Prerequisites

- Docker installed and running
- Kubernetes cluster access
- Dagster deployed (see [Deploying the Cluster](deploying-the-cluster.md))
- Polaris RBAC configured (see [Setting Up Polaris](setup-polaris.md))

## Quick Start

Using the Makefile command:

```bash
make deploy-dagster-code
```

This single command:
1. Builds the Docker image
2. Applies ConfigMap
3. Applies secrets
4. Restarts the deployment

## Step-by-Step Deployment

### Step 1: Prepare Secrets

Before deploying, create the secrets file:

```bash
# Copy the example file
cp infrastructure/kubernetes/dagster/user-code-secrets.yaml.example \
   infrastructure/kubernetes/dagster/user-code-secrets.yaml

# Edit with your credentials
# Use your preferred editor to fill in:
# - Polaris REST Catalog credentials
# - Reddit API credentials
# - MinIO S3 credentials
```

**Required Secrets:**

1. **Polaris REST Catalog Credentials**
   - Get these from `infrastructure/kubernetes/polaris/.credentials/dagster_user.txt` (after running `make init-polaris`)
   - Format: `POLARIS_CLIENT_ID` and `POLARIS_CLIENT_SECRET`

2. **Reddit API Credentials**
   - Create a Reddit application at https://www.reddit.com/prefs/apps
   - Use "script" type for personal use
   - Format: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`

3. **MinIO S3 Credentials**
   - Should match your MinIO deployment credentials
   - Format: `PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID`, `PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY`
   - Also: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

**Example secrets.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dagster-user-code-secrets
  namespace: lakehouse
type: Opaque
stringData:
  POLARIS_CLIENT_ID: "dagster_user_abc123"  # pragma: allowlist secret
  POLARIS_CLIENT_SECRET: "secret_xyz789"  # pragma: allowlist secret
  REDDIT_CLIENT_ID: "your_reddit_client_id"
  REDDIT_CLIENT_SECRET: "your_reddit_secret"  # pragma: allowlist secret
  REDDIT_USER_AGENT: "lakehouse:v1.0.0 (by /u/your_username)"
  PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID: "admin"
  PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY: "your_minio_password"  # pragma: allowlist secret
  AWS_ACCESS_KEY_ID: "admin"
  AWS_SECRET_ACCESS_KEY: "your_minio_password"  # pragma: allowlist secret
```

### Step 2: Build Docker Image

Navigate to the services/dagster directory and build:

```bash
cd services/dagster
docker build -t dagster-user-code:latest .
```

**Note**: The Dockerfile uses `python:3.10-slim` base image and installs dependencies from `pyproject.toml`.

**Build Options:**

For production, you may want to tag with a version:

```bash
docker build -t dagster-user-code:v1.0.0 .
docker build -t dagster-user-code:latest .
```

For a specific registry:

```bash
docker build -t my-registry.io/dagster-user-code:latest .
```

### Step 3: Apply ConfigMap

The ConfigMap contains non-sensitive environment variables:

```bash
kubectl apply -f infrastructure/kubernetes/dagster/user-code-env-configmap.yaml
```

**Verify ConfigMap:**
```bash
kubectl get configmap dagster-user-code-env -n lakehouse -o yaml
```

### Step 4: Apply Secrets

Apply the secrets file:

```bash
kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml
```

**Verify Secrets:**
```bash
# List secrets (values will be base64 encoded)
kubectl get secret dagster-user-code-secrets -n lakehouse -o yaml

# Verify secret exists
kubectl get secret dagster-user-code-secrets -n lakehouse
```

**Important**: The secrets file is gitignored - never commit it to version control.

### Step 5: Restart Deployment

Restart the Dagster user code deployment to pick up changes:

```bash
# Restart the deployment
kubectl rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse

# Wait for rollout to complete
kubectl rollout status deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse --timeout=120s
```

**Alternative**: If the deployment doesn't exist yet, scale it up:

```bash
# Scale up the deployment
kubectl scale deployment/dagster-dagster-user-deployments-dagster-user-code \
  --replicas=1 -n lakehouse

# Wait for pod to be ready
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/instance=dagster,component=user-deployments \
  -n lakehouse --timeout=120s
```

## Using Makefile Command

The easiest way to deploy everything:

```bash
make deploy-dagster-code
```

**What it does:**
1. Builds Docker image: `cd services/dagster && docker build -t dagster-user-code:latest .`
2. Applies ConfigMap: `kubectl apply -f infrastructure/kubernetes/dagster/user-code-env-configmap.yaml`
3. Checks and applies secrets: Validates `user-code-secrets.yaml` exists, then applies it
4. Restarts deployment: Restarts and waits for rollout

**Expected Output:**
```
Rebuilding and deploying Dagster user code...

Step 1/4: Building Docker image...
✓ Docker image built

Step 2/4: Applying ConfigMap...
✓ ConfigMap applied

Step 3/4: Applying Secrets...
✓ Secrets applied

Step 4/4: Restarting Dagster user code deployment...
✓ Dagster user code deployed successfully!

Deployment complete! Access Dagster at http://localhost:3001
```

## Verification

After deployment, verify everything is working:

### 1. Check Pod Status

```bash
kubectl get pods -n lakehouse -l component=user-deployments
```

**Expected**: Pod should be `Running` and `Ready`

### 2. Check Pod Logs

```bash
# Get pod name
POD=$(kubectl get pods -n lakehouse -l component=user-deployments -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs $POD -n lakehouse --tail=50
```

**Expected**: Logs should show:
- Dagster code server starting
- No import errors
- Server listening on port 3030

### 3. Verify in Dagster UI

1. Open Dagster UI: http://localhost:3001 (ensure port-forward is running)
2. Navigate to "Assets" or "Definitions"
3. You should see your assets (e.g., `reddit_posts`)

### 4. Test Asset Materialization

In Dagster UI:
1. Select an asset (e.g., `reddit_posts`)
2. Click "Materialize"
3. Monitor the run - it should succeed

## Updating User Code

When you make changes to your orchestration code:

### 1. Rebuild Docker Image

```bash
cd services/dagster
docker build -t dagster-user-code:latest .
```

**Tip**: Use version tags for production:
```bash
docker build -t dagster-user-code:v1.1.0 .
```

### 2. Redeploy

```bash
make deploy-dagster-code
```

Or manually:
```bash
kubectl rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse
kubectl rollout status deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse
```

### 3. Verify Changes

Check logs and Dagster UI to ensure changes are reflected.

## Updating Secrets

If you need to update secrets (e.g., new Reddit credentials):

### 1. Update Secrets File

Edit `infrastructure/kubernetes/dagster/user-code-secrets.yaml` with new values.

### 2. Apply Updated Secrets

```bash
kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml
```

### 3. Restart Deployment

```bash
kubectl rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse
```

**Note**: Secrets are mounted as environment variables, so pods need to restart to pick up changes.

## Updating ConfigMap

If you need to update non-sensitive configuration:

### 1. Edit ConfigMap

Edit `infrastructure/kubernetes/dagster/user-code-env-configmap.yaml`

### 2. Apply Changes

```bash
kubectl apply -f infrastructure/kubernetes/dagster/user-code-env-configmap.yaml
```

### 3. Restart Deployment

```bash
kubectl rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n lakehouse
```

## Troubleshooting

### Docker Build Fails

**Error**: `ModuleNotFoundError` or import errors

**Solution**:
```bash
# Verify pyproject.toml is correct
cd services/dagster
cat pyproject.toml

# Test build locally
docker build -t dagster-user-code:test .
docker run --rm dagster-user-code:test dagster --version
```

### Secrets File Not Found

**Error**: `user-code-secrets.yaml not found`

**Solution**:
```bash
# Create from example
cp infrastructure/kubernetes/dagster/user-code-secrets.yaml.example \
   infrastructure/kubernetes/dagster/user-code-secrets.yaml

# Edit with your credentials
# Then retry deployment
```

### Pod Not Starting

**Symptoms**: Pod stuck in `Pending` or `CrashLoopBackOff`

**Solutions**:
```bash
# Check pod events
kubectl describe pod <pod-name> -n lakehouse

# Check logs
kubectl logs <pod-name> -n lakehouse --tail=100

# Common issues:
# - Image pull errors: Verify image exists and is accessible
# - Secret not found: Ensure secrets.yaml is applied
# - ConfigMap not found: Ensure ConfigMap is applied
# - Resource constraints: Check resource limits
```

### Assets Not Showing in UI

**Symptoms**: Dagster UI doesn't show your assets

**Solutions**:
```bash
# Verify code server is running
kubectl logs <pod-name> -n lakehouse | grep "code-server"

# Check for import errors
kubectl logs <pod-name> -n lakehouse | grep -i error

# Verify deployment is using correct image
kubectl get deployment dagster-dagster-user-deployments-dagster-user-code \
  -n lakehouse -o jsonpath='{.spec.template.spec.containers[0].image}'

# Restart Dagster webserver (sometimes needed)
make restart-dagster
```

### Authentication Errors

**Symptoms**: Assets fail with Polaris authentication errors

**Solutions**:
```bash
# Verify Polaris credentials in secret
kubectl get secret dagster-user-code-secrets -n lakehouse \
  -o jsonpath='{.data.POLARIS_CLIENT_ID}' | base64 -d
kubectl get secret dagster-user-code-secrets -n lakehouse \
  -o jsonpath='{.data.POLARIS_CLIENT_SECRET}' | base64 -d

# Verify credentials match Polaris
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
echo "Client ID: $POLARIS_CLIENT_ID"
echo "Client Secret: $POLARIS_CLIENT_SECRET"

# Update secret if needed, then restart deployment
```

### S3/MinIO Connection Errors

**Symptoms**: Assets fail with S3 connection errors

**Solutions**:
```bash
# Verify MinIO is accessible
kubectl get svc minio -n lakehouse

# Verify S3 credentials in secret
kubectl get secret dagster-user-code-secrets -n lakehouse \
  -o jsonpath='{.data.PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID}' | base64 -d

# Test MinIO connectivity from pod
kubectl run -it --rm debug --image=amazon/aws-cli --restart=Never -n lakehouse -- \
  aws --endpoint-url=http://minio:9000 s3 ls
```

## Best Practices

1. **Version Your Images**: Use version tags for production deployments
2. **Test Locally First**: Build and test Docker image locally before deploying
3. **Keep Secrets Secure**: Never commit secrets.yaml to version control
4. **Monitor After Deployment**: Watch logs for at least 5 minutes after deployment
5. **Use Makefile**: Prefer `make deploy-dagster-code` for consistency
6. **Document Changes**: Document any manual changes or workarounds

## Related Guides

- [Deploying the Cluster](deploying-the-cluster.md) - Initial cluster deployment
- [Setting Up Polaris](setup-polaris.md) - Polaris RBAC setup (required for Polaris credentials)

## Resources

- [Dagster User Code Documentation](https://docs.dagster.io/concepts/code-locations)
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Project CLAUDE.md](../../CLAUDE.md) - Project architecture and patterns

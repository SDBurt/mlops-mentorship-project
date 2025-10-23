# Kubernetes Configurations

This directory contains Kubernetes manifests and Helm chart configurations for all services.

## Structure

```
.
├── airbyte/              # Airbyte data integration
├── dagster/              # Dagster orchestration
├── garage/               # Garage S3-compatible storage
├── trino/                # Trino SQL query engine
└── namespaces/           # Namespace definitions
```

## Values Files

Each service directory contains two values files:

- **`values.yaml`** - Your custom configuration (actively used)
- **`values-default.yaml`** - Complete default values from the Helm chart (reference only)

### Purpose of values-default.yaml

The `values-default.yaml` files are provided as comprehensive reference documentation showing all available configuration options from the upstream Helm charts. These files are:

- **Not used in deployments** - Only `values.yaml` is used
- **Reference documentation** - Shows all possible configuration options
- **For humans and AI agents** - Complete context for configuration decisions
- **Version snapshots** - Captured at a specific point in time

### Usage

When you want to customize a setting:

1. Look at `values-default.yaml` to see all available options
2. Copy only the settings you want to change to `values.yaml`
3. Modify the values as needed
4. Deploy with `helm upgrade --install -f values.yaml`

### Example

```yaml
# values-default.yaml (full reference)
webapp:
  enabled: true
  service:
    type: ClusterIP
    port: 80
  resources:
    requests:
      memory: 256Mi
      cpu: 100m
    limits:
      memory: 512Mi
      cpu: 500m
  replicas: 1
  # ... hundreds more options ...

# values.yaml (your overrides only)
webapp:
  resources:
    limits:
      memory: 1Gi      # Only override what you need
```

## Regenerating Default Values

To update the default values files (e.g., after upgrading Helm chart versions):

```bash
# Airbyte
helm show values airbyte/airbyte > infrastructure/kubernetes/airbyte/values-default.yaml

# Dagster
helm show values dagster/dagster > infrastructure/kubernetes/dagster/values-default.yaml

# Garage (requires cloning repo)
cd /tmp
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git
cat garage/script/helm/garage/values.yaml > /path/to/infrastructure/kubernetes/garage/values-default.yaml
rm -rf garage
```

## Helm Repositories

```bash
# Airbyte
helm repo add airbyte https://airbytehq.github.io/helm-charts

# Dagster
helm repo add dagster https://dagster-io.github.io/helm

# Trino
helm repo add trino https://trinodb.github.io/charts

# Garage (no Helm repo - uses local chart from git clone)
# See: https://garagehq.deuxfleurs.fr/documentation/cookbook/kubernetes/
```

## Deployment

All services are deployed using the scripts in `/scripts/`:

```bash
./scripts/deploy-all.sh        # Deploy everything
./scripts/deploy-garage.sh     # Deploy Garage only
./scripts/deploy-airbyte.sh    # Deploy Airbyte only
./scripts/deploy-dagster.sh    # Deploy Dagster only
./scripts/deploy-trino.sh      # Deploy Trino only
```

## Configuration Best Practices

### Keep values.yaml Minimal

Only override settings you need to change. The default values are well-tested and appropriate for most use cases.

**Good example:**
```yaml
# values.yaml
resources:
  limits:
    memory: 1Gi  # Override: Need more memory for our workload
```

**Bad example:**
```yaml
# values.yaml (copying entire defaults)
resources:
  requests:
    memory: 256Mi
    cpu: 100m
  limits:
    memory: 512Mi
    cpu: 500m
# ... 100s more lines of defaults ...
```

### Configuration Checklist

- ✅ **Garage** - Simplified to core settings, aligned with defaults
- ✅ **Airbyte** - Using external PostgreSQL, MinIO for now (Garage in Phase 2)
- ✅ **Dagster** - Configured with TODOs for user code deployment and Garage integration
- ✅ **Trino** - Configured with Iceberg connector for Garage S3

### Important TODOs

**Garage:**
- [ ] Generate new RPC secret for production (`openssl rand -hex 32`)
- [ ] Increase `replicationMode` to `"3"` for production multi-node setup

**Airbyte:**
- [ ] Change MinIO password for production
- [ ] Phase 2: Switch from internal MinIO to Garage S3 storage

**Dagster:**
- [ ] Update user deployment image after running `dagster init`
- [ ] Change PostgreSQL password for production
- [ ] Phase 2: Enable S3ComputeLogManager to store logs in Garage

**Trino:**
- [ ] Configure S3 credentials for Garage (use Kubernetes Secret)
- [ ] Phase 3: Configure Apache Polaris REST catalog
- [ ] Phase 3: Enable authentication for Trino web UI

### Lakehouse Integration (Phase 2)

All services will use Garage as the central S3-compatible storage:

```
Airbyte → Garage/S3 (raw data, Parquet)
           ↓
        Iceberg Tables
           ↓
Dagster ← Garage/S3 (logs, artifacts)
Trino   ← Garage/S3 (query data)
```

## Secret Management

### Overview

All sensitive credentials are externalized to `secrets.yaml` files in each service directory. These files are automatically excluded from git via `.gitignore` pattern: `**/*/secrets.yaml`.

**Current Secret Management:**
- **Garage** - RPC secret auto-generated by Helm chart (most secure)
- **Airbyte** - PostgreSQL and MinIO credentials in `secrets.yaml`
- **Dagster** - PostgreSQL credentials in `secrets.yaml`

### Creating Secrets

Each `secrets.yaml` is a Kubernetes Secret manifest with base64-encoded values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-secret-name
  namespace: my-namespace
type: Opaque
data:
  # Base64 encoded values
  username: bXl1c2VybmFtZQ==
  password: bXlwYXNzd29yZA==
```

### Generating Secrets

```bash
# Generate a random password
openssl rand -base64 32

# Encode a value to base64 (for secrets.yaml)
echo -n "your-password-here" | base64

# Decode a base64 value (to verify)
echo "bXlwYXNzd29yZA==" | base64 -d
```

### Example: secrets.yaml Structure

**Airbyte** (`infrastructure/kubernetes/airbyte/secrets.yaml`):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: airbyte-db-secrets
  namespace: airbyte
type: Opaque
data:
  DATABASE_USER: <base64-encoded-username>
  DATABASE_PASSWORD: <base64-encoded-password>
---
apiVersion: v1
kind: Secret
metadata:
  name: airbyte-minio-secrets
  namespace: airbyte
type: Opaque
data:
  root-user: <base64-encoded-username>
  root-password: <base64-encoded-password>
```

**Dagster** (`infrastructure/kubernetes/dagster/secrets.yaml`):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dagster-postgresql-secret
  namespace: dagster
type: Opaque
data:
  postgresql-password: <base64-encoded-password>
```

### Updating Secrets

1. **Generate new password:**
   ```bash
   openssl rand -base64 32
   ```

2. **Encode to base64:**
   ```bash
   echo -n "your-new-password" | base64
   ```

3. **Update secrets.yaml** with new base64 value

4. **Apply to cluster:**
   ```bash
   kubectl apply -f infrastructure/kubernetes/<service>/secrets.yaml
   ```

5. **Restart pods** (if needed):
   ```bash
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
   ```

### Security Best Practices

- **Never commit secrets.yaml**: Verify with `git status` before committing
- **Use strong passwords**: Generate with `openssl rand -base64 32`
- **Rotate regularly**: Update production secrets periodically
- **Limit access**: Use Kubernetes RBAC to restrict Secret access
- **Audit**: Monitor Secret access via Kubernetes audit logs
- **Production**: Consider external secret management (HashiCorp Vault, AWS Secrets Manager, etc.)

### Verifying Secrets Are Ignored

```bash
# Check if file is ignored
git check-ignore -v infrastructure/kubernetes/*/secrets.yaml

# Ensure no secrets are tracked
git ls-files | grep secrets.yaml
# Should return nothing
```

# Updating Polaris

This guide covers updating Apache Polaris, including version upgrades, configuration changes, and RBAC updates.

## Overview

Polaris updates may involve:
- Helm chart version upgrades
- Polaris application version updates
- Configuration changes (values.yaml)
- Secret/credential updates
- RBAC and namespace updates

## Prerequisites

- Kubernetes cluster access
- Helm installed and configured
- Bootstrap credentials available (for RBAC updates)

## Updating Polaris Version

### Using Helm Upgrade

The standard way to update Polaris is using Helm:

```bash
# Update Helm repositories to get latest chart versions
helm repo update polaris

# Upgrade Polaris with existing values
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m

# Or specify a specific version
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  --version <chart-version> \
  -n lakehouse --wait --timeout 10m
```

### Verify the Update

After upgrading, verify Polaris is running correctly:

```bash
# Check pod status
kubectl get pods -n lakehouse -l app.kubernetes.io/name=polaris

# Check logs for errors
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris --tail=50

# Test connectivity
make polaris-test
```

## Updating Configuration

### Modify values.yaml

1. Edit `infrastructure/kubernetes/polaris/values.yaml` with your changes
2. Apply the changes:

```bash
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

### Common Configuration Updates

**Database Connection:**
```yaml
persistence:
  type: relational-jdbc
  relationalJdbc:
    secret:
      name: polaris-db-secret
      username: polaris
      password: <updated-password>
      jdbcUrl: jdbc:postgresql://polaris-postgresql:5432/polaris
```

**Storage Configuration:**
```yaml
storage:
  secret:
    name: polaris-storage-secret
    awsAccessKeyId: <access-key>
    awsSecretAccessKey: <secret-key>
```

**Resource Limits:**
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

## Updating Secrets/Credentials

### Database Credentials

1. Update the secret:
```bash
kubectl create secret generic polaris-db-secret \
  --from-literal=username=polaris \
  --from-literal=password=<new-password> \
  --from-literal=jdbcUrl=jdbc:postgresql://polaris-postgresql:5432/polaris \
  -n lakehouse --dry-run=client -o yaml | kubectl apply -f -
```

2. Restart Polaris to pick up new credentials:
```bash
make restart-polaris
```

### Storage Credentials

1. Update the storage secret:
```bash
kubectl create secret generic polaris-storage-secret \
  --from-literal=aws-access-key-id=<access-key> \
  --from-literal=aws-secret-access-key=<secret-key> \
  -n lakehouse --dry-run=client -o yaml | kubectl apply -f -
```

2. Restart Polaris:
```bash
make restart-polaris
```

### Bootstrap Credentials

If bootstrap credentials change, you'll need to update them in:
- `infrastructure/kubernetes/polaris/values.yaml` (if using Helm values)
- Kubernetes Secret (if using external secret)

Then restart Polaris:
```bash
make restart-polaris
```

## Updating RBAC

If you need to update RBAC (roles, privileges, namespaces) after Polaris is updated:

```bash
# Set bootstrap credentials
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"  # pragma: allowlist secret

# Run RBAC setup (idempotent - safe to run multiple times)
make setup-polaris-rbac
```

This will:
- Update principal roles
- Update catalog roles
- Grant privileges
- Create/update namespaces

**Note**: RBAC updates are idempotent - running them multiple times is safe and won't create duplicates.

## Rolling Back Changes

If an update causes issues, you can rollback:

### Rollback Helm Release

```bash
# List release history
helm history polaris -n lakehouse

# Rollback to previous version
helm rollback polaris -n lakehouse

# Or rollback to specific revision
helm rollback polaris <revision-number> -n lakehouse
```

### Rollback Configuration

If you need to revert configuration changes:

1. Restore previous `values.yaml` from git:
```bash
git checkout HEAD -- infrastructure/kubernetes/polaris/values.yaml
```

2. Apply the previous configuration:
```bash
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m
```

## Verification After Updates

After any update, verify Polaris is functioning correctly:

### 1. Check Pod Status

```bash
make polaris-status
```

Expected output:
- Pod status: `Running`
- No recent errors in events
- Recent logs show successful startup

### 2. Test Connectivity

```bash
# Set bootstrap credentials if needed
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"  # pragma: allowlist secret

make polaris-test
```

### 3. Verify RBAC

If RBAC was updated, verify principals can authenticate:

```bash
# Test with dagster_user credentials
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt

curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
  --user "${POLARIS_CLIENT_ID}:${POLARIS_CLIENT_SECRET}" \
  -d 'grant_type=client_credentials' \
  -d 'scope=PRINCIPAL_ROLE:ALL' | jq '.access_token'
```

### 4. Test Catalog Operations

```bash
# List catalogs
curl -s http://localhost:8181/api/catalog/v1/config | jq '.'

# List namespaces (requires authenticated token)
TOKEN=$(curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
  --user "${POLARIS_CLIENT_ID}:${POLARIS_CLIENT_SECRET}" \
  -d 'grant_type=client_credentials' \
  -d 'scope=PRINCIPAL_ROLE:ALL' | jq -r '.access_token')

curl -s http://localhost:8181/api/catalog/v1/lakehouse/namespaces \
  -H "Authorization: Bearer $TOKEN" | jq '.'
```

## Troubleshooting Update Issues

### Pod Not Starting After Update

**Symptoms**: Pod stuck in `Pending` or `CrashLoopBackOff`

**Solutions**:
```bash
# Check pod events
kubectl describe pod -n lakehouse -l app.kubernetes.io/name=polaris

# Check logs
kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris --tail=100

# Common issues:
# - Resource limits too low: Increase in values.yaml
# - Database connection failure: Check database secret
# - Storage credentials invalid: Verify storage secret
```

### Database Connection Errors

**Symptoms**: Logs show database connection failures

**Solutions**:
```bash
# Verify database secret exists
kubectl get secret polaris-db-secret -n lakehouse

# Test database connectivity
kubectl run -it --rm debug --image=postgres:14 --restart=Never -n lakehouse -- \
  psql -h polaris-postgresql -U polaris -d polaris -W

# Update secret if needed (see "Updating Secrets/Credentials" above)
```

### RBAC Not Working After Update

**Symptoms**: Principals cannot authenticate or access resources

**Solutions**:
```bash
# Re-run RBAC setup
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"  # pragma: allowlist secret
make setup-polaris-rbac

# Verify credentials are still valid
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
make polaris-test
```

### Configuration Not Applied

**Symptoms**: Changes to values.yaml not taking effect

**Solutions**:
```bash
# Verify Helm values are correct
helm get values polaris -n lakehouse

# Force upgrade
helm upgrade --install polaris polaris/polaris \
  -f infrastructure/kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m --force

# Restart pods to ensure new config is loaded
make restart-polaris
```

## Best Practices

1. **Test in Development First**: Always test updates in a development environment before production
2. **Backup Configuration**: Commit values.yaml changes to git before applying
3. **Gradual Updates**: Update one component at a time (version, config, secrets)
4. **Monitor After Updates**: Watch logs and metrics after updates for at least 15 minutes
5. **Document Changes**: Document any manual changes or workarounds needed
6. **Version Control**: Keep values.yaml in version control with clear commit messages

## Related Guides

- [Setting Up Polaris](setup-polaris.md) - Initial Polaris setup and RBAC configuration
- [Deploying the Cluster](deploying-the-cluster.md) - Complete cluster deployment guide

## Resources

- [Helm Upgrade Documentation](https://helm.sh/docs/helm/helm_upgrade/)
- [Apache Polaris Documentation](https://polaris.apache.org/)
- [Kubernetes Secrets Management](https://kubernetes.io/docs/concepts/configuration/secret/)

# Kubernetes Cluster Teardown Guide

This guide provides step-by-step commands to completely clean up your existing Kubernetes lakehouse platform deployment.

## Teardown Process

### Prerequisites

Before starting, ensure you have:
- `kubectl` configured and connected to your cluster
- `helm` CLI installed

## Teardown Order

Follow these steps in order to safely tear down the cluster:

### 1. Check Current State

First, verify what's currently deployed:

```bash
# List all namespaces
kubectl get namespaces

# List all Helm releases
helm list --all-namespaces

# List all persistent volume claims
kubectl get pvc --all-namespaces
```

Expected output should show: `lakehouse` namespace and various Helm releases (garage, airbyte, dagster, trino).

---

### 2. Uninstall Helm Releases

Uninstall all Helm releases in reverse dependency order:

```bash
# All services in lakehouse namespace - uninstall in reverse dependency order

# Uninstall Dagster (orchestration - depends on storage)
helm uninstall dagster -n lakehouse

# Uninstall Trino (query engine - depends on storage)
helm uninstall trino -n lakehouse

# Uninstall Airbyte (ingestion - depends on storage)
helm uninstall airbyte -n lakehouse

# Uninstall Garage (S3 storage - base layer)
helm uninstall garage -n lakehouse

# Clean up old dev instances in default namespace (if exists)
helm uninstall dagster-dev -n default 2>/dev/null || true
helm uninstall postgresql-dev -n default 2>/dev/null || true
```

**Verification:**
```bash
# Should show no releases or only system releases
helm list --all-namespaces
```

---

### 3. Delete Lakehouse Namespace

Deleting the namespace will cascade-delete all resources within it (pods, services, deployments, PVCs):

```bash
# Delete lakehouse namespace (contains all services)
kubectl delete namespace lakehouse --wait=true
```

**Warning:** This will delete all data stored in persistent volumes. If you want to preserve data, back up PVCs first.

**Verification:**
```bash
# Should only show default Kubernetes namespaces
kubectl get namespaces
```

Expected output:
```
NAME              STATUS   AGE
default           Active   XXd
kube-node-lease   Active   XXd
kube-public       Active   XXd
kube-system       Active   XXd
```

---

### 4. Clean Up Remaining Resources in Default Namespace

Check for any remaining resources from old deployments:

```bash
# List resources in default namespace
kubectl get all -n default

# If you see postgresql-dev or dagster-dev resources, delete them:
kubectl delete statefulset postgresql-dev -n default
kubectl delete deployment dagster-dev-dagster-webserver -n default
kubectl delete deployment dagster-dev-daemon -n default
kubectl delete service postgresql-dev -n default
# ... delete any other resources shown
```

---

### 5. Verify Persistent Volume Cleanup

Check if any PVCs remain:

```bash
# List all PVCs (should be empty or only show non-related PVCs)
kubectl get pvc --all-namespaces

# List all PVs (should show Released or Available status)
kubectl get pv
```

If any PVCs remain from deleted namespaces, manually delete them:

```bash
kubectl delete pvc <pvc-name> -n <namespace>
```

---

### 6. Final Verification

Run these commands to confirm complete cleanup:

```bash
# Should show no custom namespaces
kubectl get namespaces

# Should show no Helm releases (or only intentional ones)
helm list --all-namespaces

# Should show no custom PVCs
kubectl get pvc --all-namespaces

# Check for any remaining pods
kubectl get pods --all-namespaces | grep -v kube-system
```

---

## Troubleshooting

### Namespace Stuck in "Terminating" State

If a namespace won't delete:

```bash
# Check for finalizers
kubectl get namespace <namespace> -o yaml

# Force delete (use with caution)
kubectl delete namespace <namespace> --grace-period=0 --force
```

### PVC Won't Delete

If a PVC is stuck:

```bash
# Check what's using it
kubectl describe pvc <pvc-name> -n <namespace>

# Delete the pod/statefulset using it first
kubectl delete pod <pod-name> -n <namespace>

# Then delete the PVC
kubectl delete pvc <pvc-name> -n <namespace>
```

### Helm Release Won't Uninstall

If helm uninstall fails:

```bash
# List all releases including failed ones
helm list --all --all-namespaces

# Force delete the release
helm uninstall <release-name> -n <namespace> --no-hooks
```

---

## Post-Teardown

After completing teardown, you should have:
- Only default Kubernetes namespaces (default, kube-system, kube-public, kube-node-lease)
- No custom Helm releases
- No custom PVCs or PVs
- A clean slate ready for manual deployment

**Next Step:** Proceed to `SETUP_GUIDE.md` to rebuild the cluster from scratch.

---

## Quick Teardown Script (Optional)

If you want to run all commands at once (not recommended for learning):

```bash
# Uninstall Helm releases from lakehouse namespace
helm uninstall dagster -n lakehouse 2>/dev/null || true
helm uninstall trino -n lakehouse 2>/dev/null || true
helm uninstall airbyte -n lakehouse 2>/dev/null || true
helm uninstall garage -n lakehouse 2>/dev/null || true

# Clean up old dev instances
helm uninstall dagster-dev -n default 2>/dev/null || true
helm uninstall postgresql-dev -n default 2>/dev/null || true

# Delete lakehouse namespace (waits for completion)
kubectl delete namespace lakehouse --wait=true

# Verify cleanup
kubectl get namespaces
helm list --all-namespaces
kubectl get pvc --all-namespaces
```

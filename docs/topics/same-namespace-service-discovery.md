# Same-Namespace Service Discovery

This document explains how Kubernetes services communicate within the same namespace - the approach used in this lakehouse platform.

## Overview

All lakehouse services (Garage, Airbyte, Dagster, Trino, PostgreSQL) are deployed to a single `lakehouse` namespace. This simplifies service discovery and configuration.

## Why Single Namespace?

Following [Kubernetes best practices](https://www.appvia.io/blog/best-practices-for-kubernetes-namespaces):

**Services that communicate should live together**

Benefits:
- **Simplified DNS**: Use `service:port` instead of `service.namespace.svc.cluster.local:port`
- **Easier configuration**: No need to manage cross-namespace networking
- **Reduced complexity**: Less RBAC and network policy configuration
- **Better developer experience**: Simpler troubleshooting and debugging

## DNS Resolution in Same Namespace

When services are in the same namespace, Kubernetes DNS provides simplified resolution:

### Short Form (Preferred)
```
service-name:port
```

Examples:
- `garage:3900` (Garage S3 API)
- `trino:8080` (Trino query engine)
- `postgres:5432` (PostgreSQL database)

### Full DNS Form (Still Works)
```
service-name.namespace.svc.cluster.local:port
```

Examples:
- `garage.lakehouse.svc.cluster.local:3900`
- `trino.lakehouse.svc.cluster.local:8080`
- `postgres.lakehouse.svc.cluster.local:5432`

**Recommendation**: Use short form for simplicity and readability.

## Service Communication Examples

### Airbyte → Garage S3

**Configuration** ([infrastructure/kubernetes/airbyte/values.yaml](../../infrastructure/kubernetes/airbyte/values.yaml)):
```yaml
global:
  storage:
    s3:
      endpoint: http://garage:3900  # Short DNS - same namespace
      pathStyleAccess: true
```

### Trino → Garage S3

**Configuration** ([infrastructure/kubernetes/trino/values.yaml](../../infrastructure/kubernetes/trino/values.yaml)):
```yaml
additionalCatalogs:
  iceberg: |
    s3.endpoint=http://garage:3900  # Short DNS - same namespace
    s3.path-style-access=true
```

### DBT → Trino

**Configuration** ([transformations/dbt/profiles.yml](../../transformations/dbt/profiles.yml)):
```yaml
lakehouse:
  target: dev
  outputs:
    dev:
      type: trino
      host: trino  # Short DNS - same namespace
      port: 8080
```

## Testing Service Connectivity

From within a pod in the `lakehouse` namespace:

```bash
# Get a pod name
POD=$(kubectl get pods -n lakehouse -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# Test connectivity using short DNS
kubectl exec -n lakehouse $POD -- curl -I http://garage:3900
kubectl exec -n lakehouse $POD -- curl -I http://trino:8080
kubectl exec -n lakehouse $POD -- nc -zv postgres 5432
```

## Troubleshooting

### Service Not Resolving

**Check if service exists:**
```bash
kubectl get svc -n lakehouse
```

**Test DNS resolution:**
```bash
kubectl run -it --rm debug --image=busybox --restart=Never -n lakehouse -- nslookup garage
```

**Expected output:**
```
Server:    10.96.0.10
Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local

Name:      garage
Address 1: 10.x.x.x garage.lakehouse.svc.cluster.local
```

### Connection Refused

**Check if target pod is running:**
```bash
kubectl get pods -n lakehouse
```

**Check service endpoints:**
```bash
kubectl get endpoints -n lakehouse garage
```

**Check service ports:**
```bash
kubectl describe svc -n lakehouse garage
```

## When to Use Multiple Namespaces

You should create separate namespaces when:

1. **True isolation needed**: Different security boundaries (e.g., `production` vs `development`)
2. **Resource quotas required**: Need to limit CPU/memory per team or environment
3. **Different RBAC policies**: Services need different access control
4. **Minimal communication**: Services rarely or never communicate with each other

**Example**: The MLOps platform (Phase 4) uses a separate `ml-platform` namespace because ML workloads have different resource needs and security requirements than the data platform.

## Migration from Multiple Namespaces

If you previously had separate namespaces, migration is straightforward:

1. **Create single namespace**: `kubectl apply -f infrastructure/kubernetes/namespace.yaml`
2. **Update service configurations**: Replace full DNS with short form
3. **Redeploy services**: Deploy to `lakehouse` namespace
4. **Update secrets**: Change namespace in secret metadata
5. **Delete old namespaces**: Remove individual namespaces

**See**: [SETUP_GUIDE.md](../SETUP_GUIDE.md) for complete deployment instructions.

## Related Topics

- [Kubernetes Networking](kubernetes-networking.md) - Networking fundamentals
- [Kubernetes Fundamentals](kubernetes-fundamentals.md) - Core concepts
- [Service Discovery in Kubernetes](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) - Official docs

## References

- [Kubernetes Namespace Best Practices](https://www.appvia.io/blog/best-practices-for-kubernetes-namespaces)
- [Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)

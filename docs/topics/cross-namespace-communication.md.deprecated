# Cross-Namespace Communication in Kubernetes

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Kubernetes concepts and this project's architecture, please verify critical details against official Kubernetes documentation and your specific use cases.

## Overview

Cross-namespace communication enables [Pods](kubernetes-fundamentals.md) in different [namespaces](kubernetes-fundamentals.md) to communicate via [Kubernetes DNS](kubernetes-networking.md). This is essential for microservices architectures where services are logically isolated but need to interact.

In this lakehouse platform, cross-namespace communication connects all data platform components: [Airbyte](airbyte.md) in `airbyte` namespace writes to [Garage](garage.md) in `garage` namespace, [Trino](trino.md) in `trino` namespace queries Garage, and [DBT](dbt.md) jobs in [Dagster](dagster.md) connect to Trino.

## Why Cross-Namespace Communication Matters

**Service Isolation**: Each platform component (storage, ingestion, query, orchestration) runs in its own namespace for organizational clarity.

**Team Independence**: Analytics team works in `dagster` namespace, infrastructure team in `garage` namespace, without naming conflicts.

**Secure Integration**: Services discover each other automatically via DNS without hardcoded IPs or external load balancers.

**Environment Separation**: Dev, staging, and production namespaces coexist in same cluster with isolated communication patterns.

## Key Concepts

### 1. Kubernetes DNS Hierarchy

**What it is**: Every Service gets a DNS record following a predictable pattern.

**DNS Format**:
```
<service-name>.<namespace>.svc.cluster.local
```

**Components**:
- **service-name**: Name of the Service resource
- **namespace**: Namespace containing the service
- **svc**: Constant indicating this is a service
- **cluster.local**: Cluster domain (default, configurable)

**Examples in this platform**:
```bash
# Garage S3 API
garage.garage.svc.cluster.local:3900

# Trino coordinator
trino.trino.svc.cluster.local:8080

# Dagster webserver
dagster-dagster-webserver.dagster.svc.cluster.local:80

# Airbyte server
airbyte-airbyte-server-svc.airbyte.svc.cluster.local:8001

# Dagster PostgreSQL
dagster-postgresql.dagster.svc.cluster.local:5432

# Airbyte PostgreSQL
airbyte-airbyte-postgresql.airbyte.svc.cluster.local:5432
```

### 2. DNS Shorthand Rules

**Within same namespace** (short form works):
```bash
# From pod in 'garage' namespace
curl http://garage:3900  # Resolves to garage.garage.svc.cluster.local
```

**Cross-namespace** (must use FQDN or namespace-qualified):
```bash
# From pod in 'airbyte' namespace
curl http://garage.garage.svc.cluster.local:3900  # Full FQDN ✓
curl http://garage.garage:3900                    # Namespace-qualified ✓
curl http://garage:3900                           # Fails - looks in 'airbyte' namespace ✗
```

**DNS Search Path**:
When you use short name `garage`, Kubernetes searches:
1. `garage.airbyte.svc.cluster.local` (same namespace)
2. `garage.svc.cluster.local` (no namespace specified)
3. `garage.cluster.local` (cluster domain)

If not found, resolution fails. Always use FQDN for cross-namespace.

### 3. Service Types and Accessibility

**ClusterIP** (default, used in this platform):
- Accessible from **any namespace** within cluster
- Not accessible from outside cluster (no external IP)
- DNS: `<service>.<namespace>.svc.cluster.local`

**Headless Service** (ClusterIP: None):
- Used by [StatefulSets](stateful-applications.md) for stable pod DNS
- Returns pod IPs instead of service IP
- DNS: `<pod>.<service>.<namespace>.svc.cluster.local`

**NodePort**:
- Accessible from any namespace + accessible from outside cluster via node IP
- Not used in this platform (development uses port-forward instead)

**LoadBalancer**:
- Cloud-provided external load balancer
- Not used in this platform (local development)

## Communication Patterns in This Platform

### Pattern 1: Airbyte → Garage (Data Ingestion)

**Scenario**: [Airbyte](airbyte.md) writes ingested data to [Garage](garage.md) S3-compatible storage

**Configuration** (`infrastructure/kubernetes/airbyte/values.yaml`):
```yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://garage.garage.svc.cluster.local:3900
      bucketName: lakehouse
      accessKeyId: <from-garage-key-create>
      secretAccessKey: <from-garage-key-create>
```

**Flow**:
1. Airbyte pod in `airbyte` namespace resolves `garage.garage.svc.cluster.local`
2. CoreDNS returns Garage service ClusterIP (e.g., `10.96.100.50`)
3. Airbyte connects to `10.96.100.50:3900`
4. Kubernetes routes traffic to `garage-0` pod in `garage` namespace
5. Garage receives S3 API request and stores data

**Verification**:
```bash
# Test DNS resolution from Airbyte pod
AIRBYTE_POD=$(kubectl get pod -n airbyte -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n airbyte $AIRBYTE_POD -- nslookup garage.garage.svc.cluster.local

# Expected output:
# Server:    10.96.0.10
# Name:      garage.garage.svc.cluster.local
# Address 1: 10.96.100.50 garage.garage.svc.cluster.local

# Test HTTP connectivity
kubectl exec -n airbyte $AIRBYTE_POD -- curl -I http://garage.garage.svc.cluster.local:3900
# Expected: HTTP 403 Forbidden (unauthenticated S3 request)
```

### Pattern 2: Trino → Garage (Data Query)

**Scenario**: [Trino](trino.md) queries [Apache Iceberg](apache-iceberg.md) tables stored in [Garage](garage.md)

**Configuration** (`infrastructure/kubernetes/trino/values.yaml`):
```yaml
coordinator:
  additionalCatalogs:
    iceberg: |
      connector.name=iceberg
      iceberg.catalog.type=hive_metastore
      hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
      hive.s3.endpoint=http://garage.garage.svc.cluster.local:3900
      hive.s3.path-style-access=true
      hive.s3.aws-access-key=<from-garage-key-create>
      hive.s3.aws-secret-key=<from-garage-key-create>
      hive.s3.region=garage
```

**Flow**:
1. Trino coordinator pod in `trino` namespace queries Iceberg table
2. Trino resolves `garage.garage.svc.cluster.local` for S3 operations
3. Trino sends S3 API requests (GetObject, ListObjects, etc.)
4. Garage returns Parquet file data
5. Trino workers process query over data

**Verification**:
```bash
# Test from Trino pod
TRINO_POD=$(kubectl get pod -n trino -l app.kubernetes.io/component=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n trino $TRINO_POD -- curl -I http://garage.garage.svc.cluster.local:3900
# Expected: HTTP 403 or 200
```

### Pattern 3: DBT → Trino (Data Transformation)

**Scenario**: [DBT](dbt.md) (running in [Dagster](dagster.md) or locally) connects to [Trino](trino.md) to execute transformations

**Configuration - Local DBT** (`transformations/dbt/profiles.yml`):
```yaml
lakehouse:
  outputs:
    dev:
      type: trino
      host: localhost  # Via port-forward: kubectl port-forward -n trino svc/trino 8080:8080
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino
```

**Configuration - DBT in Dagster** (inside cluster):
```yaml
lakehouse:
  outputs:
    prod:
      type: trino
      host: trino.trino.svc.cluster.local  # Full FQDN for cross-namespace
      port: 8080
      database: lakehouse
      schema: analytics
      user: trino
```

**Flow (DBT in Dagster)**:
1. Dagster pod in `dagster` namespace launches DBT job
2. DBT connects to `trino.trino.svc.cluster.local:8080`
3. DBT sends SQL queries to Trino
4. Trino executes queries and returns results
5. DBT materializes models as Iceberg tables

### Pattern 4: Dagster → PostgreSQL (Metadata Storage)

**Scenario**: [Dagster](dagster.md) components connect to embedded PostgreSQL in same namespace

**Configuration** (Dagster Helm values):
```yaml
postgresql:
  enabled: true
  postgresqlUsername: dagster
  postgresqlPassword: <secret>
  postgresqlDatabase: dagster

# Dagster components connect via:
# Connection string: postgresql://dagster:<password>@dagster-postgresql.dagster.svc.cluster.local:5432/dagster
```

**Flow**:
1. Dagster webserver/daemon pods in `dagster` namespace connect to database
2. Short form works: `dagster-postgresql:5432` (same namespace)
3. Or FQDN: `dagster-postgresql.dagster.svc.cluster.local:5432`
4. PostgreSQL pod receives connection and serves metadata

**Note**: This is **not** cross-namespace (both in `dagster`), but shows DNS usage pattern.

### Pattern 5: Trino → Hive Metastore (Catalog Access)

**Scenario**: [Trino](trino.md) queries [Hive Metastore](hive-metastore.md) (or [Polaris](polaris-rest-catalog.md)) for Iceberg table metadata

**Configuration** (Trino Iceberg catalog):
```yaml
coordinator:
  additionalCatalogs:
    iceberg: |
      connector.name=iceberg
      iceberg.catalog.type=hive_metastore
      hive.metastore.uri=thrift://hive-metastore.database.svc.cluster.local:9083
```

**Flow**:
1. Trino coordinator in `trino` namespace needs table metadata
2. Trino resolves `hive-metastore.database.svc.cluster.local`
3. Connects via Thrift protocol on port 9083
4. Hive Metastore returns table schema, partition info, file locations
5. Trino uses metadata to query actual data in Garage

## DNS Testing and Verification

### Test 1: DNS Resolution

```bash
# From any pod, test if service resolves
kubectl run -it --rm dns-test --image=busybox --restart=Never -- nslookup garage.garage.svc.cluster.local

# Expected output:
# Server:    10.96.0.10
# Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local
#
# Name:      garage.garage.svc.cluster.local
# Address 1: 10.96.100.50 garage.garage.svc.cluster.local
```

### Test 2: Connectivity

```bash
# From Airbyte namespace, test Garage connectivity
kubectl run -it --rm conn-test --image=curlimages/curl --restart=Never -n airbyte -- curl -I http://garage.garage.svc.cluster.local:3900

# Expected: HTTP response (403, 200, etc.)
```

### Test 3: Cross-Namespace Matrix

Create test pods in multiple namespaces and verify communication:

```bash
# Test from each namespace to Garage
for NS in airbyte dagster trino; do
  echo "Testing from $NS namespace..."
  kubectl run -it --rm test --image=busybox --restart=Never -n $NS -- wget -O- --timeout=5 http://garage.garage.svc.cluster.local:3900 2>&1 | head -5
done
```

**Expected**: All tests succeed (HTTP 403 or 200 response)

### Test 4: Service Endpoints

```bash
# Verify service has backend pods
kubectl get endpoints garage -n garage

# Expected:
# NAME     ENDPOINTS           AGE
# garage   10.244.0.5:3900...  10m

# If ENDPOINTS is empty, service selector doesn't match any pods
```

## Troubleshooting

### DNS Resolution Fails

**Symptom**: `nslookup: can't resolve 'garage.garage.svc.cluster.local'`

**Check CoreDNS is running**:
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Expected: coredns pods in Running status
```

**Check DNS from pod**:
```bash
# View DNS config inside pod
kubectl exec -n airbyte <pod> -- cat /etc/resolv.conf

# Expected output:
# nameserver 10.96.0.10
# search airbyte.svc.cluster.local svc.cluster.local cluster.local
# options ndots:5
```

**Common issues**:
- CoreDNS pods not running
- DNS service missing: `kubectl get svc -n kube-system kube-dns`
- Typo in DNS name

**Fix**:
```bash
# Restart CoreDNS
kubectl rollout restart deployment/coredns -n kube-system
```

### Connection Refused or Timeout

**Symptom**: DNS resolves but connection fails

**Check service exists**:
```bash
kubectl get svc garage -n garage

# If not found, service wasn't created
```

**Check service has endpoints**:
```bash
kubectl get endpoints garage -n garage

# If ENDPOINTS column is empty, no pods match service selector
```

**Check target pod is running**:
```bash
kubectl get pods -n garage

# Verify pods are Running (not Pending/CrashLoopBackOff)
```

**Debug connectivity**:
```bash
# From source namespace, test connectivity
kubectl exec -n airbyte <pod> -- telnet garage.garage.svc.cluster.local 3900

# Or with curl
kubectl exec -n airbyte <pod> -- curl -v --max-time 5 http://garage.garage.svc.cluster.local:3900
```

**Common issues**:
- Wrong port number
- Service selector doesn't match pod labels
- Pod not listening on expected port
- NetworkPolicy blocking traffic (if enabled)

### Short Name Works Within Namespace But Fails Cross-Namespace

**Symptom**: `curl http://garage:3900` works from `garage` namespace but fails from `airbyte` namespace

**This is expected behavior**: Short names only resolve within same namespace.

**Fix**: Always use FQDN for cross-namespace communication:
```yaml
# Good
endpoint: http://garage.garage.svc.cluster.local:3900

# Bad (only works from garage namespace)
endpoint: http://garage:3900
```

### NetworkPolicy Blocking Traffic

**Symptom**: DNS resolves, service has endpoints, but connection times out

**Check NetworkPolicies**:
```bash
# List policies in target namespace
kubectl get networkpolicy -n garage

# If policies exist, check rules
kubectl describe networkpolicy <policy-name> -n garage
```

**NetworkPolicy example** (allows only from specific namespaces):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: garage-ingress
  namespace: garage
spec:
  podSelector:
    matchLabels:
      app: garage
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: airbyte  # Only allow from airbyte namespace
    - namespaceSelector:
        matchLabels:
          name: trino  # And trino namespace
```

**Fix**: Update NetworkPolicy to allow traffic from required namespaces, or delete policy if not needed:
```bash
kubectl delete networkpolicy garage-ingress -n garage
```

**Note**: This platform doesn't use NetworkPolicies by default (all traffic allowed).

## Integration with Other Components

- **[Kubernetes Fundamentals](kubernetes-fundamentals.md)**: Namespaces provide isolation, Services enable communication
- **[Kubernetes Networking](kubernetes-networking.md)**: DNS and service discovery underpins cross-namespace communication
- **[Garage](garage.md)**, **[Airbyte](airbyte.md)**, **[Trino](trino.md)**, **[Dagster](dagster.md)**: All services communicate via DNS

## Best Practices

### 1. Always Use Full DNS Names Cross-Namespace

**Good**:
```yaml
s3:
  endpoint: http://garage.garage.svc.cluster.local:3900
```

**Bad**:
```yaml
s3:
  endpoint: http://garage:3900  # Fails from other namespaces
```

### 2. Document Service Dependencies

In `README.md` or architecture docs, list cross-namespace dependencies:
```markdown
## Service Dependencies

- Airbyte → Garage (S3 API for data storage)
- Trino → Garage (S3 API for data query)
- Trino → Hive Metastore (Thrift for table metadata)
- DBT → Trino (SQL for transformations)
```

### 3. Test Connectivity Before Deployment

```bash
# Create test pod in source namespace
kubectl run -it --rm test --image=curlimages/curl --restart=Never -n airbyte -- \
  curl -I http://garage.garage.svc.cluster.local:3900

# Verify connection before deploying actual application
```

### 4. Use Environment Variables for Service URLs

**In Helm values**:
```yaml
env:
- name: GARAGE_ENDPOINT
  value: http://garage.garage.svc.cluster.local:3900
- name: TRINO_HOST
  value: trino.trino.svc.cluster.local
- name: TRINO_PORT
  value: "8080"
```

**Benefits**:
- Easy to change endpoints without modifying application code
- Environment-specific overrides (dev vs prod namespaces)

### 5. Monitor Cross-Namespace Traffic

**Use service mesh** (optional, not in this platform):
- Istio, Linkerd for traffic visibility
- Automatic mTLS between namespaces
- Traffic policies and rate limiting

**Or use Kubernetes NetworkPolicies** for basic access control.

## References

- [Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Service Networking](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

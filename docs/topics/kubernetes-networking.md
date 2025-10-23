# Kubernetes Networking

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Kubernetes networking concepts and this project's architecture, please verify critical details against official Kubernetes documentation and your specific use cases.

## Overview

Kubernetes networking enables [Pods](kubernetes-fundamentals.md) to communicate with each other, with Services, and with the outside world. Every pod gets its own IP address, and Services provide stable endpoints that persist across pod restarts.

In this lakehouse platform, networking is critical for service integration: [Airbyte](airbyte.md) writes to [Garage](garage.md) S3, [Trino](trino.md) queries Garage, [DBT](dbt.md) connects to Trino, and [Dagster](dagster.md) orchestrates everything. All communication happens via Kubernetes DNS without hardcoded IP addresses.

## Why Networking Matters for This Platform

**Service Discovery**: Components discover each other automatically using DNS names (e.g., `garage.garage.svc.cluster.local`) instead of IP addresses.

**Cross-Namespace Communication**: Services in different namespaces communicate seamlessly (Airbyte in `airbyte` namespace talks to Garage in `garage` namespace).

**Local Development**: Port-forwarding enables accessing cluster services from your local machine for debugging and administration.

**Decoupling**: Services reference stable DNS names, not ephemeral pod IPs. Pods can be replaced without updating configurations.

## Key Concepts

### 1. Pod Networking

**What it is**: Every pod gets a unique IP address. Containers within the same pod share the network namespace (same IP, can communicate via localhost).

**Pod IP characteristics**:
- **Cluster-scoped**: Routable from any pod in cluster
- **Ephemeral**: Changes when pod restarts
- **Not recommended**: Don't use pod IPs directly - use Services instead

**Example**:
```bash
# List pods with IPs
kubectl get pods -n garage -o wide

# Expected output:
# NAME       READY   STATUS    IP           NODE
# garage-0   1/1     Running   10.244.0.5   docker-desktop
```

**Testing pod-to-pod communication**:
```bash
# Get Garage pod IP
GARAGE_IP=$(kubectl get pod garage-0 -n garage -o jsonpath='{.status.podIP}')
echo "Garage IP: $GARAGE_IP"

# Test from another pod (Trino namespace)
TRINO_POD=$(kubectl get pod -n trino -l app.kubernetes.io/component=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n trino $TRINO_POD -- curl -I http://$GARAGE_IP:3900

# Expected: HTTP response from Garage S3 API
```

**Why not use pod IPs directly?**
- Pod restarts get new IPs (breaks connections)
- Services provide load balancing across multiple pods
- DNS is easier to remember than IPs

### 2. Services and ClusterIP

**What it is**: A [Service](kubernetes-fundamentals.md) provides a stable IP and DNS name for accessing pods. The default `ClusterIP` type creates an internal-only endpoint.

**How it works**:
1. Service gets stable ClusterIP (e.g., 10.96.100.50)
2. Kubernetes DNS maps service name → ClusterIP
3. Service load-balances traffic across backend pods (selected by labels)

**Example - Garage Service**:
```bash
# View Garage service
kubectl get svc -n garage garage

# Expected output:
# NAME     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
# garage   ClusterIP   10.96.100.50    <none>        3900/TCP,3902/TCP   5m
```

**Service selects pods via labels**:
```yaml
# Service definition
apiVersion: v1
kind: Service
metadata:
  name: garage
  namespace: garage
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: garage  # Select pods with this label
  ports:
  - name: s3-api
    port: 3900
    targetPort: 3900
  - name: admin-api
    port: 3902
    targetPort: 3902
```

**Key points**:
- **ClusterIP**: Stable IP address (10.96.100.50) that doesn't change
- **selector**: Matches pods with label `app.kubernetes.io/name=garage`
- **port**: Service port (what clients use)
- **targetPort**: Container port (what pod listens on)

**Check service endpoints** (backend pods):
```bash
kubectl get endpoints garage -n garage

# Expected output:
# NAME     ENDPOINTS                          AGE
# garage   10.244.0.5:3900,10.244.0.5:3902    5m
```

**Endpoints** show actual pod IPs backing the service. If no endpoints, no pods match the service selector.

### 3. DNS and Service Discovery

**What it is**: Kubernetes runs an internal DNS server (CoreDNS) that automatically creates DNS records for Services.

**DNS name format**:
```
<service-name>.<namespace>.svc.cluster.local
```

**In this platform**:
- `garage.garage.svc.cluster.local` → Garage S3 API
- `trino.trino.svc.cluster.local` → Trino coordinator
- `dagster-dagster-webserver.dagster.svc.cluster.local` → Dagster UI
- `airbyte-airbyte-server-svc.airbyte.svc.cluster.local` → Airbyte API

**Shorthand within same namespace**:
- From `garage` namespace: `garage` (short form) or `garage.garage.svc.cluster.local` (FQDN)
- From `airbyte` namespace: Must use `garage.garage.svc.cluster.local` (cross-namespace)

**Example - Test DNS Resolution**:
```bash
# Run debug pod to test DNS
kubectl run -it --rm debug --image=busybox --restart=Never -n airbyte -- nslookup garage.garage.svc.cluster.local

# Expected output:
# Server:    10.96.0.10
# Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local
#
# Name:      garage.garage.svc.cluster.local
# Address 1: 10.96.100.50 garage.garage.svc.cluster.local
```

**What this shows**:
- DNS server: 10.96.0.10 (CoreDNS service)
- Resolved IP: 10.96.100.50 (Garage service ClusterIP)

**Test HTTP connectivity**:
```bash
# From Airbyte pod, access Garage S3 API
kubectl exec -n airbyte <airbyte-pod> -- curl -I http://garage.garage.svc.cluster.local:3900

# Expected: HTTP 403 or 200 response
```

See [Cross-Namespace Communication](cross-namespace-communication.md) for detailed patterns.

### 4. Port-Forwarding

**What it is**: Creates a tunnel from your local machine to a pod or service in the cluster. Essential for accessing UIs and debugging.

**Use cases**:
- Access Airbyte UI from browser (http://localhost:8080)
- Access Dagster UI from browser (http://localhost:3000)
- Access Trino UI from browser (http://localhost:8081)
- Test S3 API from local AWS CLI

**Basic syntax**:
```bash
kubectl port-forward -n <namespace> <resource-type>/<resource-name> <local-port>:<remote-port>
```

**Example - Forward Airbyte UI**:
```bash
# Forward Airbyte service port 8001 → localhost:8080
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001

# Output:
# Forwarding from 127.0.0.1:8080 -> 8001
# Forwarding from [::1]:8080 -> 8001
# Handling connection for 8080
```

**Now access** in browser: http://localhost:8080

**Port-forward characteristics**:
- **Blocks terminal**: Runs in foreground (Ctrl+C to stop)
- **Local only**: Only accessible from your machine
- **Single connection**: One port-forward per local port
- **Not for production**: Use Ingress or LoadBalancer for production access

**Multiple port-forwards** (use separate terminals):
```bash
# Terminal 1: Airbyte UI
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001

# Terminal 2: Dagster UI
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80

# Terminal 3: Trino UI (avoid 8080 conflict with Airbyte)
kubectl port-forward -n trino svc/trino 8081:8080

# Terminal 4: Garage S3 API
kubectl port-forward -n garage svc/garage 3900:3900
```

**Port-forward to pod instead of service**:
```bash
# Useful for debugging specific pod
kubectl port-forward -n garage pod/garage-0 3900:3900
```

**Background port-forward** (Linux/Mac):
```bash
# Run in background
kubectl port-forward -n garage svc/garage 3900:3900 &
PF_PID=$!

# Do work...
curl http://localhost:3900

# Kill background port-forward
kill $PF_PID
```

### 5. Headless Services

**What it is**: A service with `ClusterIP: None`. Instead of load-balancing, DNS returns all pod IPs directly.

**Why it exists**: [StatefulSets](stateful-applications.md) need stable, predictable pod DNS names.

**Example - Garage Headless Service**:
```bash
kubectl get svc -n garage garage-headless

# Expected output:
# NAME              TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)             AGE
# garage-headless   ClusterIP   None         <none>        3900/TCP,3902/TCP   5m
```

**DNS behavior with headless service**:
```bash
# Regular service → Returns ClusterIP
nslookup garage.garage.svc.cluster.local
# Answer: 10.96.100.50

# Headless service → Returns all pod IPs
nslookup garage-headless.garage.svc.cluster.local
# Answer: 10.244.0.5

# Individual pod DNS (only with headless service)
nslookup garage-0.garage-headless.garage.svc.cluster.local
# Answer: 10.244.0.5
```

**Pattern**: StatefulSet creates pods `garage-0`, `garage-1`, `garage-2`
**DNS names**:
- `garage-0.garage-headless.garage.svc.cluster.local` → Pod 0
- `garage-1.garage-headless.garage.svc.cluster.local` → Pod 1
- `garage-2.garage-headless.garage.svc.cluster.local` → Pod 2

**Why this matters**: Distributed systems like Garage need to address specific nodes (e.g., "connect to replica 0 for reads").

### 6. Network Policies

**What it is**: Firewall rules for pod-to-pod traffic. By default, all pods can reach all pods (no restrictions).

**Example - Restrict Garage Access**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: garage-ingress
  namespace: garage
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: garage
  policyTypes:
  - Ingress
  ingress:
  # Allow from Airbyte namespace
  - from:
    - namespaceSelector:
        matchLabels:
          name: airbyte
    ports:
    - protocol: TCP
      port: 3900
  # Allow from Trino namespace
  - from:
    - namespaceSelector:
        matchLabels:
          name: trino
    ports:
    - protocol: TCP
      port: 3900
```

**Note**: This project doesn't use NetworkPolicies (all pods can communicate freely) for simplicity. Add them for production security.

## Communication Patterns in This Platform

### Pattern 1: Cross-Namespace Service Access

**Scenario**: [Airbyte](airbyte.md) (in `airbyte` namespace) writes data to [Garage](garage.md) (in `garage` namespace)

**Configuration in Airbyte**:
```yaml
# infrastructure/kubernetes/airbyte/values.yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://garage.garage.svc.cluster.local:3900
      bucketName: lakehouse
      accessKeyId: <from-garage-key-create>
      secretAccessKey: <from-garage-key-create>
```

**What happens**:
1. Airbyte pod resolves `garage.garage.svc.cluster.local` via DNS → `10.96.100.50`
2. Connects to ClusterIP `10.96.100.50:3900`
3. Kubernetes routes traffic to `garage-0` pod (10.244.0.5:3900)

**Verification**:
```bash
# From Airbyte pod, test connectivity
AIRBYTE_POD=$(kubectl get pod -n airbyte -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n airbyte $AIRBYTE_POD -- curl -I http://garage.garage.svc.cluster.local:3900

# Expected: HTTP 403 Forbidden (S3 API rejects unauthenticated request)
```

### Pattern 2: DBT Connects to Trino

**Scenario**: [DBT](dbt.md) (running locally or in Dagster) connects to [Trino](trino.md)

**DBT profiles.yml** (local development with port-forward):
```yaml
lakehouse:
  outputs:
    dev:
      type: trino
      host: localhost  # Via port-forward
      port: 8080
      database: lakehouse
      schema: analytics
```

**DBT profiles.yml** (running inside cluster):
```yaml
lakehouse:
  outputs:
    prod:
      type: trino
      host: trino.trino.svc.cluster.local  # Full DNS name
      port: 8080
      database: lakehouse
      schema: analytics
```

### Pattern 3: Trino Queries Garage S3

**Scenario**: [Trino](trino.md) queries Iceberg tables stored in [Garage](garage.md) S3

**Trino catalog configuration**:
```yaml
# infrastructure/kubernetes/trino/values.yaml
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
```

**What happens**:
1. Trino coordinator pod resolves `garage.garage.svc.cluster.local` → `10.96.100.50`
2. Sends S3 API requests (ListObjects, GetObject, etc.)
3. Garage returns Parquet files
4. Trino workers read and process data in parallel

## Troubleshooting

### Cannot Resolve DNS Name

**Symptom**: `nslookup: can't resolve 'garage.garage.svc.cluster.local'`

**Check CoreDNS is running**:
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Expected: CoreDNS pods in Running status
```

**Check DNS configuration**:
```bash
# View pod DNS config
kubectl exec -n garage garage-0 -- cat /etc/resolv.conf

# Expected output:
# nameserver 10.96.0.10
# search garage.svc.cluster.local svc.cluster.local cluster.local
# options ndots:5
```

**Test DNS from pod**:
```bash
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup garage.garage.svc.cluster.local
```

**Common causes**:
- CoreDNS pods not running
- Typo in DNS name (missing namespace or `.svc.cluster.local`)
- Service doesn't exist in that namespace

### Service Has No Endpoints

**Symptom**: Service exists but `curl` times out or refused

**Check endpoints**:
```bash
kubectl get endpoints garage -n garage

# If ENDPOINTS column is empty:
# NAME     ENDPOINTS   AGE
# garage   <none>      5m
```

**Reason**: Service selector doesn't match any pod labels

**Debug**:
```bash
# View service selector
kubectl get svc garage -n garage -o jsonpath='{.spec.selector}'

# Output: {"app.kubernetes.io/name":"garage"}

# Check pod labels
kubectl get pods -n garage --show-labels

# Verify pod has matching label "app.kubernetes.io/name=garage"
```

**Fix**: Update service selector or pod labels to match

### Port-Forward Connection Refused

**Symptom**: `error: unable to forward port... connection refused`

**Common causes**:
1. **Pod not running**: Check `kubectl get pods -n <namespace>`
2. **Wrong port**: Verify container listens on that port
3. **Service doesn't exist**: Check `kubectl get svc -n <namespace>`

**Debug**:
```bash
# Check pod is running
kubectl get pod <pod-name> -n <namespace>

# Check pod logs for startup errors
kubectl logs <pod-name> -n <namespace>

# Verify port is listening inside container
kubectl exec -n <namespace> <pod-name> -- netstat -tlnp
```

### Cross-Namespace Connection Fails

**Symptom**: Can connect within namespace but not across namespaces

**Check DNS resolution**:
```bash
# From source namespace, test DNS
kubectl exec -n airbyte <pod> -- nslookup garage.garage.svc.cluster.local
```

**Check service exists in target namespace**:
```bash
kubectl get svc -n garage
```

**Check NetworkPolicies** (if enabled):
```bash
kubectl get networkpolicy -n garage
kubectl describe networkpolicy <policy-name> -n garage
```

**Common causes**:
- Typo in DNS name (forgot namespace: `garage` vs `garage.garage.svc.cluster.local`)
- NetworkPolicy blocking traffic
- Service not exposed on expected port

## Integration with Other Components

- **[Kubernetes Fundamentals](kubernetes-fundamentals.md)**: Services connect Pods, Namespaces provide isolation
- **[Cross-Namespace Communication](cross-namespace-communication.md)**: Detailed patterns for service discovery
- **[Helm Package Management](helm-package-management.md)**: Helm charts define Services
- **[Garage](garage.md)**, **[Airbyte](airbyte.md)**, **[Trino](trino.md)**, **[Dagster](dagster.md)**: All rely on DNS-based service discovery

## Best Practices

### 1. Always Use DNS Names, Not IPs

**Good**:
```yaml
endpoint: http://garage.garage.svc.cluster.local:3900
```

**Bad**:
```yaml
endpoint: http://10.244.0.5:3900  # Pod IP changes on restart!
```

### 2. Use Full DNS Names for Cross-Namespace

**Good** (explicit, works from any namespace):
```yaml
host: trino.trino.svc.cluster.local
```

**Acceptable** (within same namespace only):
```yaml
host: trino
```

### 3. Verify Connectivity Before Deployment

```bash
# Test from client namespace
kubectl run -it --rm debug --image=busybox --restart=Never -n airbyte -- wget -O- http://garage.garage.svc.cluster.local:3900
```

### 4. Use Port-Forward for Local Dev Only

**Good** (local development):
```bash
kubectl port-forward -n trino svc/trino 8080:8080
```

**Better** (production):
- Use Ingress controller for HTTP services
- Use LoadBalancer for external access

### 5. Check Endpoints After Service Changes

```bash
# Always verify service has backend pods
kubectl get endpoints <service> -n <namespace>
```

## References

- [Official Kubernetes Networking](https://kubernetes.io/docs/concepts/services-networking/)
- [Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Service Types](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

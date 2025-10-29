# Stateful Applications in Kubernetes

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Kubernetes concepts and this project's architecture, please verify critical details against official Kubernetes documentation and your specific use cases.

## Overview

Stateful applications are programs that maintain persistent data or require stable identities across restarts. Unlike stateless applications (web servers, APIs), stateful apps like databases and distributed storage systems need predictable pod names, stable network identities, and persistent storage.

[Kubernetes](kubernetes-fundamentals.md) provides **StatefulSets** to manage stateful applications. StatefulSets ensure ordered deployment, stable pod naming, and dedicated [persistent storage](kubernetes-storage.md) per replica.

In this lakehouse platform, stateful applications include: [Garage](garage.md) (distributed S3 storage), and [PostgreSQL](postgresql.md) databases for [Airbyte](airbyte.md) and [Dagster](dagster.md) metadata.

## Why StatefulSets Matter for This Platform

**Stable Identity**: [Garage](garage.md) cluster nodes need stable names (`garage-0`, `garage-1`) for peer discovery and data replication.

**Persistent Storage**: Each [PostgreSQL](postgresql.md) replica needs its own dedicated storage that persists across restarts.

**Ordered Operations**: Database initialization requires sequential startup - replica 0 must start before replica 1.

**Predictable Scaling**: When scaling Garage from 1 to 3 nodes, pods are created in order (0 → 1 → 2) and terminated in reverse (2 → 1 → 0).

## Key Concepts

### 1. StatefulSet vs Deployment

**Deployment** (stateless applications):
- Random pod names: `webapp-abc123`, `webapp-def456`
- Any pod can be deleted/recreated without affecting application
- All replicas are identical and interchangeable
- Shared or no persistent storage

**StatefulSet** (stateful applications):
- Ordered pod names: `postgres-0`, `postgres-1`, `postgres-2`
- Each pod has unique identity and dedicated storage
- Order matters: Pod 0 often has special role (primary database)
- Each replica gets its own PVC

**Comparison Table**:

| Feature | Deployment | StatefulSet |
|---------|------------|-------------|
| Pod naming | Random (`app-abc123`) | Ordered (`app-0`, `app-1`) |
| Network identity | Random pod IP | Stable DNS per pod |
| Storage | Shared or ephemeral | Dedicated PVC per pod |
| Startup order | Parallel (all at once) | Sequential (0 → 1 → 2) |
| Scaling up | Create all new pods in parallel | Create pods sequentially |
| Scaling down | Delete random pods | Delete highest ordinal first |
| Use case | Web apps, APIs, workers | Databases, storage clusters |

### 2. Stable Pod Identity

**What it is**: Each StatefulSet pod gets a deterministic name based on ordinal index: `<statefulset-name>-<ordinal>`

**Example - Garage StatefulSet with 3 replicas**:
```bash
kubectl get pods -n garage

# Expected output:
# NAME       READY   STATUS    RESTARTS   AGE
# garage-0   1/1     Running   0          5m
# garage-1   1/1     Running   0          4m
# garage-2   1/1     Running   0          3m
```

**Stable characteristics**:
- **Name persists**: If `garage-0` is deleted, Kubernetes creates new pod also named `garage-0`
- **Ordinal preserved**: Pod indices never change (no `garage-3` until you scale beyond 3)
- **Hostname matches pod name**: Inside pod, `hostname` command returns `garage-0`

**Why this matters**:
```bash
# Garage configuration references specific nodes by name
garage-0.garage-headless.garage.svc.cluster.local  # Always refers to replica 0
garage-1.garage-headless.garage.svc.cluster.local  # Always refers to replica 1
```

Distributed systems use these stable names for:
- Leader election (e.g., "node-0 is always the primary")
- Data partitioning (e.g., "replica 0 handles keys A-M")
- Peer discovery (e.g., "connect to all nodes node-0 through node-N")

### 3. Stable Network Identity

**What it is**: Each StatefulSet pod gets a stable DNS name via [headless service](kubernetes-networking.md).

**DNS pattern**:
```
<pod-name>.<headless-service-name>.<namespace>.svc.cluster.local
```

**Example - Garage with Headless Service**:
```bash
# Headless service (ClusterIP: None)
kubectl get svc -n lakehouse garage-headless

# NAME              TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)
# garage-headless   ClusterIP   None         <none>        3900/TCP,3902/TCP
```

**Pod DNS names**:
```bash
garage-0.garage-headless.garage.svc.cluster.local  # → 10.244.0.5
garage-1.garage-headless.garage.svc.cluster.local  # → 10.244.0.6
garage-2.garage-headless.garage.svc.cluster.local  # → 10.244.0.7
```

**Test DNS resolution**:
```bash
# From any pod in cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup garage-0.garage-headless.garage.svc.cluster.local

# Expected output:
# Server:    10.96.0.10
# Address 1: 10.96.0.10 kube-dns.kube-system.svc.cluster.local
#
# Name:      garage-0.garage-headless.garage.svc.cluster.local
# Address 1: 10.244.0.5 garage-0.garage.svc.cluster.local
```

**Why headless service?**
- Regular service load-balances to random pod
- Headless service allows addressing specific pod by ordinal
- Essential for leader-follower databases (connect to primary only)

### 4. Persistent Storage per Replica

**What it is**: StatefulSets use `volumeClaimTemplates` to create dedicated [PVC](kubernetes-storage.md) for each replica.

**Example - Garage StatefulSet with Storage**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
  namespace: garage
spec:
  serviceName: garage-headless
  replicas: 3
  selector:
    matchLabels:
      app: garage
  template:
    metadata:
      labels:
        app: garage
    spec:
      containers:
      - name: garage
        image: dxflrs/garage:v0.8.0
        volumeMounts:
        - name: data
          mountPath: /data
        - name: meta
          mountPath: /meta
  volumeClaimTemplates:  # Create PVC per replica
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: hostpath
      resources:
        requests:
          storage: 10Gi
  - metadata:
      name: meta
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: hostpath
      resources:
        requests:
          storage: 1Gi
```

**Result - 3 replicas create 6 PVCs**:
```bash
kubectl get pvc -n garage

# NAME            STATUS   VOLUME          CAPACITY   ACCESS MODES   STORAGECLASS
# data-garage-0   Bound    pvc-123abc...   10Gi       RWO            hostpath
# meta-garage-0   Bound    pvc-456def...   1Gi        RWO            hostpath
# data-garage-1   Bound    pvc-789ghi...   10Gi       RWO            hostpath
# meta-garage-1   Bound    pvc-012jkl...   1Gi        RWO            hostpath
# data-garage-2   Bound    pvc-345mno...   10Gi       RWO            hostpath
# meta-garage-2   Bound    pvc-678pqr...   1Gi        RWO            hostpath
```

**PVC naming pattern**: `<volume-claim-template-name>-<statefulset-name>-<ordinal>`

**Storage persistence**:
- Pod `garage-0` always mounts `data-garage-0` and `meta-garage-0`
- If pod deleted and recreated, same PVCs are reattached
- Data survives pod restarts and deletions

### 5. Ordered Deployment and Scaling

**What it is**: StatefulSets create and delete pods sequentially, not in parallel.

**Scale up** (1 → 3 replicas):
```bash
kubectl scale statefulset garage -n lakehouse --replicas=3

# Order of operations:
# 1. Create garage-1
# 2. Wait for garage-1 to be Running and Ready
# 3. Create garage-2
# 4. Wait for garage-2 to be Running and Ready
# Complete
```

**Watch scaling in progress**:
```bash
kubectl get pods -n lakehouse --watch

# Output:
# NAME       READY   STATUS              RESTARTS   AGE
# garage-0   1/1     Running             0          10m
# garage-1   0/1     ContainerCreating   0          1s   ← Creating
# garage-1   1/1     Running             0          5s   ← Ready
# garage-2   0/1     ContainerCreating   0          1s   ← Now creating garage-2
# garage-2   1/1     Running             0          5s   ← Ready
```

**Scale down** (3 → 1 replicas):
```bash
kubectl scale statefulset garage -n lakehouse --replicas=1

# Order of operations:
# 1. Delete garage-2 (highest ordinal first)
# 2. Wait for garage-2 to fully terminate
# 3. Delete garage-1
# 4. Wait for garage-1 to fully terminate
# Complete (garage-0 remains)
```

**Why ordered operations?**
- **Database initialization**: Primary (replica 0) must start before secondaries
- **Data consistency**: Distributed systems need controlled shutdown to avoid data loss
- **Dependency chains**: Some replicas depend on others being ready first

**Parallel vs Sequential**:
```bash
# Deployment: All replicas created simultaneously
kubectl scale deployment webapp --replicas=10
# → Creates 10 pods in parallel

# StatefulSet: Replicas created one at a time
kubectl scale statefulset postgres --replicas=10
# → Creates postgres-1, waits, postgres-2, waits, etc.
```

## StatefulSet Patterns in This Platform

### Pattern 1: Single-Replica Database

**Used by**: [PostgreSQL](postgresql.md) for [Airbyte](airbyte.md) and [Dagster](dagster.md) (embedded databases)

**Why**: Simple setup for development/learning - no replication complexity

**Example - Dagster PostgreSQL**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: dagster-postgresql
  namespace: dagster
spec:
  serviceName: dagster-postgresql-headless
  replicas: 1  # Single database instance
  template:
    spec:
      containers:
      - name: postgresql
        image: postgres:14
        env:
        - name: POSTGRES_DB
          value: dagster
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: dagster-postgresql
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: dagster-postgresql
              key: password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 8Gi
```

**Result**:
```bash
kubectl get all -n lakehouse -l app=postgresql

# pod/dagster-postgresql-0
# service/dagster-postgresql (ClusterIP)
# service/dagster-postgresql-headless (ClusterIP: None)
# statefulset.apps/dagster-postgresql (1/1)
# pvc/data-dagster-postgresql-0 (8Gi)
```

**Access**:
```bash
# From within cluster
postgresql://user:pass@dagster-postgresql.dagster.svc.cluster.local:5432/dagster

# Or target specific replica (same result with 1 replica)
postgresql://user:pass@dagster-postgresql-0.dagster-postgresql-headless.dagster.svc.cluster.local:5432/dagster
```

### Pattern 2: Distributed Storage Cluster

**Used by**: [Garage](garage.md) (distributed S3-compatible storage)

**Why**: Horizontal scaling for capacity and throughput

**Example - Garage Cluster**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
  namespace: garage
spec:
  serviceName: garage-headless
  replicas: 3  # 3-node cluster
  template:
    spec:
      containers:
      - name: garage
        image: dxflrs/garage:v0.8.0
        env:
        - name: GARAGE_RPC_SECRET
          valueFrom:
            secretKeyRef:
              name: garage-rpc-secret
              key: secret
        ports:
        - name: s3-api
          containerPort: 3900
        - name: admin-api
          containerPort: 3902
        - name: rpc
          containerPort: 3901
        volumeMounts:
        - name: data
          mountPath: /data
        - name: meta
          mountPath: /meta
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi
  - metadata:
      name: meta
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 1Gi
```

**Result**:
```bash
kubectl get all -n garage

# pod/garage-0
# pod/garage-1
# pod/garage-2
# service/garage (ClusterIP - load-balanced S3 API)
# service/garage-headless (ClusterIP: None - peer discovery)
# statefulset.apps/garage (3/3)
# pvc/data-garage-0, pvc/meta-garage-0
# pvc/data-garage-1, pvc/meta-garage-1
# pvc/data-garage-2, pvc/meta-garage-2
```

**Initialization** (required after deployment):
```bash
# Assign storage roles to all 3 nodes
for i in 0 1 2; do
  NODE_ID=$(kubectl exec -n lakehouse garage-$i -- /garage status | grep garage-$i | awk '{print $1}')
  kubectl exec -n lakehouse garage-0 -- /garage layout assign -z dc1 -c 10G $NODE_ID
done

# Apply layout
kubectl exec -n lakehouse garage-0 -- /garage layout apply --version 1
```

## Troubleshooting

### Pod Stuck in Pending During Scale-Up

**Symptom**: New pod never starts when scaling up

```bash
kubectl get pods -n garage

# NAME       READY   STATUS    RESTARTS   AGE
# garage-0   1/1     Running   0          10m
# garage-1   0/1     Pending   0          5m   ← Stuck!
```

**Check**:
```bash
kubectl describe pod garage-1 -n garage

# Events:
# Warning  FailedScheduling  ...  0/1 nodes are available: 1 Insufficient storage
```

**Common causes**:
1. **PVC not binding**: Check `kubectl get pvc -n garage`
2. **Insufficient storage**: Node out of disk space
3. **Previous pod not ready**: StatefulSet waits for `garage-0` to be Ready before creating `garage-1`
4. **Pod disruption budget**: Too many pods disrupted

**Debug**:
```bash
# Check PVC status
kubectl get pvc -n garage

# Check previous pod is Ready
kubectl get pod garage-0 -n garage

# Check node resources
kubectl top nodes
kubectl describe node
```

### StatefulSet Stuck During Deletion

**Symptom**: `kubectl delete statefulset garage` hangs forever

**Common cause**: Pod termination grace period too long or pod refusing to terminate

**Force delete**:
```bash
# Delete StatefulSet without waiting for pods to terminate
kubectl delete statefulset garage -n lakehouse --cascade=orphan

# Then manually delete pods
kubectl delete pod garage-0 garage-1 garage-2 -n lakehouse --force --grace-period=0
```

**Warning**: Force deletion can cause data corruption. Use only when necessary.

### PVC Not Deleted After Scale-Down

**Symptom**: Scaled from 3 → 1 replicas, but PVCs for replicas 1 and 2 still exist

```bash
kubectl get pvc -n garage

# NAME            STATUS   VOLUME          CAPACITY
# data-garage-0   Bound    pvc-123abc...   10Gi   ← In use
# data-garage-1   Bound    pvc-456def...   10Gi   ← Not deleted!
# data-garage-2   Bound    pvc-789ghi...   10Gi   ← Not deleted!
```

**This is expected behavior**: Kubernetes **never** automatically deletes StatefulSet PVCs to prevent accidental data loss.

**Manual cleanup** (if data not needed):
```bash
kubectl delete pvc data-garage-1 meta-garage-1 -n garage
kubectl delete pvc data-garage-2 meta-garage-2 -n garage
```

**Reuse PVCs** (if scaling back up):
```bash
# Scale back to 3
kubectl scale statefulset garage -n lakehouse --replicas=3

# garage-1 and garage-2 recreated and reattach to existing PVCs
# Data from previous replicas is still there!
```

### Pods Created Out of Order

**Symptom**: `garage-2` created before `garage-1` is Ready

**This should never happen** with StatefulSets (ordered guarantee). If it does:

**Possible causes**:
1. Using Deployment instead of StatefulSet (check `kubectl get deployment -n garage`)
2. StatefulSet `podManagementPolicy` set to `Parallel` (default is `OrderedReady`)

**Fix**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
spec:
  podManagementPolicy: OrderedReady  # Ensure sequential creation
```

## Integration with Other Components

- **[Kubernetes Fundamentals](kubernetes-fundamentals.md)**: StatefulSets are a type of workload controller
- **[Kubernetes Storage](kubernetes-storage.md)**: StatefulSets use VolumeClaimTemplates to create PVCs
- **[Kubernetes Networking](kubernetes-networking.md)**: Headless Services provide stable DNS for StatefulSet pods
- **[Garage](garage.md)**: Deployed as StatefulSet with 1+ replicas
- **[PostgreSQL](postgresql.md)**: Deployed as StatefulSet with 1 replica (embedded in Airbyte/Dagster)
- **[Helm Package Management](helm-package-management.md)**: Helm charts define StatefulSet resources

## Best Practices

### 1. Always Use Headless Service with StatefulSet

**Required** for stable pod DNS names:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: garage-headless
spec:
  clusterIP: None  # Headless
  selector:
    app: garage
  ports:
  - port: 3900
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
spec:
  serviceName: garage-headless  # Reference headless service
```

### 2. Set Resource Requests and Limits

Prevents resource starvation during scaling:
```yaml
containers:
- name: postgres
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
```

### 3. Use Liveness and Readiness Probes

Ensures StatefulSet doesn't proceed to next replica until current one is healthy:
```yaml
containers:
- name: garage
  livenessProbe:
    httpGet:
      path: /health
      port: 3902
    initialDelaySeconds: 30
    periodSeconds: 10
  readinessProbe:
    httpGet:
      path: /health
      port: 3902
    initialDelaySeconds: 10
    periodSeconds: 5
```

### 4. Plan for Storage Growth

Size PVCs with growth in mind (expanding PVCs can be complex):
```yaml
volumeClaimTemplates:
- metadata:
    name: data
  spec:
    resources:
      requests:
        storage: 100Gi  # Oversize for future growth
```

### 5. Test Scale-Down Before Production

```bash
# Test data survives scale-down and scale-up
kubectl scale statefulset garage -n lakehouse --replicas=3
# Wait for all pods ready
kubectl scale statefulset garage -n lakehouse --replicas=1
# Wait for scale-down
kubectl scale statefulset garage -n lakehouse --replicas=3
# Verify data still intact
```

## References

- [Official Kubernetes StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [StatefulSet Basics Tutorial](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/)
- [Running Distributed Systems (Designing Distributed Systems)](https://www.oreilly.com/library/view/designing-distributed-systems/9781491983638/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

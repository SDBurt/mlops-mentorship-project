# Kubernetes Fundamentals

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Kubernetes concepts and this project's architecture, please verify critical details against official Kubernetes documentation and your specific use cases.

## Overview

Kubernetes is an open-source container orchestration platform that automates the deployment, scaling, and management of containerized applications. It provides a declarative framework for managing distributed systems resiliently.

In this lakehouse platform, Kubernetes orchestrates all core services: storage ([Garage](garage.md)), ingestion ([Airbyte](airbyte.md)), orchestration ([Dagster](dagster.md)), and query engines ([Trino](trino.md)). Understanding Kubernetes fundamentals is essential for deploying, debugging, and operating the entire platform.

## Why Kubernetes Matters for This Platform

**Infrastructure Portability**: Deploy the same lakehouse stack on local development (Docker Desktop), cloud providers (EKS, GKE, AKS), or on-premises clusters without changing application code.

**Service Isolation**: Each data platform component (Garage, Airbyte, Dagster, Trino) runs in its own namespace, preventing resource conflicts and enabling independent scaling.

**Self-Healing**: Kubernetes automatically restarts failed containers, replaces pods on node failures, and maintains desired replica counts.

**Declarative Configuration**: Define desired state in YAML files. Kubernetes continuously reconciles actual state to match your declarations.

## Key Concepts

### 1. Namespace

**What it is**: A virtual cluster within your physical Kubernetes cluster. Provides logical isolation and resource organization.

**Why it matters**: In this project, each service has its own namespace (`garage`, `airbyte`, `dagster`, `trino`) to:
- Prevent name conflicts (multiple services can have a `postgres` pod in different namespaces)
- Enable team autonomy (analytics team works in `dagster` without affecting infrastructure team's `garage` namespace)
- Apply resource quotas per namespace
- Simplify access control (RBAC policies per namespace)

**Example**:
```bash
# Create namespace
kubectl apply -f infrastructure/kubernetes/namespaces/garage.yaml

# List all namespaces
kubectl get namespaces

# View resources in specific namespace
kubectl get all -n garage
```

**Key commands**:
```bash
kubectl get namespaces                    # List all namespaces
kubectl describe namespace <name>         # Details and resource quotas
kubectl config set-context --current --namespace=garage  # Set default namespace
```

### 2. Pod

**What it is**: The smallest deployable unit in Kubernetes. Contains one or more containers that share network and storage resources.

**Why it matters**: Every application runs inside a pod. Pods are:
- **Ephemeral**: Can be created, destroyed, and rescheduled on different nodes
- **Co-located**: Containers in the same pod run on the same node
- **Shared context**: Containers share localhost network and can share volumes

**In this platform**:
- `garage-0`: Single-container pod running Garage storage
- `airbyte-server`: Single-container pod running Airbyte API
- `dagster-postgresql-0`: Single-container pod running PostgreSQL

**Example**:
```bash
# List pods in namespace
kubectl get pods -n garage

# Expected output:
# NAME       READY   STATUS    RESTARTS   AGE
# garage-0   1/1     Running   0          5m
```

**Understanding pod status**:
- **READY "1/1"**: 1 container running out of 1 total
- **STATUS "Running"**: Pod successfully started and running
- **STATUS "Pending"**: Waiting for resources (node capacity, PVC binding)
- **STATUS "CrashLoopBackOff"**: Container repeatedly crashing
- **STATUS "ImagePullBackOff"**: Cannot download container image

**Key commands**:
```bash
kubectl get pods -n <namespace>                # List pods
kubectl describe pod <pod-name> -n <namespace> # Detailed info and events
kubectl logs <pod-name> -n <namespace>         # View container logs
kubectl logs <pod-name> -n <namespace> --tail=100 -f  # Follow last 100 lines
kubectl exec -it <pod-name> -n <namespace> -- /bin/bash  # Shell into container
```

### 3. Service

**What it is**: A stable network endpoint that provides access to a set of pods. Services abstract away pod IP addresses (which change when pods restart).

**Why it matters**: Services enable [cross-namespace communication](cross-namespace-communication.md) via DNS. Without services, you'd need to track changing pod IPs manually.

**Service Types**:
- **ClusterIP** (default): Internal-only access within cluster
- **NodePort**: Exposes service on each node's IP at a static port
- **LoadBalancer**: Provisions cloud load balancer (AWS ELB, GCP LB)

**In this platform** (all ClusterIP):
- `garage.garage.svc.cluster.local:3900` - Garage S3 API
- `trino.trino.svc.cluster.local:8080` - Trino coordinator
- `dagster-postgresql.dagster.svc.cluster.local:5432` - Dagster database

**Example**:
```bash
# List services
kubectl get svc -n garage

# Expected output:
# NAME              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
# garage            ClusterIP   10.96.100.50    <none>        3900/TCP,3902/TCP   5m
# garage-headless   ClusterIP   None            <none>        3900/TCP,3902/TCP   5m
```

**Understanding service output**:
- **ClusterIP**: Internal IP address (stable across pod restarts)
- **EXTERNAL-IP "none"**: Not exposed outside cluster
- **PORT(S)**: Format is `<container-port>/TCP`

**Headless service** (`garage-headless`):
- ClusterIP: None
- Returns pod IPs directly instead of load-balancing
- Used by [StatefulSets](stateful-applications.md) for pod discovery

**Key commands**:
```bash
kubectl get svc -n <namespace>                 # List services
kubectl describe svc <service-name> -n <namespace>  # Details and endpoints
kubectl get endpoints -n <namespace>           # View backend pods
```

### 4. Deployment

**What it is**: Manages a replicated set of stateless pods. Handles rolling updates, rollbacks, and scaling.

**Why it matters**: Most stateless applications (web servers, APIs) use Deployments. Kubernetes ensures the desired number of replicas are always running.

**Features**:
- **Rolling updates**: Gradually replace pods with new versions (zero downtime)
- **Rollback**: Revert to previous version if deployment fails
- **Scaling**: Change replica count declaratively

**In this platform**:
- `airbyte-server`: Deployment with 1 replica
- `airbyte-webapp`: Deployment with 1 replica
- `trino-coordinator`: Deployment with 1 replica
- `trino-worker`: Deployment with N replicas (configurable)

**Example**:
```bash
# List deployments
kubectl get deployments -n airbyte

# Scale deployment
kubectl scale deployment airbyte-server -n airbyte --replicas=2

# View rollout status
kubectl rollout status deployment/airbyte-server -n airbyte

# Rollback deployment
kubectl rollout undo deployment/airbyte-server -n airbyte
```

**Key commands**:
```bash
kubectl get deployments -n <namespace>         # List deployments
kubectl describe deployment <name> -n <namespace>  # Details
kubectl scale deployment <name> --replicas=3 -n <namespace>  # Scale
kubectl rollout restart deployment/<name> -n <namespace>  # Restart pods
```

### 5. StatefulSet

**What it is**: Manages stateful applications that require stable network identities, persistent storage, and ordered deployment.

**Why it matters**: Databases and distributed storage systems need StatefulSets because they require:
- **Stable pod names**: `garage-0`, `postgres-0` (not random names like `postgres-abc123`)
- **Stable storage**: Each pod gets its own PersistentVolumeClaim that persists across restarts
- **Ordered operations**: Pods start in sequence (0, 1, 2) and terminate in reverse (2, 1, 0)

**In this platform**:
- `garage-0`: StatefulSet for Garage storage node
- `dagster-postgresql-0`: StatefulSet for Dagster metadata database
- `airbyte-postgresql-0`: StatefulSet for Airbyte metadata database

**Difference from Deployment**:
| Feature | Deployment | StatefulSet |
|---------|-----------|-------------|
| Pod naming | Random (pod-abc123) | Ordered (pod-0, pod-1) |
| Storage | Shared or no storage | Dedicated PVC per pod |
| Scaling | Parallel | Sequential (ordered) |
| Use case | Stateless apps | Databases, storage clusters |

**Example**:
```bash
# List StatefulSets
kubectl get statefulset -n garage

# Expected output:
# NAME     READY   AGE
# garage   1/1     5m
```

**Scaling StatefulSets**:
```bash
# Scale to 3 replicas (creates garage-1, garage-2 in order)
kubectl scale statefulset garage -n garage --replicas=3

# Pods created sequentially: garage-0 → garage-1 → garage-2
```

See [Stateful Applications](stateful-applications.md) for detailed coverage.

**Key commands**:
```bash
kubectl get statefulset -n <namespace>         # List StatefulSets
kubectl describe statefulset <name> -n <namespace>  # Details
kubectl scale statefulset <name> --replicas=3 -n <namespace>  # Scale
```

### 6. PersistentVolumeClaim (PVC)

**What it is**: A request for storage that survives pod restarts and deletions. Kubernetes binds PVCs to available PersistentVolumes (PVs).

**Why it matters**: Without PVCs, data stored in containers is lost when pods restart. PVCs enable stateful applications like databases and object storage.

**In this platform**:
- `data-garage-0`: 10Gi storage for Garage S3 objects
- `meta-garage-0`: 1Gi storage for Garage metadata
- `data-dagster-postgresql-0`: Storage for Dagster database

**Lifecycle**:
1. **Pending**: Waiting for available PersistentVolume
2. **Bound**: Successfully attached to a PV
3. **Released**: PVC deleted but PV still exists
4. **Failed**: PV cannot be reclaimed

**Example**:
```bash
# List PVCs
kubectl get pvc -n garage

# Expected output:
# NAME            STATUS   VOLUME                 CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# data-garage-0   Bound    pvc-xxxxx              10Gi       RWO            hostpath       5m
# meta-garage-0   Bound    pvc-yyyyy              1Gi        RWO            hostpath       5m
```

**Understanding PVC output**:
- **STATUS "Bound"**: PVC successfully attached to PV (ready for use)
- **CAPACITY**: Requested storage size
- **ACCESS MODES**:
  - **RWO** (ReadWriteOnce): Volume mounted by single node (most common)
  - **ROX** (ReadOnlyMany): Volume mounted read-only by multiple nodes
  - **RWX** (ReadWriteMany): Volume mounted read-write by multiple nodes
- **STORAGECLASS**: Defines storage provider (Docker Desktop uses `hostpath`)

See [Kubernetes Storage](kubernetes-storage.md) for detailed coverage.

**Key commands**:
```bash
kubectl get pvc -n <namespace>                 # List PVCs
kubectl describe pvc <name> -n <namespace>     # Details and events
kubectl get pv                                 # List PersistentVolumes (cluster-wide)
```

## How These Concepts Work Together

**Example: Deploying Garage Storage**

1. **Create Namespace**: `kubectl apply -f namespaces/garage.yaml`
   - Logical isolation for Garage resources

2. **Deploy StatefulSet**: `helm install garage ...`
   - Creates `garage-0` pod with stable name
   - Automatically creates PVCs: `data-garage-0`, `meta-garage-0`

3. **Kubernetes binds PVCs**:
   - Finds available PersistentVolumes
   - Changes PVC status from Pending → Bound

4. **Pod starts**:
   - Kubernetes schedules pod on a node
   - Mounts PVCs to pod filesystem
   - Starts Garage container

5. **Service created**:
   - `garage` service provides stable DNS: `garage.garage.svc.cluster.local`
   - Routes traffic to `garage-0` pod

6. **Other services connect**:
   - [Airbyte](airbyte.md) uses `http://garage.garage.svc.cluster.local:3900` to write data
   - [Trino](trino.md) uses same endpoint to query data

## Common Patterns in This Platform

### Pattern 1: StatefulSet + Headless Service

Used for databases and distributed systems that need pod identity:

```yaml
# StatefulSet creates stable pods
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
spec:
  serviceName: garage-headless  # Points to headless service
  replicas: 1
  # ...

# Headless service (ClusterIP: None) for pod discovery
apiVersion: v1
kind: Service
metadata:
  name: garage-headless
spec:
  clusterIP: None
  selector:
    app: garage
```

**Why**: StatefulSet needs headless service for pod DNS resolution: `garage-0.garage-headless.garage.svc.cluster.local`

### Pattern 2: Deployment + ClusterIP Service

Used for stateless applications:

```yaml
# Deployment manages replicas
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airbyte-server
spec:
  replicas: 2
  # ...

# ClusterIP service load-balances across replicas
apiVersion: v1
kind: Service
metadata:
  name: airbyte-server
spec:
  type: ClusterIP
  selector:
    app: airbyte-server
  ports:
  - port: 8001
```

**Why**: Service provides stable endpoint regardless of which pod serves the request.

### Pattern 3: Namespace Isolation

Each domain gets its own namespace:

```bash
garage/     # Storage layer
├── garage-0 (StatefulSet)
├── garage service
└── PVCs: data-garage-0, meta-garage-0

airbyte/    # Ingestion layer
├── airbyte-server (Deployment)
├── airbyte-worker (Deployment)
└── airbyte-postgresql-0 (StatefulSet)

dagster/    # Orchestration layer
├── dagster-webserver (Deployment)
├── dagster-daemon (Deployment)
└── dagster-postgresql-0 (StatefulSet)

trino/      # Query layer
├── trino-coordinator (Deployment)
└── trino-worker (Deployment)
```

**Why**: Team independence, resource isolation, simplified RBAC.

## Troubleshooting

### Pod Not Starting (Pending Status)

**Symptom**: Pod stuck in "Pending" status

**Check**:
```bash
kubectl describe pod <pod-name> -n <namespace>
```

**Common causes**:
- **PVC not bound**: Check `kubectl get pvc -n <namespace>`
- **Insufficient resources**: Node doesn't have enough CPU/memory
- **ImagePullBackOff**: Cannot download container image

**Solution**:
```bash
# Check PVC status
kubectl get pvc -n <namespace>

# Check node resources
kubectl describe node

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

### Pod Crashing (CrashLoopBackOff)

**Symptom**: Pod repeatedly restarting

**Check**:
```bash
# View current logs
kubectl logs <pod-name> -n <namespace>

# View previous crash logs
kubectl logs <pod-name> -n <namespace> --previous
```

**Common causes**:
- Application error (check logs)
- Missing environment variables
- Failed health checks
- Dependency not ready (database not started)

### Service Not Accessible

**Symptom**: Cannot reach service from another pod

**Check**:
```bash
# Verify service has endpoints (backend pods)
kubectl get endpoints <service-name> -n <namespace>

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -n <namespace> -- nslookup garage.garage.svc.cluster.local

# Test connectivity
kubectl exec -it <pod-name> -n <namespace> -- curl http://garage.garage.svc.cluster.local:3900
```

**Common causes**:
- Service selector doesn't match pod labels
- Target pods not running
- Network policy blocking traffic
- Wrong port number

See [Kubernetes Networking](kubernetes-networking.md) for detailed troubleshooting.

## Integration with Other Components

- **[Helm Package Management](helm-package-management.md)**: Helm charts deploy these Kubernetes resources
- **[Kubernetes Networking](kubernetes-networking.md)**: Services enable cross-namespace communication
- **[Kubernetes Storage](kubernetes-storage.md)**: PVCs provide persistent storage for StatefulSets
- **[Stateful Applications](stateful-applications.md)**: Deep dive on StatefulSets and storage
- **[Garage](garage.md)**, **[Airbyte](airbyte.md)**, **[Dagster](dagster.md)**, **[Trino](trino.md)**: All deployed using these Kubernetes primitives

## References

- [Official Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kubernetes Concepts](https://kubernetes.io/docs/concepts/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Understanding Kubernetes Objects](https://kubernetes.io/docs/concepts/overview/working-with-objects/kubernetes-objects/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

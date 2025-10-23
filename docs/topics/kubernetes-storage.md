# Kubernetes Storage

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Kubernetes storage concepts and this project's architecture, please verify critical details against official Kubernetes documentation and your specific use cases.

## Overview

Kubernetes storage enables data persistence beyond the lifecycle of individual [Pods](kubernetes-fundamentals.md). Without persistent storage, data is lost when pods restart. Kubernetes provides several abstractions for managing storage: PersistentVolumes (PVs), PersistentVolumeClaims (PVCs), and StorageClasses.

In this lakehouse platform, storage is critical for stateful components: [Garage](garage.md) stores S3 objects, [PostgreSQL](postgresql.md) databases store metadata for [Airbyte](airbyte.md) and [Dagster](dagster.md). All use PersistentVolumeClaims to ensure data survives pod restarts.

## Why Storage Matters for This Platform

**Data Persistence**: Databases ([PostgreSQL](postgresql.md)) and object storage ([Garage](garage.md)) require data that survives pod failures and restarts.

**Stateful Applications**: [StatefulSets](stateful-applications.md) depend on stable storage identities - each pod gets its own dedicated PVC.

**Cluster Portability**: PVCs abstract away underlying storage providers (local disk, NFS, cloud block storage) enabling portability across environments.

**Data Integrity**: Prevents data loss during rolling updates, node failures, or pod rescheduling.

## Key Concepts

### 1. PersistentVolume (PV)

**What it is**: A piece of storage in the cluster provisioned by an administrator or dynamically by a StorageClass. Independent of pod lifecycle.

**PV characteristics**:
- **Cluster-wide resource**: Not namespaced (available to all namespaces)
- **Lifecycle independent of pods**: Exists until explicitly deleted
- **Access modes**: RWO (single node), ROX (read-only many), RWX (read-write many)
- **Reclaim policy**: What happens when PVC is deleted (Retain, Delete, Recycle)

**Example - View PersistentVolumes**:
```bash
kubectl get pv

# Expected output:
# NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM
# pvc-123abc...                              10Gi       RWO            Delete           Bound    garage/data-garage-0
# pvc-456def...                              1Gi        RWO            Delete           Bound    garage/meta-garage-0
# pvc-789ghi...                              8Gi        RWO            Delete           Bound    dagster/data-dagster-postgresql-0
```

**PV Status**:
- **Available**: Free, not bound to any claim
- **Bound**: Attached to a PVC
- **Released**: PVC deleted, but PV not yet reclaimed
- **Failed**: Automatic reclamation failed

**Access Modes**:
- **RWO (ReadWriteOnce)**: Mount read-write by single node (most common - databases, block storage)
- **ROX (ReadOnlyMany)**: Mount read-only by multiple nodes
- **RWX (ReadWriteMany)**: Mount read-write by multiple nodes (requires shared filesystem like NFS)

**Reclaim Policies**:
- **Delete**: PV automatically deleted when PVC is deleted (default for dynamic provisioning)
- **Retain**: PV kept after PVC deletion (manual cleanup required)
- **Recycle**: Basic scrub (`rm -rf /volume/*`) then make available again (deprecated)

### 2. PersistentVolumeClaim (PVC)

**What it is**: A request for storage by a user. PVCs bind to available PVs that satisfy the request (size, access mode, storage class).

**PVC characteristics**:
- **Namespaced**: Lives in specific namespace (e.g., `garage` namespace)
- **Bound to single PV**: One-to-one relationship
- **Used by pods**: Pods reference PVCs in volume mounts

**In this platform**:
```bash
# Garage storage
kubectl get pvc -n garage

# Expected output:
# NAME            STATUS   VOLUME          CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# data-garage-0   Bound    pvc-123abc...   10Gi       RWO            hostpath       10m
# meta-garage-0   Bound    pvc-456def...   1Gi        RWO            hostpath       10m

# Dagster PostgreSQL storage
kubectl get pvc -n dagster

# Expected output:
# NAME                           STATUS   VOLUME          CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# data-dagster-postgresql-0      Bound    pvc-789ghi...   8Gi        RWO            hostpath       10m
```

**PVC definition example** (from StatefulSet template):
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-garage-0
  namespace: garage
spec:
  accessModes:
  - ReadWriteOnce  # RWO
  resources:
    requests:
      storage: 10Gi  # Request 10GB storage
  storageClassName: hostpath  # Use hostpath storage class
```

**PVC Lifecycle**:
1. **Pending**: Waiting for matching PV or dynamic provisioning
2. **Bound**: Successfully attached to PV
3. **Lost**: PV doesn't exist anymore (manual intervention needed)

### 3. StorageClass

**What it is**: Defines storage "profiles" and enables dynamic provisioning. When PVC references a StorageClass, Kubernetes automatically creates a PV.

**StorageClass characteristics**:
- **Cluster-wide**: Not namespaced
- **Dynamic provisioning**: Creates PVs on demand
- **Parameters**: Storage-provider-specific settings (disk type, IOPS, replication)

**Example - Docker Desktop StorageClass**:
```bash
kubectl get storageclass

# Expected output:
# NAME                 PROVISIONER          RECLAIMPOLICY   VOLUMEBINDINGMODE      AGE
# hostpath (default)   docker.io/hostpath   Delete          Immediate              30d
```

**StorageClass definition**:
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: hostpath
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: docker.io/hostpath  # Provider (Docker Desktop uses local disk)
reclaimPolicy: Delete
volumeBindingMode: Immediate  # Bind PVC to PV immediately (vs WaitForFirstConsumer)
```

**Common provisioners**:
- **docker.io/hostpath**: Docker Desktop (local development)
- **kubernetes.io/aws-ebs**: AWS Elastic Block Storage
- **kubernetes.io/gce-pd**: Google Compute Engine Persistent Disk
- **kubernetes.io/azure-disk**: Azure Disk Storage
- **kubernetes.io/no-provisioner**: Manual provisioning only

**Volume Binding Modes**:
- **Immediate**: Bind PVC as soon as it's created (default)
- **WaitForFirstConsumer**: Delay binding until pod using PVC is scheduled (ensures volume and pod are in same availability zone)

### 4. Volume Lifecycle (Static vs Dynamic Provisioning)

**Static Provisioning** (manual):
1. Admin creates PV manually
2. User creates PVC
3. Kubernetes binds PVC to matching PV
4. Pod mounts PVC

**Dynamic Provisioning** (automatic):
1. User creates PVC with storageClassName
2. StorageClass provisioner automatically creates PV
3. Kubernetes binds PVC to new PV
4. Pod mounts PVC

**This project uses dynamic provisioning** (Docker Desktop's hostpath provisioner).

**Example - Dynamic Provisioning Flow**:
```bash
# 1. User creates PVC (via Helm chart)
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-garage-0
  namespace: garage
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: hostpath  # Triggers dynamic provisioning
EOF

# 2. Kubernetes triggers hostpath provisioner
# 3. Provisioner creates PV with 10Gi capacity
# 4. PVC status changes: Pending → Bound

kubectl get pvc data-garage-0 -n garage
# NAME            STATUS   VOLUME          CAPACITY
# data-garage-0   Bound    pvc-123abc...   10Gi
```

### 5. Volume Mounts in Pods

**What it is**: Pods reference PVCs in their volume specifications to mount persistent storage into containers.

**Example - Garage StatefulSet with PVC**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
  namespace: garage
spec:
  serviceName: garage-headless
  replicas: 1
  template:
    spec:
      containers:
      - name: garage
        image: dxflrs/garage:v0.8.0
        volumeMounts:
        - name: data  # Reference to volume
          mountPath: /data  # Where to mount in container
        - name: meta
          mountPath: /meta
  volumeClaimTemplates:  # StatefulSet creates PVC per replica
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

**Key points**:
- **volumeMounts**: Defines where volumes appear inside container (`/data`, `/meta`)
- **volumeClaimTemplates**: StatefulSet creates PVCs automatically per replica
  - Replica 0: `data-garage-0`, `meta-garage-0`
  - Replica 1: `data-garage-1`, `meta-garage-1`
  - etc.

**Verify volume mounts** inside pod:
```bash
kubectl exec -n garage garage-0 -- df -h

# Expected output:
# Filesystem      Size  Used  Avail  Use%  Mounted on
# /dev/sda1       10G   1.2G  8.8G   12%   /data
# /dev/sda2       1G    100M  900M   10%   /meta
```

## Storage Patterns in This Platform

### Pattern 1: StatefulSet with VolumeClaimTemplates

**Used by**: [Garage](garage.md), [PostgreSQL](postgresql.md) (Airbyte, Dagster)

**Why**: Each replica gets its own dedicated storage that persists across restarts

**Example - Garage StatefulSet**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: garage
spec:
  replicas: 3  # Creates 3 pods with 6 PVCs (2 per pod)
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
kubectl get pvc -n garage

# NAME            CAPACITY   POD
# data-garage-0   10Gi       garage-0
# meta-garage-0   1Gi        garage-0
# data-garage-1   10Gi       garage-1
# meta-garage-1   1Gi        garage-1
# data-garage-2   10Gi       garage-2
# meta-garage-2   1Gi        garage-2
```

**Behavior**:
- **Scale up**: New pod gets new PVC (`data-garage-3`)
- **Scale down**: PVC retained (not deleted automatically)
- **Pod restart**: Same pod mounts same PVC (data persists)

### Pattern 2: Deployment with Shared PVC

**Used by**: Stateless apps that occasionally need shared storage (logs, cache)

**Example**:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-logs
spec:
  accessModes:
  - ReadWriteMany  # RWX - multiple pods can mount
  resources:
    requests:
      storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-processor
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: processor
        volumeMounts:
        - name: logs
          mountPath: /var/log
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: shared-logs  # All replicas share same PVC
```

**Note**: Requires storage backend that supports RWX (NFS, CephFS, not local disk).

### Pattern 3: Temporary Storage (emptyDir)

**Used by**: Temporary scratch space, not persistent

**Example**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: temp-worker
spec:
  containers:
  - name: worker
    volumeMounts:
    - name: scratch
      mountPath: /tmp/scratch
  volumes:
  - name: emptyDir  # Created when pod starts, deleted when pod deleted
    emptyDir: {}
```

**Use cases**:
- Cache directories
- Temporary processing space
- Data shared between containers in same pod

**Not used for**: Databases, logs, persistent application data

## Troubleshooting

### PVC Stuck in Pending State

**Symptom**: PVC never binds to PV

```bash
kubectl get pvc -n garage

# NAME            STATUS    VOLUME   CAPACITY
# data-garage-0   Pending   ...      ...
```

**Check PVC events**:
```bash
kubectl describe pvc data-garage-0 -n garage

# Look for events like:
# Warning  ProvisioningFailed  ...  Failed to provision volume
# Warning  FailedBinding       ...  no persistent volumes available
```

**Common causes**:
1. **No matching PV**: No PV satisfies size/access mode requirements
2. **No StorageClass**: StorageClass doesn't exist or no default class
3. **Provisioner error**: Dynamic provisioning failed (check provisioner logs)
4. **Insufficient cluster storage**: Node doesn't have enough disk space

**Debug**:
```bash
# Check available PVs
kubectl get pv

# Check StorageClass exists
kubectl get storageclass

# Check node disk space (Docker Desktop)
kubectl top nodes

# Check provisioner logs (if using dynamic provisioning)
kubectl logs -n kube-system <provisioner-pod>
```

**Fix**:
```bash
# Create StorageClass if missing
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: hostpath
provisioner: docker.io/hostpath
EOF

# Or manually create PV
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-garage-data
spec:
  capacity:
    storage: 10Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: hostpath
  hostPath:
    path: /mnt/data/garage
EOF
```

### Pod Cannot Mount PVC

**Symptom**: Pod stuck in `ContainerCreating` or `Pending` status

```bash
kubectl describe pod garage-0 -n garage

# Events:
# Warning  FailedMount  ...  Unable to attach or mount volumes
```

**Common causes**:
1. **PVC doesn't exist**: Pod references non-existent PVC
2. **PVC not bound**: PVC still in Pending state
3. **Access mode conflict**: PVC has RWO but pod scheduled on different node than PV
4. **Permission denied**: Pod cannot write to mounted volume

**Debug**:
```bash
# Check PVC exists and is bound
kubectl get pvc -n garage

# Check pod node and PV node match (for RWO volumes)
kubectl get pod garage-0 -n garage -o wide
kubectl get pv <pv-name> -o yaml | grep nodeAffinity

# Check volume mount permissions inside pod
kubectl exec -n garage garage-0 -- ls -la /data
```

### Data Lost After Pod Restart

**Symptom**: Data disappeared after pod restart

**Common causes**:
1. **Using emptyDir instead of PVC**: emptyDir is ephemeral (deleted with pod)
2. **PVC deleted**: Someone deleted the PVC
3. **Reclaim policy Delete**: PV was deleted when PVC was deleted

**Verify storage is persistent**:
```bash
# Check pod uses PVC (not emptyDir)
kubectl get pod garage-0 -n garage -o yaml | grep -A 10 volumes

# Should show:
# volumes:
# - name: data
#   persistentVolumeClaim:
#     claimName: data-garage-0

# NOT:
# volumes:
# - name: data
#   emptyDir: {}
```

**Prevention**:
- Use PVCs for all persistent data
- Set reclaim policy to `Retain` for critical data
- Backup PVs regularly

### Disk Full / Out of Space

**Symptom**: Application logs show disk space errors

```bash
kubectl exec -n garage garage-0 -- df -h

# Filesystem      Size  Used  Avail  Use%  Mounted on
# /dev/sda1       10G   10G   0      100%  /data  # ← Full!
```

**Solutions**:

**Option 1: Increase PVC size** (if storage class supports expansion):
```bash
# Check if storage class allows expansion
kubectl get storageclass hostpath -o yaml | grep allowVolumeExpansion
# allowVolumeExpansion: true

# Edit PVC to request more space
kubectl edit pvc data-garage-0 -n garage

# Change:
# resources:
#   requests:
#     storage: 10Gi
# To:
#   requests:
#     storage: 20Gi

# Check expansion status
kubectl describe pvc data-garage-0 -n garage
```

**Option 2: Clean up data**:
```bash
# Delete old files inside pod
kubectl exec -n garage garage-0 -- rm -rf /data/old-data/*
```

**Option 3: Add new PVC**:
```bash
# Scale StatefulSet to add replica with new PVC
kubectl scale statefulset garage -n garage --replicas=2
```

## Integration with Other Components

- **[Kubernetes Fundamentals](kubernetes-fundamentals.md)**: PVCs used by Pods in StatefulSets
- **[Stateful Applications](stateful-applications.md)**: StatefulSets use VolumeClaimTemplates for per-replica storage
- **[Garage](garage.md)**: Uses 2 PVCs per replica (data + meta)
- **[PostgreSQL](postgresql.md)**: Uses 1 PVC per replica (database files)
- **[Helm Package Management](helm-package-management.md)**: Helm charts define PVC templates

## Best Practices

### 1. Always Use PVCs for Persistent Data

**Good** (database uses PVC):
```yaml
volumeMounts:
- name: data
  mountPath: /var/lib/postgresql
volumes:
- name: data
  persistentVolumeClaim:
    claimName: postgres-data
```

**Bad** (database uses emptyDir - data lost on restart):
```yaml
volumeMounts:
- name: data
  mountPath: /var/lib/postgresql
volumes:
- name: data
  emptyDir: {}
```

### 2. Use StorageClasses for Dynamic Provisioning

**Good** (dynamic):
```yaml
storageClassName: hostpath  # Auto-creates PV
```

**Acceptable** (static, manual):
```yaml
storageClassName: ""  # Use manually created PV
volumeName: pv-garage-data
```

### 3. Set Reclaim Policy Based on Data Criticality

**Production databases** (retain data after PVC deletion):
```yaml
reclaimPolicy: Retain
```

**Development/testing** (auto-cleanup):
```yaml
reclaimPolicy: Delete
```

### 4. Size PVCs Appropriately

**Consider**:
- Application data growth rate
- Backup/snapshot space requirements
- Storage costs (cloud environments)

**Example sizing for this platform**:
- **Garage data PVC**: 10Gi+ (grows with ingested data)
- **Garage meta PVC**: 1Gi (relatively static)
- **PostgreSQL PVC**: 8Gi (metadata only, not raw data)

### 5. Monitor Storage Usage

```bash
# Check PVC usage from inside pods
kubectl exec -n garage garage-0 -- df -h

# Check node storage (Docker Desktop)
kubectl top nodes

# Set up alerts for >80% disk usage
```

### 6. Backup Critical PVCs

**Methods**:
- Volume snapshots (VolumeSnapshot CRD)
- Backup tools (Velero, Kasten K10)
- Application-level backups (pg_dump for PostgreSQL)

## References

- [Official Kubernetes Storage](https://kubernetes.io/docs/concepts/storage/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

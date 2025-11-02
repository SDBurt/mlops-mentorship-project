# MinIO - S3-Compatible Distributed Object Storage

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established MinIO concepts and this project's architecture, please verify critical details against official MinIO documentation and your specific use cases.

## Overview

MinIO is a lightweight, self-hosted, S3-compatible object storage system designed for geo-distributed deployments. It provides an alternative to AWS S3, MinIO, or Ceph for storing large amounts of unstructured data (files, images, Parquet files, etc.).

In this lakehouse platform, MinIO serves as the foundational storage layer: [Airbyte](airbyte.md) writes ingested data as Parquet files, [Trino](trino.md) queries [Apache Iceberg](apache-iceberg.md) tables stored in MinIO, and [DBT](dbt.md) transformations materialize results back to MinIO.

## Why MinIO for This Platform?

**S3 Compatibility**: Uses standard S3 API - works with any S3-compatible tool (Airbyte, Trino, Spark, AWS CLI).

**Lightweight**: Minimal resource requirements perfect for local development and learning environments.

**Distributed Architecture**: Designed for horizontal scaling - add nodes to increase capacity and throughput.

**No Cloud Dependencies**: Runs on-premises or locally (Docker Desktop), no AWS account required.

**Data Durability**: Replication across nodes (in multi-node deployments) ensures data survives node failures.

**Learning Value**: Understanding distributed storage systems is valuable for data engineering careers.

## Key Concepts

### 1. S3 API Compatibility

**What it is**: MinIO implements AWS S3 HTTP API, making it a drop-in replacement for S3.

**Supported operations**:
- **Bucket operations**: CreateBucket, DeleteBucket, ListBuckets
- **Object operations**: PutObject, GetObject, DeleteObject, ListObjects
- **Multipart uploads**: For large files
- **Object tagging**: Metadata on objects
- **Versioning**: Keep multiple versions of objects (optional)

**Not supported** (as of v0.8):
- Server-side encryption (SSE-KMS)
- Object locking (WORM)
- Bucket policies (basic ACLs only)
- CloudFront-style CDN integration

**Example - Using AWS CLI**:
```bash
# Configure AWS CLI for MinIO
aws configure --profile minio
# AWS Access Key ID: <from-minio-key-create>
# AWS Secret Access Key: <from-minio-key-create>
# Default region name: minio
# Default output format: json

# List buckets
aws s3 ls --endpoint-url http://localhost:3900 --profile minio

# Upload file
aws s3 cp myfile.parquet s3://lakehouse/raw/myfile.parquet \
  --endpoint-url http://localhost:3900 --profile minio

# Download file
aws s3 cp s3://lakehouse/raw/myfile.parquet ./local.parquet \
  --endpoint-url http://localhost:3900 --profile minio

# List objects in bucket
aws s3 ls s3://lakehouse/raw/ --endpoint-url http://localhost:3900 --profile minio
```

**Integration - Trino S3 Configuration**:
```properties
hive.s3.endpoint=http://minio:3900
hive.s3.path-style-access=true  # Required for MinIO
hive.s3.aws-access-key=<from-minio-key-create>
hive.s3.aws-secret-key=<from-minio-key-create>
hive.s3.region=minio
```

### 2. Distributed Architecture

**What it is**: MinIO uses a peer-to-peer architecture where all nodes are equal (no master/slave).

**Components per node**:
- **RPC layer** (port 3901): Node-to-node communication
- **S3 API** (port 3900): Client requests
- **Admin API** (port 3902): Cluster management

**Cluster layout**:
- **Nodes**: Physical instances running MinIO (e.g., `minio-0`, `minio-1`, `minio-2`)
- **Zones**: Logical groupings for data placement (e.g., `dc1`, `dc2` for different datacenters)
- **Partitions**: Data split into 256 fixed partitions distributed across nodes
- **Replication**: Each partition replicated N times (configurable, default 3)

**Example cluster with 3 nodes**:
```
Zone: dc1
├── minio-0 (10.244.0.5)
│   ├── Capacity: 10GB
│   └── Partitions: 85 (0, 3, 6, 9...)
├── minio-1 (10.244.0.6)
│   ├── Capacity: 10GB
│   └── Partitions: 86 (1, 4, 7, 10...)
└── minio-2 (10.244.0.7)
    ├── Capacity: 10GB
    └── Partitions: 85 (2, 5, 8, 11...)
```

**Data flow**:
1. Client sends PutObject request to any node (e.g., minio-0)
2. MinIO determines partition based on object key hash
3. Data replicated to nodes responsible for that partition
4. Acknowledgment sent to client when quorum reached

### 3. Cluster Initialization

**CRITICAL**: MinIO cluster **must be initialized** after deployment before it can store data.

**Why**: Even single-node deployments need explicit configuration telling MinIO:
- Which nodes should store data
- How much capacity each node has
- How data should be distributed across partitions

**Initialization steps**:

**Step 1: Check cluster status**
```bash
# Get MinIO pod name
GARAGE_POD=$(kubectl get pods -n lakehouse -l app.kubernetes.io/name=minio -o jsonpath='{.items[0].metadata.name}')

# View current status
kubectl exec -n lakehouse $GARAGE_POD -- /minio status
```

**Expected output (before initialization)**:
```
==== HEALTHY NODES ====
ID                                Hostname  Address         Tags  Zone  Capacity
1234abcd5678efgh...               minio-0  10.244.0.5:3901               NO ROLE ASSIGNED
```

**Step 2: Assign storage role**
```bash
# Get node ID
NODE_ID=$(kubectl exec -n lakehouse $GARAGE_POD -- /minio status 2>/dev/null | \
  grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $1}')

# Assign role with capacity
kubectl exec -n lakehouse $GARAGE_POD -- /minio layout assign \
  -z minio-dc \
  -c 10G \
  $NODE_ID
```

**Parameters**:
- `-z minio-dc`: Zone name (for multi-datacenter awareness)
- `-c 10G`: Storage capacity to allocate
- `$NODE_ID`: Node to configure

**Step 3: Review proposed layout**
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio layout show
```

**Step 4: Apply layout**
```bash
# Apply layout version 1 (first-time setup)
kubectl exec -n lakehouse $GARAGE_POD -- /minio layout apply --version 1
```

**Step 5: Verify**
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio status

# Expected output (after initialization):
# ==== HEALTHY NODES ====
# ID                Hostname  Address         Tags  Zone       Capacity  DataAvail
# 1234abcd...       minio-0  10.244.0.5:3901       minio-dc  10.0 GB   10.0 GB
```

**Success**: Node now shows capacity instead of "NO ROLE ASSIGNED"!

### 4. Buckets and Access Keys

**Buckets**: Top-level containers for objects (like S3 buckets)

**Create bucket**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket create lakehouse
```

**Access keys**: Credentials for S3 API authentication (like AWS access keys)

**Create access key**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio key create lakehouse-access
```

**Output**:
```
Key created:
Name: lakehouse-access
Access Key ID: GK1234567890abcdefgh
Secret Access Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Grant bucket permissions**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket allow \
  --read --write lakehouse --key lakehouse-access
```

**List buckets**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket list

# Expected output:
# BUCKET      VISIBILITY
# lakehouse   private
```

**List keys**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio key list

# Expected output:
# Key ID              Key Name
# GK1234567890...     lakehouse-access
```

### 5. Data Storage and Partitioning

**How data is stored**:
1. **Object key hashed**: Deterministic hash function maps key to partition number (0-255)
2. **Partition placement**: Cluster layout determines which nodes store each partition
3. **Replication**: Data replicated to N nodes (replication factor, default 3)
4. **Local storage**: Each node stores its partition data in PersistentVolume

**Example**:
```
Object: s3://lakehouse/raw/customers.parquet
Key hash: 0x7F3A... → Partition 127
Partition 127 assigned to: minio-0, minio-1, minio-2
Data written to all 3 nodes
```

**Storage paths** (inside MinIO pod):
```bash
kubectl exec -n lakehouse $GARAGE_POD -- ls -lh /data/

# Output:
# drwxr-xr-x 2 root root 4.0K data/
# drwxr-xr-x 2 root root 4.0K meta/
```

- **/data**: Actual object data (Parquet files, etc.)
- **/meta**: MinIO metadata (partition assignments, object index)

**Check storage usage**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- df -h /data /meta

# Output:
# Filesystem      Size  Used  Avail Use% Mounted on
# /dev/sda1       10G   2.3G  7.7G  23%  /data
# /dev/sda2       1G    150M  850M  15%  /meta
```

## Deployment in Kubernetes

### StatefulSet Configuration

MinIO deployed as [StatefulSet](stateful-applications.md) with:
- **Stable pod name**: `minio-0`, `minio-1`, etc.
- **Persistent storage**: 2 PVCs per replica (data + meta)
- **Headless service**: Peer discovery via DNS

**Key files**:
- `infrastructure/helm/minio/`: Helm chart (fetched from MinIO repo)
- `infrastructure/kubernetes/minio/values.yaml`: Custom configuration
- `infrastructure/kubernetes/namespaces/minio.yaml`: Namespace definition

**Deployment command**:
```bash
helm upgrade --install minio infrastructure/helm/minio \
  -f infrastructure/kubernetes/minio/values.yaml \
  -n lakehouse --create-namespace --wait
```

**What gets created**:
```bash
kubectl get all -n minio

# pod/minio-0
# service/minio (ClusterIP)
# service/minio-headless (ClusterIP: None)
# statefulset.apps/minio (1/1 replicas)
# persistentvolumeclaim/data-minio-0 (10Gi)
# persistentvolumeclaim/meta-minio-0 (1Gi)
```

### Scaling MinIO Cluster

**Scale to 3 nodes**:
```bash
# Update Helm values
# replicas: 3

helm upgrade minio infrastructure/helm/minio \
  -f infrastructure/kubernetes/minio/values.yaml \
  -n minio

# Or scale StatefulSet directly
kubectl scale statefulset minio -n lakehouse --replicas=3
```

**Initialize new nodes**:
```bash
# Assign roles to new nodes (minio-1, minio-2)
for i in 1 2; do
  NODE_ID=$(kubectl exec -n lakehouse minio-$i -- /minio node id)
  kubectl exec -n lakehouse minio-0 -- /minio layout assign -z minio-dc -c 10G $NODE_ID
done

# Apply layout version 2
kubectl exec -n lakehouse minio-0 -- /minio layout apply --version 2

# Verify
kubectl exec -n lakehouse minio-0 -- /minio status
```

**Result**: Data automatically rebalanced across 3 nodes.

## Integration with Other Components

### Airbyte → MinIO

**Configuration** (`infrastructure/kubernetes/airbyte/values.yaml`):
```yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://minio:3900
      bucketName: lakehouse
      accessKeyId: GK1234567890abcdefgh
      secretAccessKey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**What Airbyte stores**:
- **Internal state**: Connector state, job logs
- **Destination data**: Raw ingested data (if S3 destination configured)

### Trino → MinIO

**Configuration** (Trino Iceberg catalog):
```properties
iceberg.catalog.type=hive_metastore
hive.s3.endpoint=http://minio:3900
hive.s3.path-style-access=true
hive.s3.aws-access-key=GK1234567890abcdefgh
hive.s3.aws-secret-key=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**What Trino queries**:
- **Iceberg tables**: Parquet data files
- **Metadata files**: Iceberg manifest files, snapshot files

### DBT → Trino → MinIO

**Flow**:
1. DBT sends SQL to Trino
2. Trino executes query over MinIO data
3. DBT materialization writes new Iceberg tables to MinIO

## Common Operations

### View Cluster Status

```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio status

# Shows: Node IDs, addresses, zones, capacity, data usage
```

### View Cluster Layout

```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio layout show

# Shows: Current layout, staged changes, partition distribution
```

### Bucket Management

```bash
# Create bucket
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket create <bucket-name>

# List buckets
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket list

# Delete bucket (must be empty)
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket delete <bucket-name>

# View bucket info
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket info <bucket-name>
```

### Key Management

```bash
# Create key
kubectl exec -n lakehouse $GARAGE_POD -- /minio key create <key-name>

# List keys
kubectl exec -n lakehouse $GARAGE_POD -- /minio key list

# Grant permissions
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket allow \
  --read --write <bucket> --key <key-name>

# Revoke permissions
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket deny \
  --read --write <bucket> --key <key-name>

# Delete key
kubectl exec -n lakehouse $GARAGE_POD -- /minio key delete <key-name>
```

### Monitoring

```bash
# Check storage usage
kubectl exec -n lakehouse $GARAGE_POD -- df -h /data /meta

# View MinIO logs
kubectl logs -n lakehouse minio-0 --tail=100 -f

# Describe pod for events
kubectl describe pod -n lakehouse minio-0
```

## Troubleshooting

### MinIO Pod Not Starting

**Check pod status**:
```bash
kubectl get pods -n minio
kubectl describe pod minio-0 -n minio
```

**Common causes**:
- **PVC not binding**: Check `kubectl get pvc -n minio`
- **Image pull error**: Check internet connectivity or image name
- **Resource constraints**: Check `kubectl top nodes`

### "NO ROLE ASSIGNED" - Cluster Not Initialized

**Symptom**: MinIO pod running but cannot store data

**Check**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio status

# If shows "NO ROLE ASSIGNED", cluster needs initialization
```

**Fix**: Follow initialization steps (section 3 above)

### S3 API Returns 403 Forbidden

**Symptom**: AWS CLI or application gets 403 errors

**Common causes**:
1. **Wrong access key**: Verify key matches output from `minio key create`
2. **Bucket permissions**: Key doesn't have read/write permission
3. **Bucket doesn't exist**: Check `minio bucket list`

**Debug**:
```bash
# Verify key exists
kubectl exec -n lakehouse $GARAGE_POD -- /minio key list

# Verify bucket exists
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket list

# Check bucket permissions
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket info lakehouse
```

**Fix**:
```bash
# Grant permissions
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket allow \
  --read --write lakehouse --key lakehouse-access
```

### Storage Full

**Symptom**: MinIO logs show disk space errors

**Check**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- df -h /data

# If Use% is 100%, storage is full
```

**Solutions**:
1. **Delete old data**: Use AWS CLI to delete objects
2. **Expand PVC**: Increase storage size (if storage class supports expansion)
3. **Add more nodes**: Scale StatefulSet to distribute data

**Expand PVC** (if supported):
```bash
kubectl edit pvc data-minio-0 -n minio

# Change:
# resources:
#   requests:
#     storage: 10Gi
# To:
#   requests:
#     storage: 20Gi
```

### Network Connectivity Issues

**Symptom**: Services cannot reach MinIO

**Test from client pod**:
```bash
kubectl run -it --rm test --image=curlimages/curl --restart=Never -n lakehouse -- \
  curl -I http://minio:3900
```

**Expected**: HTTP response (403 if unauthenticated)

**If connection fails**:
- Check service exists: `kubectl get svc -n minio`
- Check endpoints: `kubectl get endpoints minio -n minio`
- Check DNS: See [Cross-Namespace Communication](cross-namespace-communication.md)

## Best Practices

### 1. Initialize Cluster Immediately After Deployment

Don't wait - MinIO is unusable until initialized:
```bash
# Right after helm install
helm upgrade --install minio ...
kubectl wait --for=condition=ready pod/minio-0 -n lakehouse --timeout=300s
# Now initialize
kubectl exec -n lakehouse minio-0 -- /minio layout assign ...
```

### 2. Use Meaningful Key Names

```bash
# Good: Descriptive names
/minio key create airbyte-ingestion
/minio key create trino-query
/minio key create dbt-transform

# Bad: Generic names
/minio key create key1
/minio key create mykey
```

### 3. Separate Buckets by Purpose

```bash
/minio bucket create lakehouse-raw      # Airbyte writes here
/minio bucket create lakehouse-bronze   # Bronze layer
/minio bucket create lakehouse-silver   # Silver layer
/minio bucket create lakehouse-gold     # Gold layer
```

### 4. Monitor Storage Usage

Set up alerts for >80% disk usage:
```bash
# Check regularly
kubectl exec -n lakehouse minio-0 -- df -h /data | tail -1 | awk '{print $5}'
```

### 5. Backup MinIO Metadata

**Critical files to backup**:
- Cluster layout configuration
- Access keys and bucket permissions

**Export configuration**:
```bash
kubectl exec -n lakehouse $GARAGE_POD -- /minio layout show > minio-layout-backup.txt
kubectl exec -n lakehouse $GARAGE_POD -- /minio key list > minio-keys-backup.txt
kubectl exec -n lakehouse $GARAGE_POD -- /minio bucket list > minio-buckets-backup.txt
```

## References

- [Official MinIO Documentation](https://miniohq.deuxfleurs.fr/documentation/)
- [MinIO Cookbook (Deployment Guides)](https://miniohq.deuxfleurs.fr/documentation/cookbook/)
- [S3 API Compatibility](https://miniohq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/)
- [MinIO Architecture](https://miniohq.deuxfleurs.fr/documentation/design/internals/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
- [Apache Iceberg](apache-iceberg.md) - Table format stored in MinIO
- [Trino](trino.md) - Queries MinIO data
- [Airbyte](airbyte.md) - Writes data to MinIO

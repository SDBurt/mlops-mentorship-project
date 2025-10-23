# Garage - S3-Compatible Distributed Object Storage

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Garage concepts and this project's architecture, please verify critical details against official Garage documentation and your specific use cases.

## Overview

Garage is a lightweight, self-hosted, S3-compatible object storage system designed for geo-distributed deployments. It provides an alternative to AWS S3, MinIO, or Ceph for storing large amounts of unstructured data (files, images, Parquet files, etc.).

In this lakehouse platform, Garage serves as the foundational storage layer: [Airbyte](airbyte.md) writes ingested data as Parquet files, [Trino](trino.md) queries [Apache Iceberg](apache-iceberg.md) tables stored in Garage, and [DBT](dbt.md) transformations materialize results back to Garage.

## Why Garage for This Platform?

**S3 Compatibility**: Uses standard S3 API - works with any S3-compatible tool (Airbyte, Trino, Spark, AWS CLI).

**Lightweight**: Minimal resource requirements perfect for local development and learning environments.

**Distributed Architecture**: Designed for horizontal scaling - add nodes to increase capacity and throughput.

**No Cloud Dependencies**: Runs on-premises or locally (Docker Desktop), no AWS account required.

**Data Durability**: Replication across nodes (in multi-node deployments) ensures data survives node failures.

**Learning Value**: Understanding distributed storage systems is valuable for data engineering careers.

## Key Concepts

### 1. S3 API Compatibility

**What it is**: Garage implements AWS S3 HTTP API, making it a drop-in replacement for S3.

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
# Configure AWS CLI for Garage
aws configure --profile garage
# AWS Access Key ID: <from-garage-key-create>
# AWS Secret Access Key: <from-garage-key-create>
# Default region name: garage
# Default output format: json

# List buckets
aws s3 ls --endpoint-url http://localhost:3900 --profile garage

# Upload file
aws s3 cp myfile.parquet s3://lakehouse/raw/myfile.parquet \
  --endpoint-url http://localhost:3900 --profile garage

# Download file
aws s3 cp s3://lakehouse/raw/myfile.parquet ./local.parquet \
  --endpoint-url http://localhost:3900 --profile garage

# List objects in bucket
aws s3 ls s3://lakehouse/raw/ --endpoint-url http://localhost:3900 --profile garage
```

**Integration - Trino S3 Configuration**:
```properties
hive.s3.endpoint=http://garage.garage.svc.cluster.local:3900
hive.s3.path-style-access=true  # Required for Garage
hive.s3.aws-access-key=<from-garage-key-create>
hive.s3.aws-secret-key=<from-garage-key-create>
hive.s3.region=garage
```

### 2. Distributed Architecture

**What it is**: Garage uses a peer-to-peer architecture where all nodes are equal (no master/slave).

**Components per node**:
- **RPC layer** (port 3901): Node-to-node communication
- **S3 API** (port 3900): Client requests
- **Admin API** (port 3902): Cluster management

**Cluster layout**:
- **Nodes**: Physical instances running Garage (e.g., `garage-0`, `garage-1`, `garage-2`)
- **Zones**: Logical groupings for data placement (e.g., `dc1`, `dc2` for different datacenters)
- **Partitions**: Data split into 256 fixed partitions distributed across nodes
- **Replication**: Each partition replicated N times (configurable, default 3)

**Example cluster with 3 nodes**:
```
Zone: dc1
├── garage-0 (10.244.0.5)
│   ├── Capacity: 10GB
│   └── Partitions: 85 (0, 3, 6, 9...)
├── garage-1 (10.244.0.6)
│   ├── Capacity: 10GB
│   └── Partitions: 86 (1, 4, 7, 10...)
└── garage-2 (10.244.0.7)
    ├── Capacity: 10GB
    └── Partitions: 85 (2, 5, 8, 11...)
```

**Data flow**:
1. Client sends PutObject request to any node (e.g., garage-0)
2. Garage determines partition based on object key hash
3. Data replicated to nodes responsible for that partition
4. Acknowledgment sent to client when quorum reached

### 3. Cluster Initialization

**CRITICAL**: Garage cluster **must be initialized** after deployment before it can store data.

**Why**: Even single-node deployments need explicit configuration telling Garage:
- Which nodes should store data
- How much capacity each node has
- How data should be distributed across partitions

**Initialization steps**:

**Step 1: Check cluster status**
```bash
# Get Garage pod name
GARAGE_POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# View current status
kubectl exec -n garage $GARAGE_POD -- /garage status
```

**Expected output (before initialization)**:
```
==== HEALTHY NODES ====
ID                                Hostname  Address         Tags  Zone  Capacity
1234abcd5678efgh...               garage-0  10.244.0.5:3901               NO ROLE ASSIGNED
```

**Step 2: Assign storage role**
```bash
# Get node ID
NODE_ID=$(kubectl exec -n garage $GARAGE_POD -- /garage status 2>/dev/null | \
  grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $1}')

# Assign role with capacity
kubectl exec -n garage $GARAGE_POD -- /garage layout assign \
  -z garage-dc \
  -c 10G \
  $NODE_ID
```

**Parameters**:
- `-z garage-dc`: Zone name (for multi-datacenter awareness)
- `-c 10G`: Storage capacity to allocate
- `$NODE_ID`: Node to configure

**Step 3: Review proposed layout**
```bash
kubectl exec -n garage $GARAGE_POD -- /garage layout show
```

**Step 4: Apply layout**
```bash
# Apply layout version 1 (first-time setup)
kubectl exec -n garage $GARAGE_POD -- /garage layout apply --version 1
```

**Step 5: Verify**
```bash
kubectl exec -n garage $GARAGE_POD -- /garage status

# Expected output (after initialization):
# ==== HEALTHY NODES ====
# ID                Hostname  Address         Tags  Zone       Capacity  DataAvail
# 1234abcd...       garage-0  10.244.0.5:3901       garage-dc  10.0 GB   10.0 GB
```

**Success**: Node now shows capacity instead of "NO ROLE ASSIGNED"!

### 4. Buckets and Access Keys

**Buckets**: Top-level containers for objects (like S3 buckets)

**Create bucket**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage bucket create lakehouse
```

**Access keys**: Credentials for S3 API authentication (like AWS access keys)

**Create access key**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage key create lakehouse-access
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
kubectl exec -n garage $GARAGE_POD -- /garage bucket allow \
  --read --write lakehouse --key lakehouse-access
```

**List buckets**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage bucket list

# Expected output:
# BUCKET      VISIBILITY
# lakehouse   private
```

**List keys**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage key list

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
Partition 127 assigned to: garage-0, garage-1, garage-2
Data written to all 3 nodes
```

**Storage paths** (inside Garage pod):
```bash
kubectl exec -n garage $GARAGE_POD -- ls -lh /data/

# Output:
# drwxr-xr-x 2 root root 4.0K data/
# drwxr-xr-x 2 root root 4.0K meta/
```

- **/data**: Actual object data (Parquet files, etc.)
- **/meta**: Garage metadata (partition assignments, object index)

**Check storage usage**:
```bash
kubectl exec -n garage $GARAGE_POD -- df -h /data /meta

# Output:
# Filesystem      Size  Used  Avail Use% Mounted on
# /dev/sda1       10G   2.3G  7.7G  23%  /data
# /dev/sda2       1G    150M  850M  15%  /meta
```

## Deployment in Kubernetes

### StatefulSet Configuration

Garage deployed as [StatefulSet](stateful-applications.md) with:
- **Stable pod name**: `garage-0`, `garage-1`, etc.
- **Persistent storage**: 2 PVCs per replica (data + meta)
- **Headless service**: Peer discovery via DNS

**Key files**:
- `infrastructure/helm/garage/`: Helm chart (fetched from Garage repo)
- `infrastructure/kubernetes/garage/values.yaml`: Custom configuration
- `infrastructure/kubernetes/namespaces/garage.yaml`: Namespace definition

**Deployment command**:
```bash
helm upgrade --install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage --create-namespace --wait
```

**What gets created**:
```bash
kubectl get all -n garage

# pod/garage-0
# service/garage (ClusterIP)
# service/garage-headless (ClusterIP: None)
# statefulset.apps/garage (1/1 replicas)
# persistentvolumeclaim/data-garage-0 (10Gi)
# persistentvolumeclaim/meta-garage-0 (1Gi)
```

### Scaling Garage Cluster

**Scale to 3 nodes**:
```bash
# Update Helm values
# replicas: 3

helm upgrade garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage

# Or scale StatefulSet directly
kubectl scale statefulset garage -n garage --replicas=3
```

**Initialize new nodes**:
```bash
# Assign roles to new nodes (garage-1, garage-2)
for i in 1 2; do
  NODE_ID=$(kubectl exec -n garage garage-$i -- /garage node id)
  kubectl exec -n garage garage-0 -- /garage layout assign -z garage-dc -c 10G $NODE_ID
done

# Apply layout version 2
kubectl exec -n garage garage-0 -- /garage layout apply --version 2

# Verify
kubectl exec -n garage garage-0 -- /garage status
```

**Result**: Data automatically rebalanced across 3 nodes.

## Integration with Other Components

### Airbyte → Garage

**Configuration** (`infrastructure/kubernetes/airbyte/values.yaml`):
```yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://garage.garage.svc.cluster.local:3900
      bucketName: lakehouse
      accessKeyId: GK1234567890abcdefgh
      secretAccessKey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**What Airbyte stores**:
- **Internal state**: Connector state, job logs
- **Destination data**: Raw ingested data (if S3 destination configured)

### Trino → Garage

**Configuration** (Trino Iceberg catalog):
```properties
iceberg.catalog.type=hive_metastore
hive.s3.endpoint=http://garage.garage.svc.cluster.local:3900
hive.s3.path-style-access=true
hive.s3.aws-access-key=GK1234567890abcdefgh
hive.s3.aws-secret-key=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**What Trino queries**:
- **Iceberg tables**: Parquet data files
- **Metadata files**: Iceberg manifest files, snapshot files

### DBT → Trino → Garage

**Flow**:
1. DBT sends SQL to Trino
2. Trino executes query over Garage data
3. DBT materialization writes new Iceberg tables to Garage

## Common Operations

### View Cluster Status

```bash
kubectl exec -n garage $GARAGE_POD -- /garage status

# Shows: Node IDs, addresses, zones, capacity, data usage
```

### View Cluster Layout

```bash
kubectl exec -n garage $GARAGE_POD -- /garage layout show

# Shows: Current layout, staged changes, partition distribution
```

### Bucket Management

```bash
# Create bucket
kubectl exec -n garage $GARAGE_POD -- /garage bucket create <bucket-name>

# List buckets
kubectl exec -n garage $GARAGE_POD -- /garage bucket list

# Delete bucket (must be empty)
kubectl exec -n garage $GARAGE_POD -- /garage bucket delete <bucket-name>

# View bucket info
kubectl exec -n garage $GARAGE_POD -- /garage bucket info <bucket-name>
```

### Key Management

```bash
# Create key
kubectl exec -n garage $GARAGE_POD -- /garage key create <key-name>

# List keys
kubectl exec -n garage $GARAGE_POD -- /garage key list

# Grant permissions
kubectl exec -n garage $GARAGE_POD -- /garage bucket allow \
  --read --write <bucket> --key <key-name>

# Revoke permissions
kubectl exec -n garage $GARAGE_POD -- /garage bucket deny \
  --read --write <bucket> --key <key-name>

# Delete key
kubectl exec -n garage $GARAGE_POD -- /garage key delete <key-name>
```

### Monitoring

```bash
# Check storage usage
kubectl exec -n garage $GARAGE_POD -- df -h /data /meta

# View Garage logs
kubectl logs -n garage garage-0 --tail=100 -f

# Describe pod for events
kubectl describe pod -n garage garage-0
```

## Troubleshooting

### Garage Pod Not Starting

**Check pod status**:
```bash
kubectl get pods -n garage
kubectl describe pod garage-0 -n garage
```

**Common causes**:
- **PVC not binding**: Check `kubectl get pvc -n garage`
- **Image pull error**: Check internet connectivity or image name
- **Resource constraints**: Check `kubectl top nodes`

### "NO ROLE ASSIGNED" - Cluster Not Initialized

**Symptom**: Garage pod running but cannot store data

**Check**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage status

# If shows "NO ROLE ASSIGNED", cluster needs initialization
```

**Fix**: Follow initialization steps (section 3 above)

### S3 API Returns 403 Forbidden

**Symptom**: AWS CLI or application gets 403 errors

**Common causes**:
1. **Wrong access key**: Verify key matches output from `garage key create`
2. **Bucket permissions**: Key doesn't have read/write permission
3. **Bucket doesn't exist**: Check `garage bucket list`

**Debug**:
```bash
# Verify key exists
kubectl exec -n garage $GARAGE_POD -- /garage key list

# Verify bucket exists
kubectl exec -n garage $GARAGE_POD -- /garage bucket list

# Check bucket permissions
kubectl exec -n garage $GARAGE_POD -- /garage bucket info lakehouse
```

**Fix**:
```bash
# Grant permissions
kubectl exec -n garage $GARAGE_POD -- /garage bucket allow \
  --read --write lakehouse --key lakehouse-access
```

### Storage Full

**Symptom**: Garage logs show disk space errors

**Check**:
```bash
kubectl exec -n garage $GARAGE_POD -- df -h /data

# If Use% is 100%, storage is full
```

**Solutions**:
1. **Delete old data**: Use AWS CLI to delete objects
2. **Expand PVC**: Increase storage size (if storage class supports expansion)
3. **Add more nodes**: Scale StatefulSet to distribute data

**Expand PVC** (if supported):
```bash
kubectl edit pvc data-garage-0 -n garage

# Change:
# resources:
#   requests:
#     storage: 10Gi
# To:
#   requests:
#     storage: 20Gi
```

### Network Connectivity Issues

**Symptom**: Services cannot reach Garage

**Test from client pod**:
```bash
kubectl run -it --rm test --image=curlimages/curl --restart=Never -n airbyte -- \
  curl -I http://garage.garage.svc.cluster.local:3900
```

**Expected**: HTTP response (403 if unauthenticated)

**If connection fails**:
- Check service exists: `kubectl get svc -n garage`
- Check endpoints: `kubectl get endpoints garage -n garage`
- Check DNS: See [Cross-Namespace Communication](cross-namespace-communication.md)

## Best Practices

### 1. Initialize Cluster Immediately After Deployment

Don't wait - Garage is unusable until initialized:
```bash
# Right after helm install
helm upgrade --install garage ...
kubectl wait --for=condition=ready pod/garage-0 -n garage --timeout=300s
# Now initialize
kubectl exec -n garage garage-0 -- /garage layout assign ...
```

### 2. Use Meaningful Key Names

```bash
# Good: Descriptive names
/garage key create airbyte-ingestion
/garage key create trino-query
/garage key create dbt-transform

# Bad: Generic names
/garage key create key1
/garage key create mykey
```

### 3. Separate Buckets by Purpose

```bash
/garage bucket create lakehouse-raw      # Airbyte writes here
/garage bucket create lakehouse-bronze   # Bronze layer
/garage bucket create lakehouse-silver   # Silver layer
/garage bucket create lakehouse-gold     # Gold layer
```

### 4. Monitor Storage Usage

Set up alerts for >80% disk usage:
```bash
# Check regularly
kubectl exec -n garage garage-0 -- df -h /data | tail -1 | awk '{print $5}'
```

### 5. Backup Garage Metadata

**Critical files to backup**:
- Cluster layout configuration
- Access keys and bucket permissions

**Export configuration**:
```bash
kubectl exec -n garage $GARAGE_POD -- /garage layout show > garage-layout-backup.txt
kubectl exec -n garage $GARAGE_POD -- /garage key list > garage-keys-backup.txt
kubectl exec -n garage $GARAGE_POD -- /garage bucket list > garage-buckets-backup.txt
```

## References

- [Official Garage Documentation](https://garagehq.deuxfleurs.fr/documentation/)
- [Garage Cookbook (Deployment Guides)](https://garagehq.deuxfleurs.fr/documentation/cookbook/)
- [S3 API Compatibility](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/)
- [Garage Architecture](https://garagehq.deuxfleurs.fr/documentation/design/internals/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)
- [Apache Iceberg](apache-iceberg.md) - Table format stored in Garage
- [Trino](trino.md) - Queries Garage data
- [Airbyte](airbyte.md) - Writes data to Garage

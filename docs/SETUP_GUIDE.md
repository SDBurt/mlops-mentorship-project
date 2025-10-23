# Kubernetes Lakehouse Platform - Hands-On Learning Guide

This guide walks you through deploying the entire lakehouse platform **manually**, command by command. Each step includes explanations of **what** you're doing, **why** it matters, and **what Kubernetes concepts** are involved.

## Learning Objectives

By completing this guide, you'll understand:
- Kubernetes core concepts: Pods, Services, Namespaces, PersistentVolumes
- Helm package management
- Cross-namespace service communication
- Stateful application deployment
- S3-compatible object storage (Garage)
- Distributed SQL query engines (Trino)

## Overview

You'll deploy these components in order:
1. **Prerequisites**: Helm repos and namespaces
2. **Garage**: S3-compatible object storage (stores Parquet files)
3. **PostgreSQL**: Metadata database (for Airbyte/Dagster)
4. **Airbyte**: Data ingestion platform
5. **Dagster**: Workflow orchestration
6. **Trino**: Distributed SQL query engine

**Estimated time**: 2-3 hours (if reading carefully and understanding each step)

---

## Kubernetes Fundamentals (Quick Reference)

Before starting, here are key Kubernetes concepts you'll encounter:

**Namespace**: A virtual cluster within your Kubernetes cluster. Provides isolation and organization.
- Think of it like a folder that groups related resources
- Prevents name conflicts between different applications

**Pod**: The smallest deployable unit. One or more containers running together.
- Your application runs inside a pod
- Pods are ephemeral (can be created/destroyed)

**Service**: A stable network endpoint to access pods.
- Pods have changing IPs, Services provide consistent DNS names
- Example: `garage.garage.svc.cluster.local`

**PersistentVolumeClaim (PVC)**: Request for storage that survives pod restarts.
- Data persists even if pod is deleted
- Essential for databases and stateful applications

**StatefulSet**: Manages stateful applications (like databases).
- Provides stable pod names (e.g., `postgres-0`)
- Ensures ordered deployment and scaling

**Helm**: Package manager for Kubernetes.
- **Chart**: A package of Kubernetes resource definitions
- **Release**: An installed instance of a chart
- Think of it like apt/yum but for Kubernetes applications

---

## Prerequisites

### 1. Verify Tools

**What you're doing**: Checking that kubectl and Helm are installed and your cluster is accessible.

```bash
# Check kubectl (Kubernetes command-line tool)
kubectl version --client

# Check helm (Kubernetes package manager)
helm version

# Check your cluster is running
kubectl get nodes
```

**Expected output:**
- kubectl: Should show version v1.30+ (your client version)
- helm: Should show version v3.x
- nodes: Should show at least one node with STATUS "Ready" (e.g., docker-desktop)

**What "nodes" means**: Physical or virtual machines in your cluster. Your Docker Desktop setup has 1 node (your local machine).

---

### 2. Add Helm Repositories

**What you're doing**: Adding "app stores" where Helm can download pre-packaged applications.

**Why this matters**: Instead of writing hundreds of lines of Kubernetes YAML, Helm charts provide pre-configured application templates. Think of Helm repos like adding PPAs in Ubuntu or taps in Homebrew.

```bash
# Remove old Airbyte repo if it exists
helm repo remove airbyte 2>/dev/null || true

# Add Airbyte v2 repo (latest version)
helm repo add airbyte-v2 https://airbytehq.github.io/charts

# Add Dagster repo
helm repo add dagster https://dagster-io.github.io/helm

# Add Trino repo
helm repo add trino https://trinodb.github.io/charts

# Update repos to fetch latest chart versions
helm repo update
```

**What each command does:**
- `helm repo add <name> <url>`: Registers a chart repository with a friendly name
- `helm repo update`: Downloads the latest chart listings (like apt update)

**Verification:**
```bash
helm repo list
```

**Expected output**: Should show dagster, airbyte-v2, trino

---

### 3. Fetch Garage Helm Chart

**What you're doing**: Downloading the Garage Helm chart from their git repository.

**Why it's different**: Garage doesn't have a public Helm repository like other tools, so we fetch the chart manually from their source code.

```bash
# Create helm directory
mkdir -p infrastructure/helm

# Clone Garage repo (shallow clone - just latest commit)
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo

# Copy Helm chart to local directory
cp -r /tmp/garage-repo/script/helm/garage infrastructure/helm/garage

# Clean up temporary clone
rm -rf /tmp/garage-repo
```

**What `--depth 1` does**: Only downloads the latest commit, not entire git history. Saves time and bandwidth.

**Verification:**
```bash
ls -la infrastructure/helm/garage/
```

**Expected output**: You should see:
- `Chart.yaml` - Chart metadata (name, version)
- `values.yaml` - Default configuration
- `templates/` - Kubernetes resource templates

---

## Phase 1: Storage Layer (Garage S3)

**Goal**: Deploy S3-compatible object storage to store your data lake files (Parquet format).

**Why Garage?**
- Lightweight S3-compatible storage
- Works great for local development
- Production-ready distributed architecture
- No cloud dependencies

### 1. Create Namespace

**What you're doing**: Creating an isolated "virtual cluster" for Garage resources.

**Why namespaces matter**:
- Keeps Garage separate from other apps
- Prevents name conflicts (multiple apps can have "postgres" service in different namespaces)
- Allows different teams to work independently

```bash
kubectl apply -f infrastructure/kubernetes/namespaces/garage.yaml
```

**What `kubectl apply` does**:
- Creates or updates resources defined in YAML files
- Idempotent (safe to run multiple times)

**Verification:**
```bash
kubectl get namespace garage
```

**Expected output:**
```
NAME     STATUS   AGE
garage   Active   Xs
```

**What STATUS "Active" means**: Namespace is ready for use.

---

### 2. Deploy Garage

**What you're doing**: Installing Garage as a StatefulSet with persistent storage.

```bash
helm upgrade --install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage --create-namespace --wait
```

**Breaking down this command:**
- `helm upgrade --install` - Smart command: install if new, upgrade if exists
- `garage` - Release name (your installation identifier)
- `infrastructure/helm/garage` - Path to the chart
- `-f values.yaml` - Override default settings with your configuration
- `-n garage` - Deploy into the "garage" namespace
- `--create-namespace` - Create namespace if it doesn't exist (safety)
- `--wait` - Don't return until all pods are Running (blocks terminal)

**What gets created:**
1. **StatefulSet** (`garage-0`) - Pod with stable name/storage
2. **Services** - Network endpoints to access Garage
   - `garage` (port 3900: S3 API, port 3902: RPC/Admin API)
   - `garage-headless` (StatefulSet discovery)
3. **PersistentVolumeClaims** - Storage that survives pod restarts
   - `data-garage-0` (10Gi) - Actual S3 object data
   - `meta-garage-0` (1Gi) - Garage metadata

**Verification:**
```bash
# Check pod is running
kubectl get pods -n garage
```

**Expected output:**
```
NAME       READY   STATUS    RESTARTS   AGE
garage-0   1/1     Running   0          30s
```

**What READY "1/1" means**: 1 container running out of 1 container total.

```bash
# Check services exist
kubectl get svc -n garage
```

**Expected output:**
```
NAME              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
garage            ClusterIP   10.x.x.x        <none>        3900/TCP,3902/TCP   30s
garage-headless   ClusterIP   None            <none>        3900/TCP,3902/TCP   30s
```

**What ClusterIP means**: Service accessible only within the Kubernetes cluster (not from outside).

```bash
# Check persistent volumes are bound
kubectl get pvc -n garage
```

**Expected output:**
```
NAME            STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
data-garage-0   Bound    pvc-xxxxx...                              10Gi       RWO            hostpath       30s
meta-garage-0   Bound    pvc-xxxxx...                              1Gi        RWO            hostpath       30s
```

**What STATUS "Bound" means**: PVC successfully attached to a PersistentVolume. Data can be read/written.

**What RWO means**: ReadWriteOnce - volume can be mounted by a single node.

---

### 3. Initialize Garage Cluster

**CRITICAL SECTION**: This is the most important (and non-obvious) step.

**Why initialization is required:**

Garage is a **distributed storage system**. Even though you only have 1 pod now, it's designed to run across multiple nodes in production. Before Garage can store any data, you must:

1. Tell it which nodes should store data
2. Assign storage capacity to each node
3. Configure how data is distributed (partitions)

**Without this step**: Garage pod runs but can't store anything - no storage nodes are configured!

#### Step 3a: Check Cluster Status

**What you're doing**: Viewing the current state of the Garage cluster.

```bash
# Save pod name to variable for convenience
GARAGE_POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')
echo "Garage pod: $GARAGE_POD"

# Run /garage status command inside the pod
kubectl exec -n garage $GARAGE_POD -- /garage status
```

**Breaking down this command:**
- `kubectl exec` - Run a command inside a running pod
- `-n garage` - In the garage namespace
- `$GARAGE_POD` - The pod name (garage-0)
- `--` - Separates kubectl flags from the command to run
- `/garage status` - Garage CLI command (runs inside container)

**Expected output:**
```
==== HEALTHY NODES ====
ID                Hostname  Address         Tags  Zone  Capacity          DataAvail
<node-id>         garage-0  10.x.x.x:3901               NO ROLE ASSIGNED
```

**What this output means:**
- **ID**: Unique node identifier (randomly generated)
- **Hostname**: Pod name (garage-0)
- **Address**: Internal Kubernetes IP + port
- **NO ROLE ASSIGNED**: ⚠️ Node exists but not configured yet!

#### Step 3b: Assign Storage Role

**What you're doing**: Telling Garage this node should store data.

```bash
# Extract node ID from status output
NODE_ID=$(kubectl exec -n garage $GARAGE_POD -- /garage status 2>/dev/null | grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $1}')
echo "Node ID: $NODE_ID"

# Assign storage role with 10GB capacity
kubectl exec -n garage $GARAGE_POD -- /garage layout assign -z garage-dc -c 10G $NODE_ID
```

**Breaking down the layout assign command:**
- `/garage layout assign` - Configure cluster layout
- `-z garage-dc` - Zone name (for multi-datacenter deployments; just a label here)
- `-c 10G` - Capacity: This node can store 10 gigabytes
- `$NODE_ID` - Which node to configure

**What "zone" means**: In production, you might have zones like "us-east", "us-west" for geographic distribution. Garage ensures data is replicated across zones for disaster recovery.

**Expected output:**
```
Role changes are staged but not yet committed.
Use `garage layout show` to view staged role changes,
and `garage layout apply` to enact staged changes.
```

**Why "staged"?** Safety! Like `git commit` vs `git push`, Garage lets you review changes before applying them. This prevents accidental misconfigurations in production.

#### Step 3c: Review Proposed Layout

**What you're doing**: Viewing what will change when you apply the layout.

```bash
kubectl exec -n garage $GARAGE_POD -- /garage layout show
```

**Expected output (annotated):**
```
==== CURRENT CLUSTER LAYOUT ====
No nodes currently have a role in the cluster.
# ^ Nothing configured yet

==== STAGED ROLE CHANGES ====
ID                Tags  Zone       Capacity
<node-id>               garage-dc  10.0 GB
# ^ What you're about to apply

==== NEW CLUSTER LAYOUT AFTER APPLYING CHANGES ====
ID                Tags  Zone       Capacity  Usable capacity
<node-id>               garage-dc  10.0 GB   10.0 GB (100.0%)
# ^ Final state after applying

Zone redundancy: maximum
# ^ With 1 zone, "maximum" redundancy is 1x (no replication)

==== COMPUTATION OF A NEW PARTITION ASSIGNATION ====
Partitions are replicated 1 times on at least 1 distinct zones.
# ^ Each data chunk stored once (you only have 1 node)

Optimal partition size: 39.1 MB
# ^ 10GB / 256 partitions = ~39MB per partition

Usable capacity / total cluster capacity: 10.0 GB / 10.0 GB (100.0 %)
# ^ All capacity is usable

garage-dc           Tags  Partitions        Capacity  Usable capacity
  <node-id>               256 (256 new)     10.0 GB   10.0 GB (100.0%)
  TOTAL                   256 (256 unique)  10.0 GB   10.0 GB (100.0%)
# ^ This node will handle all 256 partitions
```

**What "partitions" mean**:
- Garage splits your data into 256 fixed chunks
- Each file is stored in one of these partitions
- Partitions can be distributed across nodes for load balancing
- With 1 node, all 256 partitions go to that node

**In production with 3 nodes**:
- Each partition would be replicated 3 times (across different nodes)
- If 1 node fails, data remains available on other 2 nodes
- This is how Garage achieves high availability

#### Step 3d: Apply the Layout

**What you're doing**: Committing the staged changes to make the cluster operational.

```bash
# Apply layout version 1
kubectl exec -n garage $GARAGE_POD -- /garage layout apply --version 1
```

**Why `--version 1`?**
- Prevents concurrent modifications (like optimistic locking in databases)
- First layout is always version 1
- If you change layout later, you'd use version 2, 3, etc.
- If someone else tries to apply with wrong version, it fails (safety)

**Expected output:**
```
Version 1 of cluster layout applied.
```

#### Step 3e: Verify Initialization

**What you're doing**: Confirming the node now has a storage role.

```bash
kubectl exec -n garage $GARAGE_POD -- /garage status
```

**Expected output:**
```
==== HEALTHY NODES ====
ID                Hostname  Address         Tags  Zone       Capacity  DataAvail
<node-id>         garage-0  10.x.x.x:3901         garage-dc  10.0 GB   10.0 GB
# ^ NOW SHOWS CAPACITY instead of "NO ROLE ASSIGNED"!
```

**Success!** Your Garage cluster is now ready to store data.

---

### 4. Create S3 Bucket and Access Keys

**What you're doing**: Creating an S3 bucket and credentials to access it.

**Why this matters**:
- Airbyte will write data to this bucket
- Trino will read data from this bucket
- You need access keys (like AWS credentials) to authenticate

```bash
# Create S3 bucket named "lakehouse"
kubectl exec -n garage $GARAGE_POD -- /garage bucket create lakehouse
```

**Expected output:**
```
Bucket lakehouse has been created
```

```bash
# Create access key (like AWS Access Key ID / Secret Access Key)
kubectl exec -n garage $GARAGE_POD -- /garage key create lakehouse-access
```

**Expected output:**
```
Key created:
Name: lakehouse-access
Access Key ID: GKxxxxxxxxxxxxxxxxxxxx
Secret Access Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**🚨 IMPORTANT**: Copy these credentials! You'll need them to configure Airbyte and Trino.

**What these credentials do**: Authenticate API requests to Garage (same as AWS credentials authenticate to S3).

```bash
# Grant read/write permissions to the bucket
kubectl exec -n garage $GARAGE_POD -- /garage bucket allow --read --write lakehouse --key lakehouse-access
```

**What this does**: Authorizes the access key to read and write objects in the "lakehouse" bucket.

```bash
# Verify bucket exists
kubectl exec -n garage $GARAGE_POD -- /garage bucket list
```

**Expected output:**
```
BUCKET      VISIBILITY
lakehouse   private
```

**Verification (Optional):**

Test Garage S3 API using AWS CLI (requires `aws` command installed):

```bash
# Port-forward S3 API to test locally
kubectl port-forward -n garage svc/garage 3900:3900 &
PF_PID=$!
sleep 2

# Configure AWS CLI profile for Garage
# Use the Access Key ID and Secret Access Key from "garage key create lakehouse-access" above
aws configure --profile garage
# AWS Access Key ID: GKxxxxxxxxxxxxxxxxxxxx (your key from above)
# AWS Secret Access Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (your secret from above)
# Default region name: garage (IMPORTANT: must be "garage", not us-east-1)
# Default output format: json

# Test S3 connection
aws s3 ls --endpoint-url http://localhost:3900 --profile garage
# Expected output: 2025-XX-XX XX:XX:XX lakehouse

# List bucket contents
aws s3 ls s3://lakehouse --endpoint-url http://localhost:3900 --profile garage
# Expected output: (empty - no objects yet)

# Stop port-forward
kill $PF_PID
```

**What this does:**
- Port-forward exposes Garage S3 API on localhost:3900 (blocks terminal)
- AWS CLI authenticates using the access key you created
- Region must be `garage` (Garage doesn't use standard AWS regions)
- Connection test verifies bucket access

**Note:** Save your Access Key ID and Secret Access Key when you create them. Garage doesn't show the secret key after creation (like AWS).

---

## Phase 2: Ingestion Layer (Airbyte)

**Goal**: Deploy Airbyte to extract data from sources and load into Garage S3.

**What Airbyte does:**
- Connects to data sources (databases, APIs, files)
- Extracts data incrementally
- Writes to destinations (Garage S3 in Parquet format)
- Tracks sync state in its own embedded PostgreSQL database

### 1. Create Namespace

```bash
kubectl apply -f infrastructure/kubernetes/namespaces/airbyte.yaml
```

---

### 2. Create Airbyte Storage Secrets

**What you're doing**: Configuring Garage S3 credentials for Airbyte's internal storage (logs, state, configuration).

Create `infrastructure/kubernetes/airbyte/airbyte-storage-secrets.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: airbyte-storage-secrets
  namespace: airbyte
type: Opaque
stringData:  # stringData = plain text (Kubernetes auto-encodes to base64)
  # Garage S3 credentials (from Phase 1: garage key create lakehouse-access)
  aws-secret-access-key-id: GKxxxxxxxxxxxxxxxxxxxx  # Your access key ID
  aws-secret-access-key-secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Your secret key
```

**What this is for**: Airbyte stores logs, sync state, and configuration in S3-compatible storage (Garage).

**Note**: Airbyte uses its own embedded PostgreSQL database (deployed automatically by the Helm chart). No separate database setup required.

Apply the secret:

```bash
kubectl apply -f infrastructure/kubernetes/airbyte/airbyte-storage-secrets.yaml
```

---

### 3. Deploy Airbyte

**What you're doing**: Installing Airbyte with all its components.

```bash
helm upgrade --install airbyte airbyte-v2/airbyte \
  --version 2.0.18 \
  -f infrastructure/kubernetes/airbyte/values.yaml \
  -n airbyte --create-namespace --wait --timeout 10m
```

**Why `--timeout 10m`?** Airbyte has many components and can take 5-10 minutes to fully start.

**What gets deployed:**
1. **airbyte-server** - Backend API
2. **airbyte-webapp** - UI frontend
3. **airbyte-worker** - Runs connector jobs
4. **airbyte-temporal** - Workflow orchestration (manages job state)
5. **airbyte-postgresql** - Embedded PostgreSQL database for metadata
6. **airbyte-cron** - Scheduled tasks
7. **airbyte-connector-builder-server** - Build custom connectors

**This takes time**: Watch progress with `kubectl get pods -n airbyte --watch`

---

### 4. Verify Deployment

```bash
# Check all pods
kubectl get pods -n airbyte
```

**Expected output (all Running):**
```
NAME                                              READY   STATUS    RESTARTS   AGE
airbyte-server-xxxxx                              1/1     Running   0          5m
airbyte-webapp-xxxxx                              1/1     Running   0          5m
airbyte-worker-xxxxx                              1/1     Running   0          5m
airbyte-temporal-xxxxx                            1/1     Running   0          5m
airbyte-minio-0                                   1/1     Running   0          5m
airbyte-cron-xxxxx                                1/1     Running   0          5m
airbyte-connector-builder-server-xxxxx            1/1     Running   0          5m
```

**If pods are CrashLooping:**
```bash
# Check logs for errors
kubectl logs -n airbyte <pod-name>
```

**Common issues:**
- Storage secret errors: Verify storage secrets applied (`kubectl get secret airbyte-storage-secrets -n airbyte`)
- PostgreSQL pod not ready: Check embedded database (`kubectl get pods -n airbyte | grep postgresql`)

---

### 5. Access Airbyte UI

**What you're doing**: Forwarding the service port to your local machine.

```bash
# Port-forward Airbyte UI to localhost
# Note: In Airbyte V2, the UI is served by airbyte-server (not a separate webapp)
kubectl port-forward -n airbyte svc/airbyte-airbyte-server-svc 8080:8001
```

**What port-forward does:**
- Maps pod port 8001 → your localhost:8080
- Runs in foreground (blocks terminal)
- Press Ctrl+C to stop

**Why port-forward?**
- Services are only accessible inside cluster by default
- Port-forward creates a tunnel for local access
- In production, you'd use Ingress controller instead

Open browser to: http://localhost:8080

**Initial credentials:**
- Email: admin@example.com
- Password: password

---

## Phase 3: Orchestration Layer (Dagster)

**Goal**: Deploy Dagster to orchestrate DBT transformations and pipelines.

**What Dagster does:**
- Schedules DBT runs
- Tracks data lineage
- Monitors pipeline health
- Manages dependencies between data assets

### 1. Create Namespace

```bash
kubectl apply -f infrastructure/kubernetes/namespaces/dagster.yaml
```

**Note**: Dagster uses its own embedded PostgreSQL database (configured in values.yaml). No separate secrets required for database connection.

---

### 2. Deploy Dagster

```bash
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n dagster --create-namespace
```

**Important**: The install may timeout waiting for user-code deployment, but that's expected. The core components will be running.

**After deployment, scale down the example user-code (you'll deploy your own later):**

```bash
# Scale down the example user-code deployment to 0 replicas
kubectl scale deployment -n dagster dagster-dagster-user-deployments-dagster-user-code --replicas=0
```

**Verify all pods are running:**

```bash
kubectl get pods -n dagster
```

Expected output:
```
NAME                                        READY   STATUS    RESTARTS   AGE
dagster-daemon-xxxxx                        1/1     Running   0          2m
dagster-dagster-webserver-xxxxx             1/1     Running   0          2m
dagster-postgresql-0                        1/1     Running   0          2m
```

**What gets deployed:**
1. **dagster-webserver** - UI and API
2. **dagster-daemon** - Background scheduler
3. **dagster-postgresql** - Dagster's own PostgreSQL for metadata
4. **dagster-user-deployments** - Placeholder (scaled to 0, you'll add your own code later)

**Why scale to 0?**: Dagster requires workspace configuration to start. The example code location will appear in the UI as "unavailable" - this is expected and harmless. You'll deploy your own DBT/Dagster code in Phase 2 to replace it.

**Note**: The workspace configuration tells Dagster what code locations exist, even if they're not currently running. Having an unavailable location is normal in a learning/development environment.

---

### 3. Access Dagster UI

```bash
# Port-forward in separate terminal
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80
```

Open browser to: http://localhost:3000

**What you'll see:**
- **Launchpad**: Manually trigger jobs
- **Assets**: Data assets with lineage graph
- **Runs**: Execution history
- **Schedules**: Automated runs

---

## Phase 4: Query Layer (Trino)

**Goal**: Deploy Trino for distributed SQL queries over Iceberg tables in Garage S3.

**What Trino does:**
- Queries data in Garage S3 (Iceberg tables)
- Distributed query execution
- ANSI SQL interface
- No data movement (queries in place)

### 1-2. Create Namespace and Deploy

```bash
kubectl apply -f infrastructure/kubernetes/namespaces/trino.yaml

helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n trino --create-namespace --wait --timeout 10m
```

**What gets deployed:**
- **trino-coordinator** - Query planner and scheduler
- **trino-workers** - Query executors (distributed)

---

### 3. Access Trino UI

```bash
# Port-forward (use 8081 to avoid conflict with Airbyte on 8080)
kubectl port-forward -n trino svc/trino 8081:8080
```

Open browser to: http://localhost:8081

---

### 4. Test Trino CLI

```bash
# Get coordinator pod name
TRINO_POD=$(kubectl get pods -n trino -l app.kubernetes.io/component=coordinator -o jsonpath='{.items[0].metadata.name}')

# Connect to Trino CLI
kubectl exec -it -n trino $TRINO_POD -- trino

# Inside Trino CLI:
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;
```

**What catalogs are**: Named connections to data sources. The `iceberg` catalog points to your Garage S3 storage.

---

## Validation and Testing

### 1. Check All Services

```bash
# All namespaces
kubectl get namespaces | grep -E 'garage|airbyte|dagster|trino|database'

# All pods
kubectl get pods --all-namespaces | grep -E 'garage|airbyte|dagster|trino|database'

# All services
kubectl get svc --all-namespaces | grep -E 'garage|airbyte|dagster|trino|database'
```

**Success criteria:**
- All pods READY 1/1 and STATUS Running
- All services have CLUSTER-IP assigned
- All PVCs STATUS Bound

---

### 2. Test Cross-Namespace Connectivity

**What you're testing**: Services can reach each other across namespaces using DNS.

```bash
# Test Garage S3 from Trino namespace
TRINO_POD=$(kubectl get pods -n trino -l app=trino,component=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n trino $TRINO_POD -- curl -I http://garage.garage.svc.cluster.local:3900

# Test Garage S3 from Airbyte namespace
AIRBYTE_POD=$(kubectl get pods -n airbyte -l app.kubernetes.io/name=server -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n airbyte $AIRBYTE_POD -- curl -I http://garage.garage.svc.cluster.local:3900
```

**Expected**: Both commands succeed (HTTP 403 or 200 response from Garage S3 API).

---

### 3. Port-Forward All UIs

**Important**: Each port-forward blocks a terminal. Open 3 separate terminals:

```bash
# Terminal 1: Airbyte
kubectl port-forward -n airbyte svc/airbyte-airbyte-webapp-svc 8080:80

# Terminal 2: Dagster
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80

# Terminal 3: Trino
kubectl port-forward -n trino svc/trino 8081:8080
```

**Access:**
- Airbyte: http://localhost:8080
- Dagster: http://localhost:3000
- Trino: http://localhost:8081

---

## Next Steps

Now that your infrastructure is deployed, you can:

1. **Configure Airbyte Data Sources**
   - Add source connectors (Postgres, MySQL, APIs)
   - Configure Garage S3 as destination
   - Set up sync schedules

2. **Create DBT Models**
   - Define Bronze layer (staging views)
   - Build Silver layer (cleaned dimensions)
   - Build Gold layer (star schema facts)

3. **Orchestrate with Dagster**
   - Create assets for DBT models
   - Schedule transformations
   - Monitor data lineage

4. **Query with Trino**
   - Create Iceberg tables in Garage
   - Run analytical queries
   - Build reports

---

## Troubleshooting

### Pod CrashLooping

```bash
# View recent logs
kubectl logs -n <namespace> <pod-name> --tail=100

# Describe pod for events (shows why it's failing)
kubectl describe pod -n <namespace> <pod-name>

# Check resource usage
kubectl top pods -n <namespace>
```

**Look for:**
- "ImagePullBackOff" - Can't download container image
- "CrashLoopBackOff" - Container starts then crashes
- "Pending" - Waiting for resources (PVC, node capacity)

---

### Service Not Accessible

```bash
# Check service has endpoints (backend pods)
kubectl get endpoints -n <namespace>

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -n <namespace> -- nslookup garage.garage.svc.cluster.local
```

---

### PVC Not Binding

```bash
# Check PVC status
kubectl describe pvc -n <namespace> <pvc-name>

# Check available storage classes
kubectl get storageclass

# For Docker Desktop
kubectl get pv
```

**Docker Desktop** uses `hostpath` storage class (local disk).

---

## Summary

**You've deployed:**
- ✅ Garage S3-compatible object storage
- ✅ PostgreSQL metadata database
- ✅ Airbyte data ingestion
- ✅ Dagster orchestration
- ✅ Trino distributed SQL

**Key Kubernetes concepts learned:**
- Namespaces for isolation
- Pods, Services, StatefulSets
- PersistentVolumeClaims for stateful storage
- Cross-namespace DNS (`<service>.<namespace>.svc.cluster.local`)
- Port-forwarding for local access
- Helm for package management

**What makes this a lakehouse:**
- Object storage (Garage) + Table format (Iceberg) = ACID transactions
- Distributed query engine (Trino) = Analytics at scale
- Orchestration (Dagster) + Transformations (DBT) = Data pipelines

**Start experimenting**: Configure your first data source in Airbyte and ingest data to Garage!

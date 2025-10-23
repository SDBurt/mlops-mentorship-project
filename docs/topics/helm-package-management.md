# Helm Package Management

> **AI-Generated Documentation**: This document was automatically generated to support learning and reference purposes. While the content is based on established Helm concepts and this project's architecture, please verify critical details against official Helm documentation and your specific use cases.

## Overview

Helm is the package manager for [Kubernetes](kubernetes-fundamentals.md). It simplifies deploying complex applications by bundling Kubernetes resources (Deployments, Services, ConfigMaps, etc.) into reusable packages called "Charts."

Think of Helm as:
- **apt/yum** for Ubuntu/RedHat - installs software packages
- **npm/pip** for Node.js/Python - manages dependencies
- **Homebrew** for macOS - formulae for applications

Instead of managing hundreds of YAML files manually, Helm charts provide pre-configured application templates with sensible defaults and easy customization.

## Why Helm Matters for This Platform

**Simplified Deployment**: Install [Airbyte](airbyte.md), [Dagster](dagster.md), and [Trino](trino.md) with single commands instead of applying dozens of YAML files manually.

**Version Management**: Easily upgrade services to newer versions or rollback to previous versions if deployments fail.

**Configuration Management**: Override default settings using values files without modifying upstream charts.

**Reproducibility**: Same Helm commands produce consistent deployments across dev, staging, and production environments.

## Key Concepts

### 1. Chart

**What it is**: A packaged application containing all Kubernetes resource definitions needed to run the application.

**Chart structure**:
```
chart-name/
├── Chart.yaml          # Metadata (name, version, description)
├── values.yaml         # Default configuration
├── templates/          # Kubernetes resource templates
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── NOTES.txt      # Post-install instructions
└── charts/            # Dependent charts (sub-charts)
```

**In this project**:
- **Airbyte chart**: Deploys 7+ components (server, worker, webapp, temporal, postgres, etc.)
- **Dagster chart**: Deploys webserver, daemon, postgres, user code deployments
- **Trino chart**: Deploys coordinator and worker pods with catalog configurations
- **Garage chart**: Deploys StatefulSet for distributed S3-compatible storage

**Example - View Chart Structure**:
```bash
# List files in Garage chart
ls -la infrastructure/helm/garage/

# Output:
# Chart.yaml       - Chart metadata
# values.yaml      - Default configuration
# templates/       - Kubernetes resource templates
```

**Chart.yaml example**:
```yaml
apiVersion: v2
name: garage
description: S3-compatible distributed object storage
version: 0.4.0
appVersion: v0.8.0
```

### 2. Release

**What it is**: An installed instance of a chart running in your cluster. One chart can be installed multiple times with different release names.

**Example**:
```bash
# Install Garage chart as "garage" release
helm install garage infrastructure/helm/garage -n garage

# Install same chart again as "garage-dev" release
helm install garage-dev infrastructure/helm/garage -n garage-dev
```

**Release lifecycle**:
1. **Install**: Create new release
2. **Upgrade**: Update existing release to new version or configuration
3. **Rollback**: Revert to previous release version
4. **Uninstall**: Delete release and all resources

**List releases**:
```bash
# All releases across namespaces
helm list --all-namespaces

# Expected output:
# NAME     NAMESPACE   REVISION   STATUS     CHART           APP VERSION
# garage   garage      1          deployed   garage-0.4.0    v0.8.0
# airbyte  airbyte     1          deployed   airbyte-2.0.18  0.50.0
# dagster  dagster     1          deployed   dagster-1.5.0   1.5.0
# trino    trino       1          deployed   trino-0.18.0    430
```

**Understanding release output**:
- **REVISION**: Number of upgrades (1 = initial install, 2 = first upgrade)
- **STATUS**:
  - `deployed` - Successfully installed
  - `failed` - Installation/upgrade failed
  - `pending-install` - Installation in progress
  - `pending-upgrade` - Upgrade in progress

### 3. Repository

**What it is**: A collection of charts hosted at a URL. Like package repositories (apt repos, npm registry), Helm repositories store charts for download.

**In this project**:
```bash
# Add Airbyte repository
helm repo add airbyte-v2 https://airbytehq.github.io/charts

# Add Dagster repository
helm repo add dagster https://dagster-io.github.io/helm

# Add Trino repository
helm repo add trino https://trinodb.github.io/charts

# Update repositories (like apt update)
helm repo update
```

**List configured repositories**:
```bash
helm repo list

# Expected output:
# NAME         URL
# airbyte-v2   https://airbytehq.github.io/charts
# dagster      https://dagster-io.github.io/helm
# trino        https://trinodb.github.io/charts
```

**Search charts in repository**:
```bash
# Search for Airbyte charts
helm search repo airbyte-v2

# Output:
# NAME                    CHART VERSION   APP VERSION   DESCRIPTION
# airbyte-v2/airbyte      2.0.18          0.50.0        Airbyte data integration platform
```

**Note about Garage**: Garage doesn't have a public Helm repository, so we fetch the chart directly from their Git repository:
```bash
# Clone Garage repo (shallow clone)
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo

# Copy chart locally
cp -r /tmp/garage-repo/script/helm/garage infrastructure/helm/garage

# Install from local path
helm install garage infrastructure/helm/garage -n garage
```

### 4. Values File

**What it is**: A YAML file that overrides default chart configurations. Values files enable customization without modifying chart templates.

**Pattern in this project**:
```
infrastructure/kubernetes/<service>/
├── values.yaml         # Custom overrides (actively edited)
└── values-default.yaml # Complete upstream defaults (reference only, never edit)
```

**Example - Garage Values Override**:

**Default values** (in chart's `values.yaml`):
```yaml
replicaCount: 1
persistence:
  data:
    size: 10Gi
  meta:
    size: 1Gi
```

**Custom override** (`infrastructure/kubernetes/garage/values.yaml`):
```yaml
# Override only what you need to change
replicaCount: 3  # Scale to 3 nodes
persistence:
  data:
    size: 100Gi  # Increase data storage
```

**Applying values**:
```bash
helm install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage
```

**Multiple values files** (last file wins):
```bash
helm install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -f infrastructure/kubernetes/garage/values-prod.yaml \
  -n garage
```

**Override single value via CLI**:
```bash
helm install garage infrastructure/helm/garage \
  --set replicaCount=3 \
  --set persistence.data.size=100Gi \
  -n garage
```

**Best practice**: Use values files for permanent configuration, `--set` for temporary overrides.

### 5. Template Engine

**What it is**: Helm uses Go templates to generate Kubernetes YAML dynamically based on values.

**Example template** (`templates/deployment.yaml`):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-server
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
      - name: server
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

**Template variables**:
- `{{ .Release.Name }}` - Release name (e.g., "garage")
- `{{ .Release.Namespace }}` - Target namespace
- `{{ .Values.replicaCount }}` - Value from values.yaml
- `{{ .Chart.Name }}` - Chart name
- `{{ .Chart.Version }}` - Chart version

**Testing templates** (dry run):
```bash
# Render templates without installing
helm template garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml

# Output: Final rendered Kubernetes YAML
```

**Debug template rendering**:
```bash
# Install with debug output
helm install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage --dry-run --debug
```

## Common Helm Commands

### Installation and Upgrades

```bash
# Install new release
helm install <release-name> <chart> -n <namespace>

# Install with custom values
helm install <release-name> <chart> \
  -f values.yaml \
  -n <namespace> --create-namespace

# Install and wait for resources to be ready
helm install <release-name> <chart> \
  -n <namespace> --wait --timeout 10m

# Upgrade existing release
helm upgrade <release-name> <chart> \
  -f values.yaml \
  -n <namespace>

# Install OR upgrade (idempotent)
helm upgrade --install <release-name> <chart> \
  -f values.yaml \
  -n <namespace> --create-namespace --wait
```

**Why `upgrade --install`?**: Used throughout this project because:
- First run: Installs the release
- Subsequent runs: Upgrades existing release
- Idempotent: Safe to run multiple times

### Viewing Releases

```bash
# List releases in namespace
helm list -n <namespace>

# List all releases across all namespaces
helm list --all-namespaces

# Show release status
helm status <release-name> -n <namespace>

# View release history (revisions)
helm history <release-name> -n <namespace>

# Get values used in release
helm get values <release-name> -n <namespace>

# Get all values (including defaults)
helm get values <release-name> -n <namespace> --all

# Get rendered manifests
helm get manifest <release-name> -n <namespace>
```

### Rollbacks and Uninstalls

```bash
# Rollback to previous revision
helm rollback <release-name> -n <namespace>

# Rollback to specific revision
helm rollback <release-name> 2 -n <namespace>

# Uninstall release (delete all resources)
helm uninstall <release-name> -n <namespace>

# Uninstall and keep history (can rollback later)
helm uninstall <release-name> -n <namespace> --keep-history
```

### Repository Management

```bash
# Add repository
helm repo add <name> <url>

# Update repositories (fetch latest chart versions)
helm repo update

# List repositories
helm repo list

# Remove repository
helm repo remove <name>

# Search charts in repositories
helm search repo <keyword>

# Search Helm Hub (public charts)
helm search hub <keyword>
```

## Deployment Patterns in This Platform

### Pattern 1: Managed Chart from Repository

**Used for**: Airbyte, Dagster, Trino (charts maintained by upstream projects)

**Steps**:
1. Add repository:
```bash
helm repo add airbyte-v2 https://airbytehq.github.io/charts
helm repo update
```

2. Create custom values file:
```bash
# infrastructure/kubernetes/airbyte/values.yaml
global:
  storage:
    type: s3
    s3:
      endpoint: http://garage.garage.svc.cluster.local:3900
```

3. Deploy with custom values:
```bash
helm upgrade --install airbyte airbyte-v2/airbyte \
  --version 2.0.18 \
  -f infrastructure/kubernetes/airbyte/values.yaml \
  -n airbyte --create-namespace --wait --timeout 10m
```

**Advantages**:
- Easy upgrades: `helm upgrade airbyte airbyte-v2/airbyte --version 2.0.20`
- Upstream maintains chart
- Community support

### Pattern 2: Local Chart (No Repository)

**Used for**: [Garage](garage.md) (no public Helm repository available)

**Steps**:
1. Fetch chart from Git:
```bash
git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo
cp -r /tmp/garage-repo/script/helm/garage infrastructure/helm/garage
rm -rf /tmp/garage-repo
```

2. Create custom values file:
```bash
# infrastructure/kubernetes/garage/values.yaml
replicaCount: 1
persistence:
  data:
    size: 10Gi
```

3. Deploy from local path:
```bash
helm upgrade --install garage infrastructure/helm/garage \
  -f infrastructure/kubernetes/garage/values.yaml \
  -n garage --create-namespace --wait
```

**Advantages**:
- Full control over chart
- Can modify templates if needed
- Version pinned (commit hash)

**Disadvantages**:
- Manual upgrade process (fetch new chart version)
- No automated security updates

### Pattern 3: Minimal Values Override

**Philosophy**: Keep `values.yaml` small - only override what's necessary.

**Example - Trino values.yaml**:
```yaml
# Only override catalog configuration
coordinator:
  config:
    catalogs:
      iceberg:
        connector.name: iceberg
        hive.metastore.uri: thrift://hive-metastore.database.svc.cluster.local:9083
        iceberg.file-format: PARQUET

worker:
  replicas: 2  # Scale workers
```

**Why minimal overrides?**
- Easier to understand what changed
- Simpler upgrades (fewer conflicts)
- Upstream defaults are usually sensible

**Keep full defaults as reference** (`values-default.yaml`):
```bash
# Fetch full default values from chart
helm show values trino/trino > infrastructure/kubernetes/trino/values-default.yaml
```

## Troubleshooting

### Installation Hangs or Times Out

**Symptom**: `helm install` command hangs or times out

**Check**:
```bash
# Check pod status in target namespace
kubectl get pods -n <namespace>

# View pod logs
kubectl logs -n <namespace> <pod-name>

# Check Helm status
helm status <release-name> -n <namespace>
```

**Common causes**:
- Pods stuck in `Pending` state (PVC not binding, insufficient resources)
- Pods `CrashLoopBackOff` (application error)
- Long startup time (increase `--timeout` value)

**Solution**:
```bash
# Increase timeout for slow-starting applications
helm install airbyte airbyte-v2/airbyte \
  -n airbyte --wait --timeout 15m

# Check events for details
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

### Upgrade Fails with Conflicts

**Symptom**: `helm upgrade` fails with "resource already exists" or similar errors

**Check**:
```bash
# View release history
helm history <release-name> -n <namespace>

# Check if resources were manually modified
kubectl get all -n <namespace> -o yaml | grep "managed-by: Helm"
```

**Common causes**:
- Manual `kubectl apply` created conflicting resources
- Previous upgrade failed mid-flight
- Resource ownership conflict

**Solution**:
```bash
# Force upgrade (use with caution)
helm upgrade <release-name> <chart> \
  -n <namespace> --force

# Or rollback and try again
helm rollback <release-name> -n <namespace>

# Or uninstall and reinstall (loses data!)
helm uninstall <release-name> -n <namespace>
helm install <release-name> <chart> -n <namespace>
```

### Values Not Applied

**Symptom**: Changed values.yaml but deployment still uses old configuration

**Check**:
```bash
# View actual values used in release
helm get values <release-name> -n <namespace>

# Compare with your values file
diff <(helm get values <release-name> -n <namespace>) infrastructure/kubernetes/<service>/values.yaml
```

**Common causes**:
- Forgot to specify `-f values.yaml` in command
- Syntax error in values.yaml (ignored silently)
- Values cached from previous install

**Solution**:
```bash
# Always specify values file explicitly
helm upgrade --install <release-name> <chart> \
  -f infrastructure/kubernetes/<service>/values.yaml \
  -n <namespace>

# Validate values syntax
helm lint infrastructure/helm/<chart> \
  -f infrastructure/kubernetes/<service>/values.yaml

# Dry-run to see rendered templates
helm upgrade --install <release-name> <chart> \
  -f infrastructure/kubernetes/<service>/values.yaml \
  -n <namespace> --dry-run --debug
```

### Chart Version Confusion

**Symptom**: Uncertain which chart version is installed or available

**Check**:
```bash
# List installed releases with versions
helm list -n <namespace>

# Search available chart versions
helm search repo <chart> --versions

# View chart info
helm show chart <repo>/<chart> --version <version>
```

**Solution**:
```bash
# Always pin chart version explicitly
helm upgrade --install airbyte airbyte-v2/airbyte \
  --version 2.0.18 \
  -n airbyte

# Upgrade to specific newer version
helm upgrade airbyte airbyte-v2/airbyte \
  --version 2.0.20 \
  -n airbyte
```

## Integration with Other Components

- **[Kubernetes Fundamentals](kubernetes-fundamentals.md)**: Helm creates Namespaces, Pods, Services, Deployments, StatefulSets
- **[Stateful Applications](stateful-applications.md)**: Helm charts deploy StatefulSets with PVCs for databases
- **[Garage](garage.md)**, **[Airbyte](airbyte.md)**, **[Dagster](dagster.md)**, **[Trino](trino.md)**: All deployed using Helm charts
- **[Kubernetes Storage](kubernetes-storage.md)**: Helm creates PVCs defined in chart templates

## Best Practices

### 1. Always Use `upgrade --install`

**Why**: Idempotent command works for both initial install and updates
```bash
helm upgrade --install <release> <chart> -n <namespace>
```

### 2. Pin Chart Versions

**Why**: Ensures reproducible deployments
```bash
# Good: Explicit version
helm upgrade --install airbyte airbyte-v2/airbyte --version 2.0.18

# Bad: Uses latest (unpredictable)
helm upgrade --install airbyte airbyte-v2/airbyte
```

### 3. Keep Values Files Minimal

**Why**: Easier to maintain and understand

**Good**:
```yaml
# values.yaml - Only overrides
replicaCount: 3
resources:
  limits:
    memory: 4Gi
```

**Bad**:
```yaml
# values.yaml - Copy-pasted entire default values (hundreds of lines)
# ...hard to tell what actually changed...
```

### 4. Use Namespaces for Isolation

**Why**: Multiple releases don't conflict
```bash
helm install garage-prod ./garage -n garage-prod
helm install garage-dev ./garage -n garage-dev
```

### 5. Use `--wait` for Deployments

**Why**: Ensures resources are healthy before command returns
```bash
helm upgrade --install airbyte airbyte-v2/airbyte \
  -n airbyte --wait --timeout 10m
```

### 6. Test Templates Before Deploying

**Why**: Catch errors early
```bash
# Render templates without installing
helm template <release> <chart> -f values.yaml

# Validate chart
helm lint <chart> -f values.yaml

# Dry-run installation
helm install <release> <chart> -f values.yaml --dry-run --debug
```

## References

- [Official Helm Documentation](https://helm.sh/docs/)
- [Helm Chart Template Guide](https://helm.sh/docs/chart_template_guide/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Artifact Hub (Chart Search)](https://artifacthub.io/)
- Project Setup Guide: [SETUP_GUIDE.md](../../SETUP_GUIDE.md)

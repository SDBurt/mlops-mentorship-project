# Polaris RBAC Setup Guide

This guide walks you through initializing Apache Polaris with proper Role-Based Access Control (RBAC) for Dagster and other services.

**Important**: All scripts require bootstrap credentials to be provided via environment variables or command-line flags. Never hardcode credentials in scripts or configuration files.

## Overview

Apache Polaris requires proper RBAC setup before clients can create or access tables. The permission model follows a chain:

```
Principal → Principal Role → Catalog Role → Catalog Privileges
```

**Key Concepts:**
- **Principal**: A unique identity (user or service account)
- **Principal Role**: A label granted to principals
- **Catalog Role**: A label for catalogs that holds privileges
- **Privileges**: Specific permissions (e.g., `CATALOG_MANAGE_CONTENT`, `TABLE_READ_DATA`)

## Quick Start

### 1. Deploy Polaris

First, ensure Polaris is deployed:

```bash
make deploy
```

This will deploy all lakehouse services including Polaris.

**Important**: After deployment, ensure bootstrap credentials are available. These are typically configured in `polaris/values.yaml` or via Kubernetes secrets. Check your deployment configuration for the actual bootstrap credentials.

### 2. Set Bootstrap Credentials

Before initializing Polaris, you need to provide bootstrap credentials:

```bash
# Option 1: Environment variables (recommended)
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"

# Option 2: Command-line flags (see step 3)
```

**Note**: Bootstrap credentials are typically set during Polaris deployment. Check your `polaris/values.yaml` or Kubernetes secrets for the actual values.

### 3. Initialize Polaris RBAC

Run the initialization script:

```bash
# With environment variables (from step 2)
make init-polaris

# Or with command-line flags
make init-polaris BOOTSTRAP_ID=polaris_admin BOOTSTRAP_SECRET=your_secret
```

This script will:
1. Create the `lakehouse` catalog
2. Create a `dagster_user` service account principal
3. Set up the permission chain (principal roles, catalog roles, privileges)
4. Grant `CATALOG_MANAGE_CONTENT` privilege
5. Create namespace: `data` (single namespace for all tables)
6. Save credentials to `infrastructure/kubernetes/polaris/.credentials/dagster_user.txt`

**Alternative**: If you only need to set up RBAC and namespaces (catalog/principal already exist):

```bash
make setup-polaris-rbac
```

### 4. Update Dagster Configuration

After initialization, update the Dagster environment variables:

```bash
# Source the generated credentials
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt

# Display credentials (for copying to set_pyiceberg_env.sh)
cat infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
```

Update [services/dagster/set_pyiceberg_env.sh](../../../services/dagster/set_pyiceberg_env.sh) with the new credentials:

```bash
# Replace the PYICEBERG_CATALOG__DEFAULT__CREDENTIAL line with:
export PYICEBERG_CATALOG__DEFAULT__CREDENTIAL="<client_id>:<client_secret>"
```

### 5. Test Polaris Connectivity

Verify Polaris is accessible:

```bash
# Set bootstrap credentials if not already set
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"

make polaris-test
```

This will test:
- REST API endpoint accessibility
- OAuth token generation (if credentials are provided)
- Authentication with bootstrap credentials

**Note**: If credentials are not set, the OAuth test will be skipped with a warning.

### 6. Run Dagster

Now you can run Dagster and materialize assets:

```bash
cd services/dagster
source set_pyiceberg_env.sh
uv run dagster dev
```

In the Dagster UI (http://localhost:3001), materialize the `reddit_posts` asset. It should now succeed!

## Manual Setup (Without Makefile)

If you prefer to run the script directly:

```bash
# Set bootstrap credentials
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"

# Start port-forward to Polaris
kubectl port-forward -n lakehouse svc/polaris 8181:8181 &

# Run initialization script
chmod +x infrastructure/kubernetes/polaris/init-polaris.sh
./infrastructure/kubernetes/polaris/init-polaris.sh http://localhost:8181

# Or with command-line flags
./infrastructure/kubernetes/polaris/init-polaris.sh \
  --host http://localhost:8181 \
  --bootstrap-client-id polaris_admin \
  --bootstrap-client-secret your_secret

# Source the credentials
source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
```

### Setup RBAC and Namespaces Only

If the catalog and principal already exist, you can set up RBAC and namespaces separately:

```bash
# Set bootstrap credentials
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"

# Start port-forward
kubectl port-forward -n lakehouse svc/polaris 8181:8181 &

# Run RBAC/namespace setup script
chmod +x infrastructure/kubernetes/polaris/setup-rbac-namespaces.sh
./infrastructure/kubernetes/polaris/setup-rbac-namespaces.sh http://localhost:8181
```

## Understanding the RBAC Setup

The initialization script creates the following structure:

```
┌─────────────────────────────────────────────┐
│ Principal: dagster_user (SERVICE)           │
│ Client ID: <generated>                      │
│ Client Secret: <generated>                  │
└──────────────────┬──────────────────────────┘
                   │ granted
                   ↓
┌─────────────────────────────────────────────┐
│ Principal Role: dagster_role                │
└──────────────────┬──────────────────────────┘
                   │ assigned
                   ↓
┌─────────────────────────────────────────────┐
│ Catalog Role: catalog_admin                 │
│ (in lakehouse catalog)                      │
└──────────────────┬──────────────────────────┘
                   │ has privilege
                   ↓
┌─────────────────────────────────────────────┐
│ Privilege: CATALOG_MANAGE_CONTENT           │
│ - Create/read/write all entities            │
│ - Manage tables, views, namespaces          │
└─────────────────────────────────────────────┘
```

## Available Privileges

Polaris supports granular privileges:

### Catalog Privileges
- `CATALOG_MANAGE_CONTENT` - Full management (create/read/write/delete all entities)
- `CATALOG_MANAGE_ACCESS` - Manage access control
- `CATALOG_MANAGE_METADATA` - Manage catalog metadata

### Namespace Privileges
- `NAMESPACE_CREATE` - Create tables/views in namespace
- `NAMESPACE_LIST` - List tables/views
- `NAMESPACE_READ_PROPERTIES` - Read namespace properties

### Table Privileges
- `TABLE_CREATE` - Create tables
- `TABLE_DROP` - Drop tables
- `TABLE_READ_DATA` - Read table data
- `TABLE_WRITE_DATA` - Write/update table data
- `TABLE_READ_PROPERTIES` - Read table properties
- `TABLE_WRITE_PROPERTIES` - Update table properties

### View Privileges
- `VIEW_CREATE` - Create views
- `VIEW_DROP` - Drop views
- `VIEW_READ_PROPERTIES` - Read view properties
- `VIEW_WRITE_PROPERTIES` - Update view properties

## Creating Additional Principals

You can create additional principals for other services (Trino, DBT, BI tools, etc.).

### Example: Create a Read-Only Analyst Principal

```bash
# Set bootstrap credentials (from environment or Kubernetes Secret)
export POLARIS_BOOTSTRAP_CLIENT_ID="${POLARIS_BOOTSTRAP_CLIENT_ID:-polaris_admin}"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="${POLARIS_BOOTSTRAP_CLIENT_SECRET:-}"

# Validate credentials are set
if [ -z "$POLARIS_BOOTSTRAP_CLIENT_SECRET" ]; then
  echo "ERROR: POLARIS_BOOTSTRAP_CLIENT_SECRET must be set"
  exit 1
fi

# Get bootstrap token
BOOTSTRAP_TOKEN=$(curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
   --user "${POLARIS_BOOTSTRAP_CLIENT_ID}:${POLARIS_BOOTSTRAP_CLIENT_SECRET}" \
   -d 'grant_type=client_credentials' \
   -d 'scope=PRINCIPAL_ROLE:ALL' | jq -r .access_token)

# Create principal
curl -X POST http://localhost:8181/api/management/v1/principals \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "name": "analyst_user",
      "type": "SERVICE"
    }
  }'

# Create principal role
curl -X POST http://localhost:8181/api/management/v1/principal-roles \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "principalRole": {
      "name": "analyst_role"
    }
  }'

# Grant principal role to principal
curl -X PUT "http://localhost:8181/api/management/v1/principals/analyst_user/principal-roles/analyst_role" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN"

# Create catalog role
curl -X POST "http://localhost:8181/api/management/v1/catalogs/lakehouse/catalog-roles" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "catalogRole": {
      "name": "read_only_role"
    }
  }'

# Grant catalog role to principal role
curl -X PUT "http://localhost:8181/api/management/v1/catalogs/lakehouse/catalog-roles/read_only_role/principal-roles/analyst_role" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN"

# Grant read-only privileges (TABLE_READ_DATA) on marts namespace
curl -X PUT "http://localhost:8181/api/management/v1/catalogs/lakehouse/catalog-roles/read_only_role/grants" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "namespace",
    "namespace": ["marts"],
    "privilege": "TABLE_READ_DATA"
  }'
```

## Troubleshooting

### Error: "Principal 'X' is not authorized for op Y"

**Cause**: The principal doesn't have the required privilege.

**Solution**:
1. Verify the principal exists: Check `infrastructure/kubernetes/polaris/.credentials/`
2. Re-run RBAC setup: `make setup-polaris-rbac` (idempotent)
3. Or re-run full initialization: `make init-polaris` (idempotent)
4. Check credentials in `set_pyiceberg_env.sh` match the generated credentials

### Error: "Cannot connect to Polaris (HTTP XXX)"

**Cause**: Polaris is not accessible or port-forward is not running.

**Solution**:
```bash
# Check Polaris is running
make polaris-status

# Start port-forward
make port-forward-start

# Test connectivity
make polaris-test
```

### Error: "Failed to create catalog (HTTP 409)"

**Cause**: Catalog already exists (this is non-critical).

**Solution**: The script is idempotent - existing resources are preserved. This warning is safe to ignore.

### Error: "Failed to authenticate with dagster_user"

**Cause**: The dagster_user credentials haven't been generated yet or were regenerated.

**Solution**:
1. Run `make init-polaris` to generate new credentials
2. Source the credentials: `source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt`
3. Update `services/dagster/set_pyiceberg_env.sh` with the new credentials
4. Restart Dagster: `uv run dagster dev`

### Error: "Bootstrap credentials are required!"

**Cause**: The initialization script requires bootstrap credentials to authenticate.

**Solution**:
```bash
# Set environment variables
export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"

# Or use command-line flags
make init-polaris BOOTSTRAP_ID=polaris_admin BOOTSTRAP_SECRET=your_secret
```

### Error: "Namespace creation failed"

**Cause**: Namespaces can only be created by principals with proper privileges.

**Solution**:
1. Ensure RBAC is set up: `make setup-polaris-rbac`
2. Namespaces can also be created via Trino:

```sql
-- Connect to Trino
CREATE SCHEMA lakehouse.data;
```

**Note**: The current architecture uses a single `data` namespace for all tables, organized by naming conventions (e.g., `raw_*`, `staging_*`, `marts_*`).

## Security Best Practices

1. **Never Hardcode Credentials**: Always use environment variables or Kubernetes Secrets
2. **Use Service Accounts**: Always create dedicated service accounts (not `polaris_admin`) for applications
3. **Principle of Least Privilege**: Grant only the minimum privileges required
4. **Rotate Credentials**: Periodically regenerate principal credentials
5. **Audit Access**: Monitor Polaris logs for unauthorized access attempts
6. **Namespace Isolation**: Use separate namespaces for different teams/environments
7. **Bootstrap Credentials**: Store bootstrap credentials in Kubernetes Secrets, not in scripts or config files

## Next Steps

### For Trino Integration

Update [trino/values.yaml](../trino/values.yaml) to use principal credentials instead of bootstrap credentials:

```yaml
env:
  - name: POLARIS_CLIENT_ID
    value: "<dagster_user_client_id>"
  - name: POLARIS_CLIENT_SECRET
    value: "<dagster_user_client_secret>"
```

### For DBT Integration

Update DBT profiles.yml to use OAuth credentials:

```yaml
lakehouse_analytics:
  target: dev
  outputs:
    dev:
      type: trino
      method: oauth
      user: dagster_user
      catalog: lakehouse
      ...
```

### For Phase 3 Governance

1. Create team-specific principals and roles
2. Implement row-level security policies
3. Set up audit log monitoring
4. Document data lineage and access patterns

## Resources

- [Apache Polaris Documentation](https://polaris.apache.org/)
- [Polaris RBAC Guide](https://polaris.apache.org/in-dev/unreleased/entities/)
- [Apache Iceberg REST Catalog Spec](https://iceberg.apache.org/spec/#catalog-api)
- [Project CLAUDE.md](../../../CLAUDE.md) - Project architecture and patterns

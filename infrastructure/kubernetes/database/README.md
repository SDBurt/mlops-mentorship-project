# PostgreSQL Database for Airbyte

This directory contains the Kubernetes manifests for deploying PostgreSQL as a shared database service for Airbyte.

## Components

- **Namespace**: `database`
- **StatefulSet**: `postgres` (single replica for development)
- **Service**: `postgres.database.svc.cluster.local:5432`
- **Storage**: 20GB PersistentVolumeClaim

## Credentials

Stored in `postgres-secret.yaml`:
- Username: `airbyte`
- Password: `airbyte123`
- Database: `airbyte`

## Deployment

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Create secret
kubectl apply -f postgres-secret.yaml

# Deploy PostgreSQL
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f postgres-service.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgres -n database --timeout=300s
```

## Verification

```bash
# Check pod status
kubectl get pods -n database

# Test connection
kubectl exec -n database postgres-0 -- pg_isready -U airbyte

# Connect to database
kubectl exec -it -n database postgres-0 -- psql -U airbyte -d airbyte

# View Airbyte tables
kubectl exec -n database postgres-0 -- psql -U airbyte -d airbyte -c '\dt'
```

## Backup (Manual)

```bash
# Dump database
kubectl exec -n database postgres-0 -- pg_dump -U airbyte airbyte > airbyte_backup.sql

# Restore database
cat airbyte_backup.sql | kubectl exec -i -n database postgres-0 -- psql -U airbyte airbyte
```

## Scaling

For production, consider:
1. Increasing `replicas` to 3 for high availability
2. Using PostgreSQL cluster operators (e.g., Zalando Postgres Operator)
3. Enabling automated backups
4. Using separate databases for different services

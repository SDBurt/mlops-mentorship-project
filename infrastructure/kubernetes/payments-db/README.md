# Payments PostgreSQL Database

Bronze layer PostgreSQL database for payment events. Stores enriched events from Temporal workflows before batch loading to Iceberg.

## Deployment

```bash
# Create secrets first
cp secrets.yaml.example secrets.yaml
# Edit secrets.yaml with your passwords

# Apply secrets and init script
kubectl apply -f secrets.yaml -n lakehouse
kubectl apply -f init-configmap.yaml -n lakehouse

# Install PostgreSQL
helm install payments-db bitnami/postgresql -n lakehouse -f values.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql,app.kubernetes.io/instance=payments-db -n lakehouse --timeout=300s
```

## Service Access

### Internal (Kubernetes)

```
Host: payments-db-postgresql.lakehouse.svc.cluster.local
Port: 5432
Database: payments
User: payments
```

Or within lakehouse namespace:
```
Host: payments-db-postgresql
Port: 5432
```

### External (Port-Forward)

```bash
kubectl port-forward svc/payments-db-postgresql 5433:5432 -n lakehouse
```

Then connect to `localhost:5433`.

## Tables

### payment_events

Bronze table for successfully processed payment events:

| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR(255) | Unique event identifier |
| provider | VARCHAR(50) | Payment provider (stripe, square, etc.) |
| amount_cents | BIGINT | Transaction amount in cents |
| fraud_score | DECIMAL(5,4) | ML fraud score (0-1) |
| churn_score | DECIMAL(5,4) | ML churn score (0-1) |
| retry_strategy | VARCHAR(50) | Recommended retry strategy |
| loaded_to_iceberg | BOOLEAN | Batch ETL tracking flag |

### payment_events_quarantine

Quarantine table for failed/invalid events:

| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR(255) | Event identifier |
| original_payload | JSONB | Raw event data |
| validation_errors | JSONB | List of validation errors |
| reviewed | BOOLEAN | Manual review status |

## Verification

```bash
# Check pod status
kubectl get pods -n lakehouse -l app.kubernetes.io/instance=payments-db

# Connect to database
kubectl exec -it payments-db-postgresql-0 -n lakehouse -- psql -U payments -d payments

# Check tables
\dt

# Count events
SELECT COUNT(*) FROM payment_events;
```

## Environment Variables for Services

```yaml
env:
  POSTGRES_HOST: payments-db-postgresql
  POSTGRES_PORT: "5432"
  POSTGRES_USER: payments
  POSTGRES_DB: payments
  POSTGRES_PASSWORD:
    valueFrom:
      secretKeyRef:
        name: payments-db-secret
        key: password
```

## Backup (Optional)

```bash
# Create backup
kubectl exec payments-db-postgresql-0 -n lakehouse -- \
  pg_dump -U payments payments > backup.sql

# Restore backup
kubectl exec -i payments-db-postgresql-0 -n lakehouse -- \
  psql -U payments payments < backup.sql
```

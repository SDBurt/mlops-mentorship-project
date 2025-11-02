# Polaris Component (lakehouse namespace)

**Purpose:** REST catalog for Apache Iceberg tables (unified metadata, governance)

**Resources:**
- Deployment: `polaris`
- Services: `polaris` (8181), `polaris-management` (8182)

**Configuration:**
- Helm chart: `polaris/polaris` (from GitHub)
- Values: `kubernetes/polaris/values.yaml`
- Secrets: `kubernetes/polaris/secrets.yaml` (gitignored)

**Key Commands:**
```bash
# Deploy
kubectl apply -f kubernetes/polaris/secrets.yaml
git clone https://github.com/apache/polaris.git /tmp/polaris-repo
helm upgrade --install polaris /tmp/polaris-repo/helm/polaris \
  -f kubernetes/polaris/values.yaml \
  -n lakehouse --wait --timeout 10m

# Verify
kubectl get pods -n lakehouse -l app.kubernetes.io/name=polaris

# Access REST API
kubectl port-forward -n lakehouse svc/polaris 8181:8181
# Open: http://localhost:8181

# Health checks
curl http://localhost:8182/q/health/live
curl http://localhost:8182/q/health/ready
```

**Connection Details:**
- REST API: `http://polaris:8181`
- Catalog Endpoint: `http://polaris:8181/api/catalog`
- Management: `http://polaris:8182` (metrics, health)
- Database: Uses Dagster PostgreSQL for metadata storage
- Storage: Uses MinIO S3 for Iceberg table data

**Trino Integration:**
Update Trino catalog to use Polaris REST catalog:
```yaml
# In trino/values.yaml
additionalCatalogs:
  lakehouse: |
    connector.name=iceberg
    iceberg.catalog.type=rest
    iceberg.rest.uri=http://polaris:8181/api/catalog
    iceberg.rest.warehouse=lakehouse
    s3.endpoint=http://minio:9000
    s3.path-style-access=true
```

**Troubleshooting:**
- If pod fails to start: Check database secret and connection
- If Trino can't connect: Verify Polaris service is ready
- View logs: `kubectl logs -n lakehouse -l app.kubernetes.io/name=polaris`

---

See [polaris/README.md](polaris/README.md) for complete deployment guide.

# MLOps Lakehouse Platform - A Mentorship Learning Project

A **hands-on learning journey** from foundational data engineering to production MLOps. This project demonstrates how to build a complete data lakehouse platform on Kubernetes, then extend it with machine learning workflows, feature stores, model serving, and ML governance.

## Project Vision

**Learn by Building**: Start with a solid data platform foundation, then progressively integrate MLOps capabilities. This project showcases the full spectrum of modern data and ML engineering - from raw data ingestion to serving ML models in production.

**End Goal**: A production-ready platform that demonstrates:
- Modern data engineering (batch pipelines, dimensional modeling, data quality)
- MLOps best practices (feature stores, model versioning, automated training)
- Platform engineering (Kubernetes, infrastructure as code, monitoring)
- Data governance (access control, lineage, compliance)

## Learning Path

This project follows a deliberate progression that mirrors real-world platform development:

### Phase 1-2: Data Foundation (Learn First)
**Build the data pipeline infrastructure**
- Deploy Kubernetes services (MinIO, Dagster, Trino)
- Implement batch data ingestion
- Create DBT transformations (Bronze → Silver → Gold)
- Build dimensional models (star schema)
- Master SQL, data modeling, and pipeline orchestration

**Why this matters**: You can't do MLOps without a solid data foundation. Features come from data pipelines.

### Phase 3: Data Governance (Learn Second)
**Add catalog and access control**
- Deploy Polaris REST Catalog for unified metadata
- Implement RBAC for tables and features
- Set up audit logging and lineage tracking
- Learn data governance patterns

**Why this matters**: Production ML requires governance. Who can access features? Who deployed this model?

### Phase 4: MLOps Integration (Learn Third - Primary Goal)
**Extend the platform with ML capabilities**
- Deploy Feast feature store (online + offline)
- Set up Kubeflow for ML pipelines
- Implement DVC for data/model versioning
- Build training pipelines
- Deploy models with KServe
- Monitor model performance

**Why this matters**: This is where data engineering meets machine learning. The ultimate goal of this project.

### Phase 5: Real-Time & Production (Learn Fourth)
**Add streaming and production hardening**
- Kafka/Redpanda for real-time ingestion
- Stream processing with Flink
- Real-time feature computation
- Production monitoring and observability

## Architecture Overview

### Current Focus: Data Pipeline Foundation

```
Data Sources
    ↓
[Meltano] - ELT Ingestion (Singer Taps/Targets)
    ↓
[MinIO S3] - Object Storage (Parquet files)
    ↓
[Apache Iceberg] - Table Format (ACID, Schema Evolution)
    ↓
[DBT] - Transformations (Bronze → Silver → Gold)
    ↓
[Trino] - Query Engine
    ↓
Analytics & BI
```

### Future Goal: MLOps Platform

```
Data Pipeline (above)
    ↓
[Feast] - Feature Store
    ├─→ Online Store (Redis) - Low-latency serving
    └─→ Offline Store (Iceberg) - Training data
         ↓
    [Kubeflow] - ML Pipeline Orchestration
         ├─→ Training Jobs
         ├─→ Hyperparameter Tuning
         └─→ Experiment Tracking
              ↓
    [DVC] - Data & Model Versioning
         ↓
    [Model Registry] - Version Management
         ↓
    [KServe] - Model Serving
         ↓
    Production Predictions
```

## Current Stack

**Infrastructure** (Kubernetes-native):
- **Kubernetes**: Container orchestration (Docker Desktop / minikube)
- **Helm**: Package management for services
- **MinIO**: S3-compatible object storage (lightweight alternative to MinIO)
- **PostgreSQL**: Metadata storage (embedded in Dagster)

**Data Platform**:
- **Meltano**: ELT ingestion via Singer ecosystem (600+ connectors)
- **Apache Iceberg**: Open table format (ACID, time travel, schema evolution)
- **DBT**: SQL-based transformations (medallion architecture)
- **Dagster**: Asset-centric orchestration
- **Trino**: Distributed SQL query engine

**Future MLOps Stack** (Phase 4):
- **Feast**: Feature store (online + offline)
- **Kubeflow**: ML platform (pipelines, notebooks, training)
- **DVC**: Data and model versioning
- **KServe**: Model serving
- **MLflow/Weights & Biases**: Experiment tracking

## My Learning Progress

### Week 1-2: Infrastructure Foundation
**Status**: [x] Complete

**What was Learned**:
- Kubernetes fundamentals (pods, services, namespaces, StatefulSets)
- Helm package management (charts, releases, values files)
- Kubernetes networking (DNS, same-namespace service discovery)
- Persistent storage with PVCs
- Namespace best practices (grouping communicating services)

**Tasks Completed**:
- [x] MinIO S3 storage with cluster initialization
- [x] Dagster with embedded PostgreSQL
- [x] Trino query engine

**Key Challenges Solved**:
- MinIO cluster initialization (non-obvious required step)
- Namespace strategy (single namespace for communicating services)
- StatefulSet storage management with PVCs

**Documentation Created**:
- 18 comprehensive topic guides in [docs/topics/](docs/topics/)
- [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) - Step-by-step deployment
- [TEARDOWN.md](docs/TEARDOWN.md) - Clean uninstall procedures

### Week 3-4: Data Pipeline Implementation
**Status**: 🔄 In Progress

**Current Focus**:
- [ ] Deploy and configure Meltano for data ingestion
- [ ] Add Singer taps for data sources (PostgreSQL, APIs, etc.)
- [ ] Configure target-parquet for MinIO S3
- [ ] Ingest raw data as Parquet files
- [ ] Create Iceberg tables in MinIO S3
- [ ] Configure Trino Iceberg catalog
- [ ] Build DBT project structure
- [ ] Implement Bronze layer (staging views)
- [ ] Implement Silver layer (cleaned dimensions)
- [ ] Implement Gold layer (star schema facts)
- [ ] Test DBT transformations via Trino

**Learning Goals**:
- Master Iceberg table format and operations
- Understand medallion architecture (Bronze/Silver/Gold)
- Learn dimensional modeling (star schema)
- Practice SQL transformations with DBT
- Understand incremental models and partitioning

**Blockers/Questions**:
- _(Record any challenges or questions here)_

**Resources Used**:
- [Apache Iceberg docs](docs/topics/apache-iceberg.md)
- [DBT docs](docs/topics/dbt.md)
- [Medallion Architecture guide](docs/topics/medallion-architecture.md)
- [Star Schema patterns](docs/topics/star-schema.md)

### Week 5-6: Orchestration & Data Quality
**Status**: ⏳ Planned

**Planned Tasks**:
- [ ] Create Dagster assets for DBT models
- [ ] Set up daily refresh schedules
- [ ] Implement data quality tests in DBT
- [ ] Build Dagster sensors for data refreshes
- [ ] Create monitoring dashboards
- [ ] Set up alerting for pipeline failures

**Learning Goals**:
- Dagster asset-centric orchestration
- DBT testing framework
- Pipeline monitoring best practices
- Error handling and retry strategies

### Week 7-8: Data Governance (Phase 3)
**Status**: ⏳ Planned

**Planned Tasks**:
- [ ] Deploy Apache Polaris REST Catalog
- [ ] Migrate Trino to use Polaris catalog
- [ ] Implement RBAC policies for table access
- [ ] Set up audit logging and monitoring
- [ ] Document table lineage
- [ ] Multi-engine catalog sharing

**Learning Goals**:
- Modern REST catalog vs embedded catalogs
- Fine-grained access control for data lakes
- Governance and compliance in production systems
- Centralized metadata management

### Week 9-12: MLOps Integration (Phase 4) - PRIMARY GOAL
**Status**: ⏳ Planned

**Planned Tasks**:
- [ ] Deploy Feast feature store
  - [ ] Configure offline store (Iceberg/MinIO)
  - [ ] Configure online store (Redis)
  - [ ] Define feature views from Gold tables
- [ ] Deploy Kubeflow platform
  - [ ] Set up Kubeflow Pipelines
  - [ ] Create Jupyter notebook environment
  - [ ] Build first training pipeline
- [ ] Set up DVC for versioning
  - [ ] Configure MinIO as remote storage
  - [ ] Version training datasets
  - [ ] Track model artifacts
- [ ] Build ML pipelines
  - [ ] Feature engineering from DBT models
  - [ ] Model training workflow
  - [ ] Hyperparameter tuning with Katib
  - [ ] Model evaluation and validation
- [ ] Deploy model serving
  - [ ] Set up KServe
  - [ ] Deploy first model
  - [ ] Implement A/B testing
- [ ] Implement monitoring
  - [ ] Track model performance
  - [ ] Detect data drift
  - [ ] Alert on degradation

**Learning Goals**:
- Feature store architecture and patterns
- ML pipeline orchestration
- Model versioning and registry
- Production model serving
- ML monitoring and observability

### Phase 5+: Real-Time & Production
**Status**: ⏳ Future

**Topics to Learn**:
- Stream processing with Kafka/Flink
- Real-time feature computation
- Lambda architecture (batch + streaming)
- Production hardening and SRE practices

## Quick Start

### Prerequisites
```bash
# Verify prerequisites
kubectl version --client    # Kubernetes CLI
helm version               # Helm package manager
docker --version          # Docker (for local cluster)
```

### Deploy the Platform

**Step 1: Follow the Setup Guide**
```bash
# Comprehensive step-by-step guide with explanations
cat docs/SETUP_GUIDE.md
```

**Step 2: Deploy Services in Order**
```bash
# Create lakehouse namespace
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# 1. Storage layer (MinIO)
helm upgrade --install minio infrastructure/helm/minio \
  -f infrastructure/kubernetes/minio/values.yaml \
  -n lakehouse --wait

# 2. Orchestration (Dagster)
helm upgrade --install dagster dagster/dagster \
  -f infrastructure/kubernetes/dagster/values.yaml \
  -n lakehouse

# 3. Query engine (Trino)
helm upgrade --install trino trino/trino \
  -f infrastructure/kubernetes/trino/values.yaml \
  -n lakehouse --wait --timeout 10m
```

**Step 3: Access Services**
```bash
# Port-forward UIs (each in separate terminal)
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80
kubectl port-forward -n trino svc/trino 8080:8080
```

- Dagster: http://localhost:3000
- Trino: http://localhost:8080

### Check Status
```bash
# View all deployments
kubectl get pods --all-namespaces | grep -E 'minio|dagster|trino'

# Check specific service
kubectl get pods -n lakehouse -l app.kubernetes.io/name=minio
kubectl logs -n lakehouse minio-0 --tail=100
```

## Project Structure

```
.
├── docs/                          # Comprehensive documentation
│   ├── topics/                   # Detailed topic guides
│   │   ├── kubernetes-fundamentals.md
│   │   ├── minio.md
│   │   ├── dagster.md
│   │   ├── trino.md
│   │   ├── dbt.md
│   │   ├── apache-iceberg.md
│   │   ├── hive-metastore.md
│   │   ├── polaris-rest-catalog.md
│   │   ├── medallion-architecture.md
│   │   ├── star-schema.md
│   │   ├── mlops.md              # Phase 4 guide
│   │   └── ... (more)
│   ├── ARCHITECTURE.md           # Technical deep dive
│   ├── SETUP_GUIDE.md            # Step-by-step deployment
│   └── TEARDOWN.md               # Clean uninstall guide
│
├── infrastructure/               # Platform infrastructure
│   ├── kubernetes/              # K8s manifests and Helm values
│   │   ├── minio/             # S3 storage
│   │   ├── dagster/            # Orchestration
│   │   ├── trino/              # Query engine
│   │   ├── polaris/            # Polaris REST Catalog (Phase 3)
│   │   └── namespace.yaml      # Single lakehouse namespace
│   └── helm/                   # Local Helm charts
│       └── minio/             # MinIO Helm chart
│
├── transformations/             # DBT transformations
│   └── dbt/
│       ├── models/
│       │   ├── sources.yml     # Raw data sources
│       │   ├── bronze/         # Staging views
│       │   ├── silver/         # Cleaned dimensions
│       │   └── gold/           # Star schema facts
│       ├── dbt_project.yml
│       └── profiles.yml        # Trino connection
│
├── orchestration/               # Dagster pipelines
│   └── dagster/
│       ├── assets/             # DBT assets, custom assets
│       ├── jobs/               # Job definitions
│       ├── schedules/          # Schedules
│       └── sensors/            # Sensors (data triggers)
│
├── lakehouse/                   # Iceberg schemas & conventions
│   ├── schemas/
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── conventions/            # Naming standards
│
├── ml/                          # MLOps (Phase 4)
│   ├── feast/                  # Feature store
│   │   ├── features/          # Feature definitions
│   │   └── entities/          # Entity definitions
│   ├── kubeflow/              # ML pipelines
│   │   ├── pipelines/         # Training workflows
│   │   └── components/        # Reusable components
│   ├── models/                # Model code
│   │   ├── training/
│   │   ├── evaluation/
│   │   └── serving/
│   ├── notebooks/             # Jupyter notebooks
│   └── dvc/                   # DVC versioning
│
├── analytics/                   # BI & dashboards (Phase 2+)
│   └── superset/
│
├── CLAUDE.md                   # Project conventions & guidance
└── README.md                   # This file
```

## Key Learning Resources

### Documentation
- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**: Complete deployment walkthrough with explanations
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Technical deep dive into design decisions
- **[docs/topics/](docs/topics/)**: 18 comprehensive guides on every component

### Essential Topics
- [Kubernetes Fundamentals](docs/topics/kubernetes-fundamentals.md)
- [Helm Package Management](docs/topics/helm-package-management.md)
- [Apache Iceberg](docs/topics/apache-iceberg.md)
- [DBT Transformations](docs/topics/dbt.md)
- [Medallion Architecture](docs/topics/medallion-architecture.md)
- [Star Schema Design](docs/topics/star-schema.md)
- [MLOps Overview](docs/topics/mlops.md)

### External Resources
- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [DBT Documentation](https://docs.getdbt.com/)
- [Dagster Documentation](https://docs.dagster.io/)
- [Feast Documentation](https://docs.feast.dev/)
- [Kubeflow Documentation](https://www.kubeflow.org/docs/)

## Mentorship Notes

### What I'm Learning
This project teaches the complete modern data stack:

**Foundation Skills**:
- Kubernetes deployment and management
- Infrastructure as code with Helm
- SQL and dimensional modeling
- Data pipeline orchestration
- Testing and data quality

**Advanced Skills**:
- Apache Iceberg table format
- DBT incremental models and testing
- Asset-centric orchestration with Dagster
- Distributed query optimization with Trino

**MLOps Skills** (Phase 4 focus):
- Feature store architecture
- ML pipeline orchestration
- Model versioning and registry
- Production model serving
- ML monitoring and drift detection

### Challenges & Solutions

**Challenge**: MinIO cluster initialization was not automatic
**Solution**: Must explicitly assign storage roles and apply layout after deployment. Documented in [MinIO guide](docs/topics/minio.md).

**Challenge**: Understanding StatefulSets vs Deployments
**Solution**: StatefulSets provide stable pod names and dedicated storage - critical for databases. See [Stateful Applications](docs/topics/stateful-applications.md).

**Challenge**: Namespace organization for communicating services
**Solution**: Use single `lakehouse` namespace for all services - enables simplified DNS (`service:port`). Follows Kubernetes best practices: services that communicate should live together. See [Kubernetes Networking](docs/topics/kubernetes-networking.md).

### Questions for Mentor
- _(Record questions to discuss during mentorship sessions)_
-
-

### Next Session Goals
- _(Prepare topics to cover in next mentorship session)_
-
-

## Cleanup

```bash
# Uninstall all services (see docs/TEARDOWN.md for details)
helm uninstall dagster -n dagster
helm uninstall trino -n trino
helm uninstall minio -n minio

# Delete namespaces
kubectl delete namespace dagster trino minio
```

## License

This is a personal learning project for mentorship and portfolio purposes.

## Acknowledgments

This project synthesizes concepts and best practices from:
- Apache Iceberg community
- DBT Labs documentation
- Dagster Labs examples
- Kubernetes documentation
- MLOps community resources

Built with guidance from mentors and the data engineering community.

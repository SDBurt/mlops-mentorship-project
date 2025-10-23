# Modern Data Lakehouse Platform

A **learning-focused portfolio project** demonstrating modern data engineering and MLOps practices. Built incrementally from fundamentals to advanced concepts, this platform showcases a complete data lakehouse architecture on Kubernetes with Apache Iceberg, distributed query processing with Trino, and end-to-end orchestration with Dagster.

## Learning Philosophy

This project emphasizes **progressive learning** and **hands-on practice**:

- **Start Simple**: Begin with batch ingestion, basic transformations, and foundational concepts
- **Build Incrementally**: Add complexity layer by layer (batch → real-time, SQL → ML, local → production)
- **Learn by Doing**: Each phase introduces new tools and patterns to master
- **Portfolio Quality**: Demonstrate enterprise best practices suitable for production environments

**Learning Path:**
1. **Phase 1-2**: Master batch data pipelines, SQL transformations, dimensional modeling
2. **Phase 3**: Learn data governance, access control, and compliance
3. **Phase 4**: Explore ML workflows, feature stores, and model serving
4. **Phase 5**: Understand real-time streaming and production operations

## Overview

This platform implements a lakehouse architecture using open table formats (Apache Iceberg) with Parquet storage, enabling ACID transactions, schema evolution, and time travel capabilities. The project is structured as a **monorepo with clear domain separation** to support team collaboration without conflicts.

**Key Features:**
- Modern lakehouse architecture with Apache Iceberg tables
- S3-compatible object storage with Garage
- Custom data integration pipelines with Airbyte
- Orchestration and transformation with Dagster + DBT Core
- Distributed SQL queries with Trino
- Business intelligence with Apache Superset
- Cloud-native deployment on Kubernetes

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
│  (APIs, Databases, Streaming, Files, Custom Connectors)         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Airbyte (Ingestion)                           │
│              Custom Sources & Connectors                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Garage (S3-Compatible Storage)                   │
│                     Parquet Files + Metadata                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Apache Iceberg (Table Format)                   │
│         ACID Transactions, Schema Evolution, Time Travel         │
└──────────┬──────────────────────────────────────┬───────────────┘
           │                                       │
           ▼                                       ▼
┌──────────────────────────┐       ┌──────────────────────────────┐
│  Dagster + DBT Core      │       │    Trino (Query Engine)      │
│  (Orchestration +        │       │  (Distributed SQL Queries)   │
│   Transformation)        │       └──────────────┬───────────────┘
└──────────────────────────┘                      │
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  Apache Superset (Analytics) │
                                   │    Dashboards & BI           │
                                   └──────────────────────────────┘
```

## Current Stack (Phase 1)

**Infrastructure:**
- Kubernetes for container orchestration
- Garage for S3-compatible object storage
- PostgreSQL for metadata storage

**Data Ingestion:**
- Airbyte with custom source connectors
- Support for batch and streaming data

**Storage Layer:**
- Apache Iceberg table format
- Parquet columnar storage
- ACID transactions and schema evolution

**Deployment:**
- Helm charts for service management
- Local development with port-forwarding
- Infrastructure as Code with shell scripts

## Roadmap

### Phase 1: Foundation ✓ (Current)
- [x] Kubernetes cluster setup
- [x] Garage S3-compatible storage
- [x] Airbyte for data ingestion
- [x] Dagster deployment foundation
- [x] Infrastructure automation scripts
- [ ] Apache Iceberg integration
- [ ] Custom Airbyte connectors
- [ ] Initial Parquet data pipelines

### Phase 2: Analytics & Orchestration (In Progress)
- [ ] Dagster orchestration workflows
- [ ] DBT Core for transformations
- [ ] **Star schema dimensional modeling** (fact + dimension tables)
- [ ] Trino for distributed queries
- [ ] Apache Superset for analytics
- [ ] Iceberg table management
- [ ] Data quality framework
- [ ] Pipeline monitoring and alerting

**Learning Goals:**
- Master SQL transformations and medallion architecture
- Understand dimensional modeling (star schema) for analytics
- Learn DBT best practices and testing
- Build production-grade data pipelines

### Phase 3: Data Governance & Catalog (Planned)
- [ ] Apache Polaris catalog for Iceberg
- [ ] Unified catalog with RBAC (role-based access control)
- [ ] Table-level access control policies
- [ ] Row/column-level security in Trino
- [ ] Data lineage visualization
- [ ] Audit logging and compliance
- [ ] Data quality monitoring dashboard
- [ ] PII detection and masking
- [ ] Automated schema validation

### Phase 4: ML/MLOps Integration (Planned)
- [ ] Feast feature store deployment
  - Online store (Redis) for low-latency serving
  - Offline store (Iceberg/Parquet in Garage)
  - Feature registry and versioning
- [ ] Kubeflow ML platform
  - Kubeflow Pipelines for training workflows
  - Jupyter notebooks for data science
  - Model training on Kubernetes
  - Experiment tracking
- [ ] DVC (Data Version Control)
  - ML dataset versioning with Garage backend
  - Model versioning and registry
  - Experiment reproducibility
  - Integration with git workflows
- [ ] Feature engineering pipelines (Dagster + Feast)
- [ ] Model serving infrastructure (KServe)
- [ ] A/B testing framework
- [ ] Model monitoring and drift detection

### Phase 5: Real-Time Streaming (Planned - Learning Focus)
- [ ] **Real-time ingestion architecture** (learning goal)
- [ ] Apache Kafka deployment and concepts
  - Topics, partitions, consumer groups
  - Stream processing fundamentals
  - Kafka Connect for sources
- [ ] Alternative: Redpanda (Kafka-compatible, simpler operations)
- [ ] Stream processing with:
  - Option 1: Flink for complex event processing
  - Option 2: Kafka Streams for simpler use cases
- [ ] Real-time → Iceberg integration
- [ ] Change Data Capture (CDC) patterns
- [ ] Lambda architecture (batch + streaming)
- [ ] Late-arriving data handling

**Learning Goals:**
- Understand stream processing concepts and patterns
- Compare Kafka vs alternatives (Redpanda, Pulsar)
- Learn to handle event-time vs processing-time
- Master exactly-once semantics
- Build unified batch + streaming pipelines

### Phase 6: Production-Ready (Planned)
- [ ] MetalLB for load balancing
- [ ] Traefik ingress controller
- [ ] Prometheus + Grafana monitoring stack
- [ ] Automated backups and disaster recovery
- [ ] Security hardening (network policies, pod security)
- [ ] CI/CD pipelines for pipelines and models
- [ ] Performance optimization and tuning
- [ ] Multi-region deployment
- [ ] Cost optimization and resource management

## Quick Start

### Prerequisites
- Kubernetes cluster (minikube, kind, k3d, or Docker Desktop)
- Docker and Docker Compose
- Helm 3.x
- kubectl configured

### Deploy the Platform

```bash
# Deploy all services
./scripts/deploy-all.sh

# Set up port forwarding
./scripts/port-forward.sh
```

### Access Services

- **Garage S3 API**: http://localhost:3900
- **Garage Admin**: http://localhost:3903
- **Airbyte UI**: http://localhost:8080
- **Dagster UI**: http://localhost:3000

### Check Status

```bash
./scripts/status.sh              # View all deployments
./scripts/logs.sh <service>      # View service logs
```

## Project Structure

**Monorepo with Domain Separation** - Organized so team members can work independently without conflicts:

```
.
├── scripts/                    # Shared deployment scripts
│   ├── deploy-all.sh
│   ├── deploy-garage.sh
│   ├── deploy-airbyte.sh
│   ├── deploy-dagster.sh
│   ├── port-forward.sh
│   └── status.sh
│
├── infrastructure/             # Infrastructure team domain
│   ├── kubernetes/            # K8s manifests and Helm values
│   │   ├── garage/           # S3-compatible storage
│   │   │   ├── values.yaml
│   │   │   ├── values-default.yaml
│   │   │   └── secrets.yaml (gitignored)
│   │   ├── airbyte/          # Data ingestion
│   │   ├── dagster/          # Orchestration
│   │   ├── trino/            # Query engine (Phase 2)
│   │   ├── superset/         # BI tool (Phase 2)
│   │   └── namespaces/       # K8s namespace definitions
│   ├── docker/               # Docker Compose services
│   └── scripts/              # Setup and cleanup
│
├── ingestion/                  # Data ingestion team domain
│   ├── airbyte/              # Custom Airbyte connectors
│   │   ├── source-custom-api/
│   │   └── connector-configs/
│   └── streaming/            # Real-time ingestion (Phase 5)
│       ├── kafka/            # Kafka configurations
│       └── flink/            # Stream processing jobs
│
├── orchestration/              # Orchestration team domain
│   ├── dagster/              # Dagster pipelines
│   │   ├── assets/          # Software-defined assets
│   │   ├── jobs/            # Job definitions
│   │   ├── schedules/       # Schedule definitions
│   │   ├── sensors/         # Sensor definitions
│   │   └── resources/       # Resource configurations
│   └── tests/               # Pipeline tests
│
├── transformations/            # Analytics engineering team domain
│   ├── dbt/                 # DBT transformation models
│   │   ├── models/
│   │   │   ├── staging/    # Bronze → Silver
│   │   │   ├── intermediate/ # Business logic
│   │   │   └── marts/      # Silver → Gold (star schema)
│   │   │       ├── core/   # Core business entities
│   │   │       ├── finance/ # Finance mart
│   │   │       └── marketing/ # Marketing mart
│   │   ├── tests/          # DBT tests
│   │   ├── macros/         # Reusable SQL macros
│   │   └── analyses/       # Ad-hoc analyses
│   └── sql/                # Standalone SQL scripts
│
├── lakehouse/                  # Data modeling team domain
│   ├── schemas/              # Iceberg table schemas
│   │   ├── bronze/          # Raw data schemas
│   │   ├── silver/          # Cleaned data schemas
│   │   └── gold/            # Analytics schemas (star schema)
│   ├── conventions/         # Naming conventions
│   └── migrations/          # Schema migrations
│
├── ml/                         # ML engineering team domain (Phase 4)
│   ├── feast/               # Feature store definitions
│   │   ├── features/       # Feature views
│   │   └── entities/       # Entity definitions
│   ├── kubeflow/            # ML pipeline definitions
│   │   ├── pipelines/      # Training pipelines
│   │   └── components/     # Reusable components
│   ├── models/              # Model code and experiments
│   │   ├── training/       # Training scripts
│   │   ├── evaluation/     # Evaluation scripts
│   │   └── serving/        # Model serving code
│   ├── notebooks/           # Jupyter notebooks
│   └── dvc/                 # DVC configuration
│       ├── .dvc/
│       └── dvc.yaml        # DVC pipeline definitions
│
├── analytics/                  # BI/Analytics team domain
│   ├── superset/            # Superset dashboards
│   │   ├── dashboards/     # Dashboard exports
│   │   └── datasets/       # Dataset definitions
│   └── reports/            # Scheduled reports
│
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md       # Technical architecture
│   ├── data-modeling.md      # Data modeling guide
│   ├── team-structure.md     # Team collaboration guide
│   └── onboarding.md         # New member onboarding
│
└── README.md                  # Project overview

```

**Team Domains and Responsibilities:**

| Domain | Team | Focus Area | Primary Tools |
|--------|------|-----------|---------------|
| `infrastructure/` | Platform/DevOps | K8s, deployments, infrastructure | Helm, kubectl |
| `ingestion/` | Data Engineering | Source connectors, CDC, streaming | Airbyte, Kafka |
| `orchestration/` | Data Engineering | Pipeline orchestration, scheduling | Dagster |
| `transformations/` | Analytics Engineering | SQL transformations, data quality | DBT, SQL |
| `lakehouse/` | Data Architecture | Schema design, data modeling | Iceberg, SQL |
| `ml/` | ML Engineering | Features, training, serving | Feast, Kubeflow, Python |
| `analytics/` | Analytics/BI | Dashboards, reporting | Superset, SQL |

**Collaboration Patterns:**
- Teams work in their own directories with minimal cross-domain PRs
- Shared contracts: Iceberg table schemas in `lakehouse/schemas/`
- Integration points: Dagster orchestrates across all domains
- Code ownership: CODEOWNERS file defines team responsibilities

## Working with the Platform

### Airbyte - Data Ingestion

1. Access UI at http://localhost:8080
2. Configure custom source connectors
3. Set up destinations (Garage/S3)
4. Define sync schedules and transformations
5. Monitor data pipeline health

### Garage - Object Storage

Initialize and configure S3-compatible storage:

```bash
# Get pod name
POD=$(kubectl get pods -n garage -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}')

# Check cluster status
kubectl exec -n garage $POD -- garage status

# Create S3 access credentials
kubectl exec -n garage $POD -- garage key new --name lakehouse-access
```

### Iceberg Tables

Data is stored as Iceberg tables with Parquet files, providing:
- ACID transactions
- Schema evolution without rewrites
- Time travel and rollback capabilities
- Partition evolution
- Hidden partitioning

See `lakehouse/README.md` for table conventions and best practices.

### Dagster - Orchestration

Dagster orchestrates the entire data platform:

```bash
# Initialize Dagster project (first time)
cd orchestration/
dagster project scaffold --name data-platform

# Develop locally
dagster dev
```

See `orchestration/README.md` for pipeline development guide.

## Development Workflow

### Creating Data Pipelines

1. **Ingest** - Configure Airbyte sources and connectors
2. **Store** - Write Parquet files to Garage/S3
3. **Catalog** - Register as Iceberg tables
4. **Transform** - Build DBT models
5. **Orchestrate** - Schedule with Dagster
6. **Query** - Access via Trino
7. **Visualize** - Create Superset dashboards

### Best Practices

- Use Iceberg for all analytical tables
- Store raw data in Parquet format
- Implement medallion architecture (bronze/silver/gold layers)
- Version control all pipelines and transformations
- Test data quality at each stage
- Monitor pipeline performance and SLAs
- Document data lineage

## MLOps Integration (Phase 4)

This platform will integrate comprehensive ML capabilities:

### Feature Store (Feast)
- **Online Store**: Redis for low-latency feature serving (<10ms)
- **Offline Store**: Iceberg tables in Garage for training data
- **Feature Registry**: Versioned feature definitions
- **Integration**: Dagster orchestrates feature materialization from Iceberg → Feast

### ML Platform (Kubeflow)
- **Kubeflow Pipelines**: Training workflow orchestration
- **Notebooks**: JupyterHub for data science workloads
- **Training**: Distributed training on Kubernetes (TensorFlow, PyTorch)
- **Experiments**: MLflow integration for tracking
- **Integration**: Reads from Iceberg, writes models to Garage/S3

### Data Versioning (DVC)
- **Dataset Versioning**: Track training datasets in git + Garage
- **Model Registry**: Version ML models with metadata
- **Reproducibility**: Recreate any experiment from version history
- **Integration**: Uses Garage S3 as remote storage backend

### ML Data Flow
```
Iceberg Tables (Gold Layer)
    ↓
Feature Engineering (Dagster + DBT)
    ↓
Feast Feature Store
    ├─→ Online Store (Redis) → Model Serving (KServe)
    └─→ Offline Store (Iceberg) → Training (Kubeflow)
                                        ↓
                                   DVC Versioning
                                        ↓
                                   Model Registry
                                        ↓
                                   Deployment
```

## Technical Highlights

### Why Iceberg?

- **ACID Transactions**: Consistent reads and writes
- **Schema Evolution**: Add/remove/rename columns without rewrites
- **Time Travel**: Query historical data snapshots
- **Partition Evolution**: Change partitioning without data migration
- **Performance**: Metadata-based query planning

### Why Garage?

- Lightweight S3-compatible storage
- Self-hosted alternative to cloud object storage
- Perfect for local development and testing
- Production-ready distributed architecture

### Why Dagster + DBT?

- Native DBT integration in Dagster
- Asset-centric orchestration
- Software-defined assets
- Built-in data lineage
- Comprehensive testing framework

## Configuration

See `ARCHITECTURE.md` for detailed configuration guides including:
- Iceberg catalog configuration
- Garage S3 credentials and policies
- Trino connector setup
- DBT profiles and models
- Superset data source connections

## Monitoring and Logs

```bash
# View service logs
./scripts/logs.sh garage
./scripts/logs.sh airbyte
./scripts/logs.sh dagster

# Check resource usage
kubectl top pods -n garage
kubectl top pods -n airbyte
kubectl top pods -n dagster

# View all deployments
./scripts/status.sh
```

## Cleanup

```bash
cd infrastructure/scripts
./cleanup.sh
```

## Resources

- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [Garage Documentation](https://garagehq.deuxfleurs.fr/documentation/)
- [Airbyte Documentation](https://docs.airbyte.com/)
- [Dagster Documentation](https://docs.dagster.io/)
- [DBT Documentation](https://docs.getdbt.com/)
- [Trino Documentation](https://trino.io/docs/current/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)

## License

This is a portfolio project for demonstration purposes.

## Contact

For questions or collaboration opportunities, please reach out via the repository.

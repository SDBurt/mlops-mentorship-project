# Project Structure Review: Multi-Team MLOps Organization

*Reviewed: 2025-12-28*

## Current Structure

```
mlops-mentorship-project/
├── payment-pipeline/          # 3 services in 1 package (gateway, normalizer, orchestrator)
├── orchestration-dagster/     # Batch orchestration + ML training
├── orchestration-dbt/         # SQL transformations
├── mlops/feature-store/       # Feast configuration
├── infrastructure/            # Docker + Kubernetes configs
├── docs/
└── Makefile                   # 1000+ lines orchestrating everything
```

## Issues Identified

| Issue | Impact |
|-------|--------|
| **Shared Makefile** | All teams modify same file, merge conflicts |
| **No shared contracts** | Schema changes break downstream silently |
| **Mixed concerns in payment-pipeline** | 3 services, 4 providers = 12 combinations in one package |
| **Infrastructure coupled to services** | Can't deploy services independently |
| **No versioning between services** | Breaking changes propagate immediately |

## Recommended Target Structure

```
mlops-platform/
├── services/                        # All deployable services
│   ├── gateway/                     # Payment webhook receiver
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── normalizer/                  # Kafka validation/transform
│   ├── orchestrator/                # Temporal workflows
│   ├── inference/                   # ML scoring API
│   ├── dagster/                     # Batch orchestration
│   └── feast/                       # Feature store
│
├── dbt/                             # SQL transformations (not a service)
│   ├── models/
│   ├── macros/
│   └── dbt_project.yml
│
├── contracts/                       # Shared schemas - THE KEY ADDITION
│   ├── schemas/
│   │   ├── payment_event.py         # Pydantic: Kafka message schema
│   │   ├── normalized_event.py      # Pydantic: Normalized output
│   │   └── features.py              # Pydantic: Feature vectors
│   └── sql/
│       └── payment_events.sql       # DDL for bronze tables
│
├── infrastructure/
│   ├── docker/
│   │   ├── compose.yml
│   │   └── configs/
│   └── kubernetes/
│
├── scripts/
├── docs/
├── Makefile
└── README.md
```

## Key Changes Summary

| Current | Proposed | Why |
|---------|----------|-----|
| `payment-pipeline/src/` with 3 services | `services/{gateway,normalizer,orchestrator}/` | Each service is independently deployable |
| Schemas scattered in code | `contracts/schemas/` | Single source of truth |
| `orchestration-dagster/` | `services/dagster/` | Consistent naming |
| `orchestration-dbt/dbt/` | `dbt/` | DBT isn't a service, don't nest it |
| `mlops/feature-store/` | `services/feast/` | Consistent with other services |

## Migration Plan (When Ready)

### Phase 1: Create contracts/ folder
1. Create `contracts/schemas/` with Pydantic models
2. Extract schemas from normalizer, orchestrator, dagster
3. Update imports

### Phase 2: Flatten service structure
1. Move services from `payment-pipeline/src/` to `services/`
2. Move `orchestration-dagster/` to `services/dagster/`
3. Move `mlops/feature-store/` to `services/feast/`

### Phase 3: Flatten DBT
1. Move `orchestration-dbt/dbt/` to `dbt/`

### Phase 4: Update Makefile and Docker Compose
1. Update all paths

## Portfolio Value

This structure demonstrates:
1. **Service-oriented architecture** - Each service is independently deployable
2. **Contract-first design** - Shared schemas prevent breaking changes
3. **Clean separation** - DBT is data transformation, not a service
4. **Production patterns** - Same structure used at scale companies

# Payment Pipeline Architecture Diagrams

This document provides visual representations of the payment pipeline system architecture.

## Table of Contents

### Payment Pipeline
- [System Overview](#system-overview)
- [Data Flow](#data-flow)
- [Provider-Specific Containers](#provider-specific-containers)
- [Kafka Topic Flow](#kafka-topic-flow)
- [Temporal Orchestration](#temporal-orchestration)
- [Temporal Activity Flow](#temporal-activity-flow)

### Infrastructure
- [Docker Compose Services](#docker-compose-services)
- [Network Architecture](#network-architecture)
- [Deployment Profiles](#deployment-profiles)

### Data Models
- [Unified Event Schema](#unified-event-schema)

### Lakehouse Integration
- [Lakehouse Integration](#lakehouse-integration)
- [Polaris Catalog Architecture](#polaris-catalog-architecture)
- [Dagster Iceberg Integration](#dagster-iceberg-integration)
- [Trino Iceberg Connector](#trino-iceberg-connector)
- [DBT Transformation Flow](#dbt-transformation-flow)
- [MinIO Storage Layout](#minio-storage-layout)
- [Dagster Asset Lineage](#dagster-asset-lineage)
- [Connection Configuration Summary](#connection-configuration-summary)

---

## System Overview

High-level view of the entire payment processing pipeline from webhook ingestion to data lakehouse.

```mermaid
flowchart TB
    subgraph External["External Payment Providers"]
        Stripe[Stripe]
        Square[Square]
        Adyen[Adyen]
        Braintree[Braintree]
    end

    subgraph Ingestion["Webhook Ingestion Layer"]
        Traefik[Traefik Reverse Proxy<br/>:8000]
        subgraph Gateways["Provider Gateways"]
            SG[Stripe Gateway]
            SQG[Square Gateway]
            AG[Adyen Gateway]
            BG[Braintree Gateway]
        end
    end

    subgraph Streaming["Streaming Layer"]
        Kafka[(Apache Kafka)]
    end

    subgraph Processing["Processing Layer"]
        subgraph Normalizers["Provider Normalizers"]
            SN[Stripe Normalizer]
            SQN[Square Normalizer]
            AN[Adyen Normalizer]
            BN[Braintree Normalizer]
        end
    end

    subgraph Orchestration["Orchestration Layer"]
        Temporal[Temporal Server]
        Orchestrator[Payment Orchestrator]
        Inference[Inference Service<br/>Fraud/Churn/Retry]
    end

    subgraph Storage["Storage Layer"]
        PostgreSQL[(PostgreSQL<br/>Bronze Events)]
        subgraph Lakehouse["Data Lakehouse"]
            Dagster[Dagster]
            Iceberg[(Apache Iceberg)]
            Trino[Trino]
        end
    end

    External --> Traefik
    Traefik --> Gateways
    Gateways --> Kafka
    Kafka --> Normalizers
    Normalizers --> Kafka
    Kafka --> Orchestrator
    Orchestrator <--> Temporal
    Orchestrator --> Inference
    Orchestrator --> PostgreSQL
    PostgreSQL --> Dagster
    Dagster --> Iceberg
    Iceberg --> Trino
```

---

## Data Flow

Detailed view of how payment events flow through the system with topic names.

```mermaid
flowchart LR
    subgraph Webhooks["Incoming Webhooks"]
        W1[payment_intent.succeeded]
        W2[charge.captured]
        W3[refund.created]
    end

    subgraph Gateway["Gateway Layer"]
        GW[Payment Gateway<br/>Signature Verification]
        DLQ1[webhooks.dlq]
    end

    subgraph RawTopics["Raw Kafka Topics"]
        T1[webhooks.stripe.payment_intent]
        T2[webhooks.stripe.charge]
        T3[webhooks.stripe.refund]
        T4[webhooks.square.payment]
        T5[webhooks.square.refund]
        T6[webhooks.adyen.notification]
        T7[webhooks.braintree.notification]
    end

    subgraph Normalizer["Normalizer Layer"]
        NM[Schema Normalization<br/>Validation]
        DLQ2[payments.validation.dlq]
    end

    subgraph NormalizedTopic["Normalized Topic"]
        NT[payments.normalized]
    end

    subgraph Orchestrator["Orchestrator Layer"]
        ORC[Temporal Workflows]
    end

    subgraph Enrichment["ML Enrichment"]
        INF[Inference Service]
        FS[Fraud Score]
        CS[Churn Score]
        RS[Retry Strategy]
    end

    subgraph Persistence["Persistence"]
        PG[(PostgreSQL)]
    end

    Webhooks --> GW
    GW -->|valid| RawTopics
    GW -->|invalid signature| DLQ1
    RawTopics --> NM
    NM -->|valid| NT
    NM -->|validation failed| DLQ2
    NT --> ORC
    DLQ2 --> ORC
    ORC --> INF
    INF --> FS
    INF --> CS
    INF --> RS
    ORC --> PG
```

---

## Provider-Specific Containers

Architecture showing independent scaling of provider-specific containers.

```mermaid
flowchart TB
    subgraph Internet["Internet"]
        Client[Payment Provider Webhooks]
    end

    subgraph Traefik["Traefik Reverse Proxy :8000"]
        Router{Path Router}
    end

    subgraph StripeStack["Stripe Stack"]
        SG[stripe-gateway]
        SN[stripe-normalizer]
        ST1[webhooks.stripe.payment_intent]
        ST2[webhooks.stripe.charge]
        ST3[webhooks.stripe.refund]
    end

    subgraph SquareStack["Square Stack"]
        SQG[square-gateway]
        SQN[square-normalizer]
        SQT1[webhooks.square.payment]
        SQT2[webhooks.square.refund]
    end

    subgraph AdyenStack["Adyen Stack"]
        AG[adyen-gateway]
        AN[adyen-normalizer]
        AT1[webhooks.adyen.notification]
    end

    subgraph BraintreeStack["Braintree Stack"]
        BG[braintree-gateway]
        BN[braintree-normalizer]
        BT1[webhooks.braintree.notification]
    end

    subgraph Output["Unified Output"]
        Normalized[payments.normalized]
    end

    Client --> Router
    Router -->|/webhooks/stripe/*| SG
    Router -->|/webhooks/square/*| SQG
    Router -->|/webhooks/adyen/*| AG
    Router -->|/webhooks/braintree/*| BG

    SG --> ST1
    SG --> ST2
    SG --> ST3
    ST1 --> SN
    ST2 --> SN
    ST3 --> SN

    SQG --> SQT1
    SQG --> SQT2
    SQT1 --> SQN
    SQT2 --> SQN

    AG --> AT1
    AT1 --> AN

    BG --> BT1
    BT1 --> BN

    SN --> Normalized
    SQN --> Normalized
    AN --> Normalized
    BN --> Normalized
```

---

## Kafka Topic Flow

Visualization of all Kafka topics and their producers/consumers.

```mermaid
flowchart LR
    subgraph Producers["Producers"]
        SG[stripe-gateway]
        SQG[square-gateway]
        AG[adyen-gateway]
        BG[braintree-gateway]
        SN[stripe-normalizer]
        SQN[square-normalizer]
        AN[adyen-normalizer]
        BN[braintree-normalizer]
    end

    subgraph Topics["Kafka Topics"]
        subgraph StripeTopics["Stripe Topics"]
            T1[webhooks.stripe.payment_intent]
            T2[webhooks.stripe.charge]
            T3[webhooks.stripe.refund]
        end
        subgraph SquareTopics["Square Topics"]
            T4[webhooks.square.payment]
            T5[webhooks.square.refund]
        end
        subgraph AdyenTopics["Adyen Topics"]
            T6[webhooks.adyen.notification]
        end
        subgraph BraintreeTopics["Braintree Topics"]
            T7[webhooks.braintree.notification]
        end
        subgraph OutputTopics["Output Topics"]
            T8[payments.normalized]
            T9[payments.validation.dlq]
        end
        subgraph DLQ["Dead Letter Queue"]
            T10[webhooks.dlq]
        end
    end

    subgraph Consumers["Consumers"]
        ORC[orchestrator]
    end

    SG --> T1 & T2 & T3
    SQG --> T4 & T5
    AG --> T6
    BG --> T7

    T1 & T2 & T3 --> SN
    T4 & T5 --> SQN
    T6 --> AN
    T7 --> BN

    SN & SQN & AN & BN --> T8
    SN & SQN & AN & BN -.->|validation errors| T9
    SG & SQG & AG & BG -.->|signature errors| T10

    T8 --> ORC
    T9 --> ORC
```

---

## Temporal Orchestration

Workflow execution in Temporal for payment processing.

```mermaid
flowchart TB
    subgraph Input["Input"]
        Kafka[payments.normalized]
        DLQ[payments.validation.dlq]
    end

    subgraph Consumer["Kafka Consumer"]
        KC[Orchestrator Consumer]
    end

    subgraph Temporal["Temporal Server"]
        subgraph PaymentWorkflow["PaymentEventWorkflow"]
            V[validate_business_rules]
            F[get_fraud_score]
            R[get_retry_strategy]
            C[get_churn_prediction]
            P[persist_to_postgres]
        end
        subgraph DLQWorkflow["DLQReviewWorkflow"]
            Q[persist_to_quarantine]
        end
    end

    subgraph Inference["Inference Service"]
        FS["POST /fraud/score"]
        RS["POST /retry/strategy"]
        CS["POST /churn/predict"]
    end

    subgraph Storage["PostgreSQL"]
        PE[(payment_events)]
        PQ[(payment_events_quarantine)]
    end

    Kafka --> KC
    DLQ --> KC
    KC -->|valid events| PaymentWorkflow
    KC -->|invalid events| DLQWorkflow

    V --> F
    F --> FS
    V --> R
    R --> RS
    V --> C
    C --> CS
    F --> P
    R --> P
    C --> P
    P --> PE

    Q --> PQ
```

---

## Temporal Activity Flow

Detailed view of activity execution based on payment status.

```mermaid
flowchart TB
    Start([Payment Event]) --> Validate[validate_business_rules]

    Validate -->|valid| CheckStatus{Payment Status?}
    Validate -->|invalid| Reject[Reject Event]

    CheckStatus -->|succeeded| FraudPath[get_fraud_score]
    CheckStatus -->|failed| RetryPath[get_retry_strategy]

    FraudPath --> ChurnPath[get_churn_prediction]
    RetryPath --> ChurnPath

    ChurnPath --> Persist[persist_to_postgres]

    Persist --> End([Workflow Complete])
    Reject --> DLQ[Send to DLQ]

    subgraph Enrichment["Enriched Fields"]
        E1[fraud_score: 0.0-1.0]
        E2[retry_strategy: immediate/delayed/none]
        E3[churn_score: 0.0-1.0]
    end

    FraudPath -.-> E1
    RetryPath -.-> E2
    ChurnPath -.-> E3
```

---

## Docker Compose Services

Overview of all Docker Compose services and their profiles.

```mermaid
flowchart TB
    subgraph Core["Core Services (always running)"]
        Kafka[kafka-broker]
        Polaris[polaris]
        Minio[minio]
        Trino[trino]
        Postgres[postgres]
    end

    subgraph Dagster["Dagster (always running)"]
        DUC[dagster-user-code]
        DWS[dagster-webserver]
        DD[dagster-daemon]
    end

    subgraph Gateway["Profile: gateway"]
        Traefik[traefik]
        SG[stripe-gateway]
        SQG[square-gateway]
        AG[adyen-gateway]
        BG[braintree-gateway]
    end

    subgraph Normalizer["Profile: normalizer"]
        SN[stripe-normalizer]
        SQN[square-normalizer]
        AN[adyen-normalizer]
        BN[braintree-normalizer]
    end

    subgraph Simulator["Profile: simulator"]
        SS[stripe-simulator]
        SQS[square-simulator]
        AS[adyen-simulator]
        BS[braintree-simulator]
    end

    subgraph Orchestrator["Profile: orchestrator"]
        Temporal[temporal]
        TUI[temporal-ui]
        TDB[temporal-db]
        PDB[payments-db]
        INF[inference-service]
        ORC[orchestrator]
    end

    subgraph Superset["Profile: superset"]
        SS_DB[superset-db]
        SS_R[superset-redis]
        SS_I[superset-init]
        SS_W[superset-worker]
        SS_A[superset]
    end

    Kafka --> Gateway
    Kafka --> Normalizer
    Gateway --> Normalizer
    Normalizer --> Orchestrator
    Orchestrator --> Dagster
    Dagster --> Trino
    Trino --> Superset
```

---

## Network Architecture

Docker network connectivity between services.

```mermaid
flowchart TB
    subgraph Network["local-iceberg-lakehouse network"]
        subgraph External["External Ports"]
            P8000[":8000 - Traefik/Webhooks"]
            P8080[":8080 - Trino"]
            P8088[":8088 - Temporal UI"]
            P8089[":8089 - Superset"]
            P9000[":9000 - MinIO S3"]
            P9001[":9001 - MinIO Console"]
            P9092[":9092 - Kafka"]
            P3000[":3000 - Dagster"]
            P8181[":8181 - Polaris"]
        end

        subgraph Internal["Internal Services"]
            KB[kafka-broker:29092]
            PL[polaris:8181]
            MN[minio:9000]
            TR[trino:8080]
            TM[temporal:7233]
            INF[inference-service:8002]
            PDB[payments-db:5432]
        end
    end

    P8000 --> Traefik
    Traefik --> SG & SQG & AG & BG
    SG & SQG & AG & BG --> KB
    KB --> SN & SQN & AN & BN
    SN & SQN & AN & BN --> KB
    KB --> ORC
    ORC --> TM
    ORC --> INF
    ORC --> PDB
```

---

## Unified Event Schema

The normalized payment event structure used across all providers.

```mermaid
classDiagram
    class UnifiedPaymentEvent {
        +str event_id
        +str provider
        +str event_type
        +int amount_cents
        +str currency
        +str status
        +Optional~str~ failure_code
        +Optional~str~ customer_id
        +Optional~str~ merchant_id
        +datetime timestamp
        +dict metadata
    }

    class EnrichedPaymentEvent {
        +float fraud_score
        +float churn_score
        +str retry_strategy
        +datetime processed_at
    }

    class ProviderEvent {
        <<interface>>
        +transform() UnifiedPaymentEvent
    }

    class StripeEvent {
        +str id
        +str type
        +dict data
    }

    class SquareEvent {
        +str event_id
        +str type
        +dict data
    }

    class AdyenEvent {
        +str pspReference
        +str eventCode
        +dict additionalData
    }

    class BraintreeEvent {
        +str kind
        +str timestamp
        +dict transaction
    }

    ProviderEvent <|-- StripeEvent
    ProviderEvent <|-- SquareEvent
    ProviderEvent <|-- AdyenEvent
    ProviderEvent <|-- BraintreeEvent

    ProviderEvent --> UnifiedPaymentEvent : transforms to
    UnifiedPaymentEvent --> EnrichedPaymentEvent : enriched by orchestrator
```

---

## Deployment Profiles

Quick reference for Docker Compose profile combinations.

```mermaid
flowchart LR
    subgraph Profiles["make Commands"]
        A[make pipeline-up]
        B[make orchestrator-up]
        C[make gateway-simulator]
    end

    subgraph ProfileA["pipeline-up profiles"]
        A1[gateway]
        A2[normalizer]
    end

    subgraph ProfileB["orchestrator-up profiles"]
        B1[gateway]
        B2[normalizer]
        B3[orchestrator]
    end

    subgraph ProfileC["gateway-simulator profiles"]
        C1[gateway]
        C2[simulator]
    end

    A --> A1 & A2
    B --> B1 & B2 & B3
    C --> C1 & C2
```

| Command | Profiles | Services Started |
|---------|----------|------------------|
| `make pipeline-up` | gateway, normalizer | Traefik, 4 gateways, 4 normalizers |
| `make orchestrator-up` | gateway, normalizer, orchestrator | Above + Temporal, Inference, Orchestrator |
| `make gateway-simulator` | gateway, simulator | Traefik, 4 gateways, 4 simulators |

---

## Lakehouse Integration

How Polaris, Trino, Dagster, DBT, and MinIO integrate with Apache Iceberg.

```mermaid
flowchart TB
    subgraph Catalog["Apache Polaris :8181"]
        PC[REST Catalog API]
        PM[Table Metadata]
        PS[Schema Registry]
        PP[Partition Specs]
    end

    subgraph Storage["MinIO :9000"]
        MB[("s3://warehouse")]
        subgraph Data["Parquet Files"]
            D1[payment_events/*.parquet]
            D2[dim_customer/*.parquet]
            D3[fct_payments/*.parquet]
        end
    end

    subgraph Writers["Data Writers"]
        Dagster[Dagster<br/>PyIceberg IO Manager]
        DBT[DBT Models<br/>via Trino SQL]
    end

    subgraph Readers["Data Readers"]
        Trino[Trino :8080<br/>Iceberg Connector]
        Superset[Superset<br/>BI Dashboards]
    end

    Dagster -->|"REST API + OAuth2"| PC
    Dagster -->|"S3 API"| MB
    PC -->|"Manages"| PM
    PM -->|"References"| MB

    DBT -->|"SQL Queries"| Trino
    Trino -->|"REST API + OAuth2"| PC
    Trino -->|"S3 API"| MB

    Superset -->|"SQL"| Trino
```

---

## Polaris Catalog Architecture

Apache Polaris as the central Iceberg REST catalog.

```mermaid
flowchart LR
    subgraph Clients["Catalog Clients"]
        C1[Dagster/PyIceberg]
        C2[Trino]
        C3[Spark]
    end

    subgraph Polaris["Apache Polaris"]
        subgraph Auth["Authentication"]
            OAuth[OAuth2 Token Endpoint]
            Creds[Client Credentials]
        end

        subgraph API["REST Catalog API"]
            NS[Namespaces]
            TBL[Tables]
            SCH[Schemas]
        end

        subgraph RBAC["Access Control"]
            PR[Principal Roles]
            CR[Catalog Roles]
            GR[Grants]
        end
    end

    subgraph Catalog["polariscatalog"]
        subgraph Namespace["data namespace"]
            T1[payment_events]
            T2[payment_events_quarantine]
            T3[dim_customer]
            T4[dim_merchant]
            T5[fct_payments]
        end
    end

    C1 & C2 & C3 -->|"1. Get Token"| OAuth
    OAuth -->|"2. Validate"| Creds
    C1 & C2 & C3 -->|"3. API Requests"| API
    API -->|"4. Check Permissions"| RBAC
    API -->|"5. Manage"| Catalog
```

---

## Dagster Iceberg Integration

How Dagster writes DataFrames to Iceberg tables.

```mermaid
flowchart TB
    subgraph Dagster["Dagster Orchestrator"]
        Asset[Payment Events Asset]
        IOM[Iceberg IO Manager<br/>PandasIcebergIOManager]
        PyIce[PyIceberg Client]
    end

    subgraph Config["Configuration"]
        ENV[Environment Variables]
        URI["PYICEBERG_CATALOG__DEFAULT__URI"]
        CRED["PYICEBERG_CATALOG__DEFAULT__CREDENTIAL"]
        S3["PYICEBERG_CATALOG__DEFAULT__S3__*"]
    end

    subgraph Polaris["Polaris Catalog"]
        REST[REST API :8181]
        Meta[Table Metadata]
    end

    subgraph MinIO["MinIO Storage"]
        S3API[S3 API :9000]
        Parquet[Parquet Files]
    end

    Asset -->|"pd.DataFrame"| IOM
    IOM --> PyIce
    ENV --> PyIce

    PyIce -->|"1. Create/Update Table"| REST
    REST -->|"2. Return Metadata"| PyIce
    PyIce -->|"3. Write Parquet"| S3API
    S3API --> Parquet
    PyIce -->|"4. Commit Metadata"| REST
    REST --> Meta
```

---

## Trino Iceberg Connector

How Trino queries Iceberg tables via Polaris.

```mermaid
flowchart LR
    subgraph Client["Query Clients"]
        DBT[DBT]
        SS[Superset]
        CLI[Trino CLI]
    end

    subgraph Trino["Trino Coordinator :8080"]
        Parser[SQL Parser]
        Planner[Query Planner]
        subgraph Connector["Iceberg Connector"]
            IC[iceberg.properties]
            OAuth[OAuth2 Auth]
        end
    end

    subgraph Polaris["Polaris :8181"]
        Cat["/api/catalog/v1"]
        Tables[Table Metadata]
    end

    subgraph MinIO["MinIO :9000"]
        Files[Parquet Files]
    end

    Client -->|"SQL"| Parser
    Parser --> Planner
    Planner --> Connector

    Connector -->|"Get Token"| OAuth
    OAuth -->|"REST + Bearer Token"| Cat
    Cat --> Tables

    Connector -->|"Read Parquet"| Files
```

---

## DBT Transformation Flow

How DBT creates Iceberg tables via Trino.

```mermaid
flowchart TB
    subgraph DBT["DBT Project"]
        subgraph Models["Models"]
            SRC[sources.yml<br/>Bronze Tables]
            INT[intermediate/<br/>Ephemeral Models]
            MART[marts/<br/>Materialized Tables]
        end
        Profile[profiles.yml<br/>Trino Connection]
    end

    subgraph Trino["Trino"]
        SQL[SQL Execution]
        CTAS["CREATE TABLE AS SELECT"]
    end

    subgraph Iceberg["Iceberg Tables"]
        subgraph Source["Source Tables"]
            PE[data.payment_events]
        end
        subgraph Intermediate["Intermediate"]
            ICM[int_customer_metrics]
            IMM[int_merchant_metrics]
        end
        subgraph Marts["Mart Tables"]
            DC[dim_customer]
            DM[dim_merchant]
            FP[fct_payments]
        end
    end

    SRC -->|"ref"| INT
    INT -->|"ref"| MART
    Profile --> SQL

    DBT -->|"dbt run"| Trino
    SQL -->|"Read"| Source
    CTAS -->|"Write"| Intermediate
    CTAS -->|"Write"| Marts
```

---

## MinIO Storage Layout

How Iceberg data is organized in MinIO object storage.

```mermaid
flowchart TB
    subgraph MinIO["MinIO S3 Storage"]
        subgraph Bucket["s3://warehouse"]
            subgraph DataNS["data/"]
                subgraph PE["payment_events/"]
                    PEM[metadata/]
                    PED[data/]
                    PE1["v1.metadata.json"]
                    PE2["*.parquet"]
                end
                subgraph DC["dim_customer/"]
                    DCM[metadata/]
                    DCD[data/]
                end
                subgraph FP["fct_payments/"]
                    FPM[metadata/]
                    FPD[data/]
                end
            end
        end
    end

    PEM --> PE1
    PED --> PE2
```

### Storage Structure

| Path | Contents |
|------|----------|
| `s3://warehouse/` | Root bucket |
| `s3://warehouse/data/` | Namespace directory |
| `s3://warehouse/data/{table}/metadata/` | Iceberg metadata JSON files |
| `s3://warehouse/data/{table}/data/` | Parquet data files |

---

## Dagster Asset Lineage

Complete data lineage from PostgreSQL to analytics marts.

```mermaid
flowchart LR
    subgraph Bronze["Bronze Layer"]
        PG[(PostgreSQL<br/>payment_events)]
    end

    subgraph Ingestion["Dagster Ingestion"]
        DA1[payment_events asset]
        DA2[payment_events_quarantine asset]
    end

    subgraph Iceberg["Iceberg Tables"]
        IT1[data.payment_events]
        IT2[data.payment_events_quarantine]
    end

    subgraph DBT["DBT Transformations"]
        subgraph IntLayer["Intermediate"]
            I1[int_customer_metrics]
            I2[int_merchant_metrics]
            I3[int_daily_summary]
        end
        subgraph MartLayer["Marts"]
            M1[dim_customer]
            M2[dim_merchant]
            M3[dim_date]
            M4[fct_payments]
            M5[fct_daily_payments]
        end
    end

    subgraph Analytics["Analytics"]
        Trino[Trino Queries]
        Superset[Superset Dashboards]
    end

    PG --> DA1
    PG --> DA2
    DA1 --> IT1
    DA2 --> IT2

    IT1 --> I1 & I2 & I3
    I1 & I2 --> M1
    I1 & I2 --> M2
    I3 --> M3
    IT1 & I1 & I2 --> M4
    I3 --> M5

    M1 & M2 & M3 & M4 & M5 --> Trino
    Trino --> Superset
```

---

## Connection Configuration Summary

```mermaid
flowchart TB
    subgraph Env["Environment Variables"]
        E1["POLARIS_USER / POLARIS_PASSWORD"]
        E2["AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY"]
        E3["PYICEBERG_CATALOG__DEFAULT__*"]
    end

    subgraph Services["Service Connections"]
        subgraph DagsterConn["Dagster"]
            DC1["uri: http://polaris:8181/api/catalog"]
            DC2["s3.endpoint: http://minio:9000"]
            DC3["credential: user:password"]
        end

        subgraph TrinoConn["Trino"]
            TC1["iceberg.rest-catalog.uri: http://polaris:8181/api/catalog/"]
            TC2["s3.endpoint: http://minio:9000"]
            TC3["oauth2.credential: user:password"]
        end

        subgraph DBTConn["DBT"]
            DBC1["host: trino"]
            DBC2["port: 8080"]
            DBC3["database: iceberg"]
            DBC4["schema: data"]
        end
    end

    E1 --> DC3 & TC3
    E2 --> DC2 & TC2
    E3 --> DagsterConn
```

| Service | Polaris URL | MinIO URL | Auth Method |
|---------|-------------|-----------|-------------|
| Dagster | `http://polaris:8181/api/catalog` | `http://minio:9000` | OAuth2 client credentials |
| Trino | `http://polaris:8181/api/catalog/` | `http://minio:9000` | OAuth2 client credentials |
| DBT | N/A (via Trino) | N/A (via Trino) | None (Trino handles) |

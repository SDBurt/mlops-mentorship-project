# Butter Payments Project Implementation Plan

**Target Role:** Data Engineer at Butter Payments
**Project Goal:** Transform existing lakehouse into streaming payment processing platform demonstrating upstream validation, real-time ingestion, and workflow orchestration capabilities.

**Timeline:** 10 weeks
**Status:** Planning Phase

---

## Executive Summary

This plan expands the existing Kubernetes-based data lakehouse (Polaris, MinIO, Dagster, DBT) to demonstrate key capabilities required for the Butter Payments Data Engineer role:

1. **Real-time payment event streaming** (Kafka + Flink)
2. **Multi-layer upstream validation** (Flink + DBT)
3. **Per-payment workflow orchestration** (Temporal)
4. **ML-driven retry simulation** (Mock inference service)
5. **Multi-provider normalization** (Unified schema design)

This project directly addresses Butter's core requirements: upstream validation ("Is it null, NULL, or 'null'?"), real-time processing ("not in batches"), and distributed workflow management.

---

## Current State

### Existing Infrastructure
- **Kubernetes cluster** with lakehouse namespace
- **Polaris** as Iceberg REST catalog
- **MinIO** for S3-compatible object storage
- **Dagster** for data pipeline orchestration
- **DBT** for SQL transformations
- **Reddit pipeline** demonstrating batch API ingestion with PRAW

### Current Capabilities
- Bronze/Silver/Gold medallion architecture
- Incremental model processing
- Data quality testing in DBT
- Kubernetes-native deployment with Helm

### Gaps to Address
- No real-time streaming ingestion
- No upstream validation before data lands
- No per-event workflow orchestration
- No payment domain simulation

---

## Target Architecture

### High-Level Flow

```
Payment Event Generated
    ↓
[Temporal Workflow] - Individual payment processing
├─► Fraud Check Activity
├─► Payment Charge Activity (with retries)
├─► ML Retry Strategy Activity
└─► Emit Event to Kafka
    ↓
[Kafka] - Event buffering
    ↓
[Flink] - Stream Validation (Layer 1)
├─► Valid events → Iceberg Bronze
└─► Invalid events → Quarantine Tables
    ↓
[Iceberg Bronze] - Raw validated events accumulate
    ↓
[Dagster Schedule] - Hourly trigger
    ↓
[DBT Transformations] - Validation Layer 2
├─► Silver: Clean, validated data
├─► Gold: Analytics-ready aggregates
└─► Quarantine: Failed validations
    ↓
[Analytics & Monitoring]
```

### Component Responsibilities

**Temporal:**
- Orchestrates individual payment processing workflows
- Manages stateful retry logic with durable timers
- Calls ML inference service for retry strategies
- Emits completed events to Kafka
- Demonstrates: "per-payment approach, not batches"

**Kafka:**
- Buffers payment events from Temporal workflows
- Decouples event generation from processing
- Enables replay and backfill scenarios

**Flink:**
- Real-time stream validation (Layer 1)
- Schema enforcement and normalization
- Null handling ("null" vs NULL vs 'null')
- Invalid currency/amount filtering
- Writes to Iceberg Bronze with ACID guarantees

**Dagster:**
- Schedules DBT transformations (hourly)
- Monitors pipeline health
- Tracks quarantine metrics
- Orchestrates batch analytics jobs

**DBT:**
- Business validation rules (Layer 2)
- Provider schema normalization
- Star schema modeling for analytics
- Data quality tests with dbt-expectations

**ML Service:**
- Mock inference endpoint (FastAPI)
- Returns retry strategy based on payment context
- Called by Temporal as an activity

---

## Implementation Phases

### Phase 1: Streaming Foundation (Weeks 1-2)

**Status**: ✅ Completed

**Objective**: Establish Kafka + Flink streaming pipeline

**Tasks**:

1. **Deploy Kafka to Kubernetes**
   - Deployed Bitnami Kafka via Docker Compose (for local dev)
   - Configured topics for charges, refunds, disputes, subscriptions

2. **Deploy Flink Cluster**
   - Created custom Flink Docker image with Iceberg connector
   - Deployed JobManager + TaskManager
   - Configured Flink to access Polaris catalog

3. **Create JR Payment Templates**
   - Created templates for all 4 payment types
   - Configured realistic data generation (nulls, invalid currencies)

4. **Basic Flink SQL Pipeline**
   - Created Kafka source tables
   - Created Iceberg sink tables via Polaris
   - Implemented auto-submission service (`flink-job-submitter`)

**Success Criteria:**
- [x] Kafka accessible from Flink and external clients
- [x] Flink successfully writes to Iceberg via Polaris
- [x] JR generates 100+ events/sec to Kafka
- [x] Events queryable in Trino within 30 seconds

**Deliverables:**
- Docker Compose stack for streaming
- Flink SQL auto-submission script
- JR payment template files
- Basic architecture diagram

---

### Phase 2: Upstream Validation (Weeks 3-4)

**Status**: ✅ Completed

**Objective**: Implement multi-layer validation catching data quality issues

**Tasks**:

1. **Flink Validation Layer (Layer 1)**
   - Implemented validation logic in Flink SQL INSERT statements
   - **Null Normalization**: Converted 'null', 'NULL', '' to SQL NULL
   - **Currency Validation**: Enforced whitelist (USD, CAD, GBP, EUR, JPY)
   - **Amount Validation**: Enforced > 0 and <= 1,000,000
   - **Stream Splitting**: Valid records → `payment_charges`, Invalid → `quarantine_payment_charges`

2. **Create Quarantine Tables**
   - Created quarantine tables for all 4 event types
   - Added `quarantine_timestamp` and `rejection_reason` columns
   - Captures full record context for debugging

3. **DBT Validation Layer (Layer 2)**
   - Created Staging models (Silver layer)
   - Implemented business logic validation (e.g., suspicious patterns)
   - Added `validation_flag` for records requiring review

4. **DBT Data Quality Tests**
   - Implemented `unique`, `not_null`, `accepted_values` tests
   - Added custom expression tests for business rules

5. **Dagster Monitoring Assets**
   - `quarantine_charges_monitor`: Alerts on >100 invalid records/hour
   - `quarantine_summary_monitor`: Aggregates quality metrics across all tables
   - `validation_flag_monitor`: Tracks suspicious pattern rates

**Success Criteria:**
- [x] <1% invalid data reaches Silver layer
- [x] All null variations handled correctly
- [x] Quarantine tables capture rejection reasons
- [x] DBT tests pass on all Silver models
- [x] Dagster alerts on quarantine spikes

**Deliverables:**
- Flink validation SQL scripts
- DBT Silver layer models with tests
- Dagster monitoring assets
- Validation documentation explaining each layer

---

### Phase 3: Temporal Integration (Weeks 5-6)

**Objective:** Add per-payment workflow orchestration with stateful retry logic

**Tasks:**

1. **Deploy Temporal Server**
   ```bash
   helm repo add temporalio https://go.temporal.io/helm-charts
   helm install temporal temporalio/temporal -n lakehouse \
     --set server.replicaCount=1 \
     --set cassandra.enabled=true \
     --set cassandra.persistence.enabled=false \
     --set web.enabled=true
   ```

2. **Create Payment Processing Workflow**
   ```python
   # workflows/payment_processor.py
   from temporalio import workflow, activity
   from datetime import timedelta
   import random

   @activity.defn
   async def check_fraud(payment_data: dict) -> dict:
       """Fraud detection activity - simulates ML model call"""
       risk_score = random.random()

       return {
           "is_safe": risk_score < 0.98,  # 2% fraud rate
           "risk_score": risk_score,
           "reasons": ["high_risk_country"] if risk_score >= 0.98 else []
       }

   @activity.defn
   async def charge_payment(payment_data: dict) -> dict:
       """Payment processing activity with simulated failures"""
       # Simulate 10% decline rate
       if random.random() < 0.10:
           failure_codes = [
               "card_declined",
               "insufficient_funds",
               "expired_card",
               "incorrect_cvc"
           ]
           raise Exception(random.choice(failure_codes))

       return {
           "status": "succeeded",
           "charge_id": f"ch_{random.randint(1000000, 9999999)}",
           "amount_charged": payment_data['amount']
       }

   @activity.defn
   async def get_retry_strategy(payment_data: dict, failure_reason: str) -> dict:
       """Call ML service to determine optimal retry strategy"""
       # This would call your ML inference service
       # For now, return simple rules-based strategy
       strategies = {
           "card_declined": {"delay_hours": 6, "method": "alternative_card"},
           "insufficient_funds": {"delay_hours": 24, "method": "same_card"},
           "expired_card": {"delay_hours": 0, "method": "update_card"},
           "incorrect_cvc": {"delay_hours": 1, "method": "retry_with_correct_cvc"}
       }

       return strategies.get(failure_reason, {"delay_hours": 12, "method": "same_card"})

   @activity.defn
   async def emit_to_kafka(event: dict):
       """Send completed payment event to Kafka"""
       from kafka import KafkaProducer
       import json

       producer = KafkaProducer(
           bootstrap_servers=['kafka.lakehouse.svc.cluster.local:9092'],
           value_serializer=lambda v: json.dumps(v).encode('utf-8')
       )
       producer.send('transactions', event)
       producer.flush()

   @workflow.defn
   class PaymentProcessingWorkflow:
       @workflow.run
       async def run(self, payment_request: dict) -> dict:
           """
           Orchestrates payment processing with ML-driven retry logic.

           This demonstrates Temporal's strength: stateful, per-payment
           workflows with durable timers and retry policies.
           """
           workflow_id = workflow.info().workflow_id

           # Step 1: Fraud check (no retries - immediate decision)
           fraud_check = await workflow.execute_activity(
               check_fraud,
               payment_request,
               start_to_close_timeout=timedelta(seconds=10)
           )

           if not fraud_check["is_safe"]:
               event = {
                   "event_id": f"evt_{random.randint(1000000, 9999999)}",
                   "type": "charge.blocked",
                   "created": payment_request["transaction_time"],
                   "data": {
                       **payment_request,
                       "fraud_score": fraud_check["risk_score"],
                       "block_reasons": fraud_check["reasons"]
                   }
               }
               await workflow.execute_activity(
                   emit_to_kafka,
                   event,
                   start_to_close_timeout=timedelta(seconds=5)
               )
               return event

           # Step 2: Charge payment (with retry policy)
           max_retry_attempts = 3
           for attempt in range(max_retry_attempts):
               try:
                   result = await workflow.execute_activity(
                       charge_payment,
                       payment_request,
                       start_to_close_timeout=timedelta(seconds=30),
                       retry_policy={
                           "maximum_attempts": 1,  # We handle retries in workflow
                           "initial_interval": timedelta(seconds=1)
                       }
                   )

                   # Success!
                   event = {
                       "event_id": f"evt_{random.randint(1000000, 9999999)}",
                       "type": "charge.succeeded",
                       "created": payment_request["transaction_time"],
                       "data": {
                           **payment_request,
                           **result,
                           "attempts": attempt + 1
                       }
                   }

                   await workflow.execute_activity(
                       emit_to_kafka,
                       event,
                       start_to_close_timeout=timedelta(seconds=5)
                   )

                   return event

               except Exception as e:
                   failure_reason = str(e)

                   if attempt < max_retry_attempts - 1:
                       # Get ML-driven retry strategy
                       strategy = await workflow.execute_activity(
                           get_retry_strategy,
                           args=[payment_request, failure_reason],
                           start_to_close_timeout=timedelta(seconds=5)
                       )

                       # Durable timer - workflow sleeps but state preserved
                       await workflow.sleep(timedelta(hours=strategy["delay_hours"]))

                       # Update payment method based on strategy
                       if strategy["method"] == "alternative_card":
                           payment_request["payment_method"] = "backup_card"
                   else:
                       # Final failure after all retries
                       event = {
                           "event_id": f"evt_{random.randint(1000000, 9999999)}",
                           "type": "charge.failed",
                           "created": payment_request["transaction_time"],
                           "data": {
                               **payment_request,
                               "failure_code": failure_reason,
                               "attempts": max_retry_attempts,
                               "final_failure": True
                           }
                       }

                       await workflow.execute_activity(
                           emit_to_kafka,
                           event,
                           start_to_close_timeout=timedelta(seconds=5)
                       )

                       return event
   ```

3. **Create Temporal Worker**
   ```python
   # workflows/worker.py
   import asyncio
   from temporalio.client import Client
   from temporalio.worker import Worker
   from payment_processor import (
       PaymentProcessingWorkflow,
       charge_payment,
       check_fraud,
       get_retry_strategy,
       emit_to_kafka
   )

   async def main():
       client = await Client.connect(
           "temporal-frontend.lakehouse.svc.cluster.local:7233"
       )

       worker = Worker(
           client,
           task_queue="payment-processing",
           workflows=[PaymentProcessingWorkflow],
           activities=[
               charge_payment,
               check_fraud,
               get_retry_strategy,
               emit_to_kafka
           ],
           max_concurrent_workflow_tasks=100
       )

       print("Worker started, listening for tasks...")
       await worker.run()

   if __name__ == "__main__":
       asyncio.run(main())
   ```

4. **Payment Generator Client**
   ```python
   # workflows/payment_generator.py
   import asyncio
   from temporalio.client import Client
   import random
   from datetime import datetime

   async def generate_payments():
       """
       Replaces JR tool - triggers Temporal workflows instead of
       directly writing to Kafka. This simulates payment attempts.
       """
       client = await Client.connect(
           "temporal-frontend.lakehouse.svc.cluster.local:7233"
       )

       payment_id = 0

       while True:
           payment_id += 1

           payment_request = {
               "transaction_id": f"TXN_{payment_id:08d}",
               "user_id": f"USER_{random.randint(1, 3000)}",
               "customer_id": f"cus_{random.randint(1, 10000)}",
               "amount": random.randint(100, 50000),  # cents
               "currency": random.choice(["usd", "cad", "gbp", "eur"]),
               "payment_method": "card",
               "merchant": random.choice([
                   "Amazon", "Apple", "Netflix", "Spotify", "Uber"
               ]),
               "transaction_time": datetime.utcnow().isoformat(),
               "metadata": {
                   "merchant_id": f"merch_{random.randint(1, 5000)}"
               }
           }

           # Start workflow (non-blocking)
           await client.start_workflow(
               PaymentProcessingWorkflow.run,
               payment_request,
               id=f"payment-{payment_request['transaction_id']}",
               task_queue="payment-processing"
           )

           # Generate 2 payments/sec
           await asyncio.sleep(0.5)

   if __name__ == "__main__":
       asyncio.run(generate_payments())
   ```

5. **Containerize Temporal Components**
   ```dockerfile
   # workflows/Dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir \
       temporalio \
       kafka-python \
       requests

   COPY . .

   # Default to worker, but can override
   CMD ["python", "worker.py"]
   ```

6. **Deploy Worker to Kubernetes**
   ```yaml
   # k8s/temporal-worker-deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: temporal-payment-worker
     namespace: lakehouse
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: temporal-worker
     template:
       metadata:
         labels:
           app: temporal-worker
       spec:
         containers:
         - name: worker
           image: payment-worker:latest
           env:
           - name: TEMPORAL_ADDRESS
             value: "temporal-frontend.lakehouse.svc.cluster.local:7233"
           - name: KAFKA_BOOTSTRAP_SERVERS
             value: "kafka.lakehouse.svc.cluster.local:9092"
           resources:
             requests:
               memory: "256Mi"
               cpu: "250m"
             limits:
               memory: "512Mi"
               cpu: "500m"
   ---
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: payment-generator
     namespace: lakehouse
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: payment-generator
     template:
       metadata:
         labels:
           app: payment-generator
       spec:
         containers:
         - name: generator
           image: payment-worker:latest
           command: ["python", "payment_generator.py"]
           env:
           - name: TEMPORAL_ADDRESS
             value: "temporal-frontend.lakehouse.svc.cluster.local:7233"
   ```

**Success Criteria:**
- [ ] Temporal workflows execute with retry logic
- [ ] Failed payments retry with ML-driven delays
- [ ] Workflows survive pod restarts (durable state)
- [ ] Events flow: Temporal → Kafka → Flink → Iceberg
- [ ] Temporal UI shows workflow history

**Deliverables:**
- Temporal workflow implementations
- Worker deployment manifests
- Architecture diagram showing Temporal's role
- Documentation: When to use Temporal vs Dagster

---

### Phase 4: ML Retry Simulation (Weeks 7-8)

**Objective:** Add ML inference service for retry strategy optimization

**Tasks:**

1. **Create ML Inference Service**
   ```python
   # ml_service/app.py
   from fastapi import FastAPI
   from pydantic import BaseModel
   import random

   app = FastAPI()

   class PaymentContext(BaseModel):
       customer_id: str
       failure_code: str
       amount: int
       currency: str
       previous_attempts: int
       time_since_last_attempt_hours: float
       customer_lifetime_value: float = 0.0
       payment_history_success_rate: float = 0.95

   class RetryStrategy(BaseModel):
       retry_method: str
       delay_hours: float
       probability_success: float
       reasoning: str

   @app.post("/predict_retry_strategy")
   def predict_retry_strategy(context: PaymentContext) -> RetryStrategy:
       """
       Mock ML model that returns retry strategy.
       In production, this would call a trained model.
       """

       # Simple rule-based logic mimicking ML decisions
       if context.failure_code == "insufficient_funds":
           # High-value customers get faster retries
           if context.customer_lifetime_value > 10000:
               return RetryStrategy(
                   retry_method="same_card",
                   delay_hours=6.0,
                   probability_success=0.72,
                   reasoning="High CLV customer, shorter wait"
               )
           else:
               return RetryStrategy(
                   retry_method="same_card",
                   delay_hours=24.0,
                   probability_success=0.65,
                   reasoning="Standard wait for funds availability"
               )

       elif context.failure_code == "card_declined":
           # If customer has backup payment method
           if context.payment_history_success_rate > 0.90:
               return RetryStrategy(
                   retry_method="alternative_card",
                   delay_hours=1.0,
                   probability_success=0.85,
                   reasoning="Good history, try backup card quickly"
               )
           else:
               return RetryStrategy(
                   retry_method="contact_customer",
                   delay_hours=0.0,
                   probability_success=0.45,
                   reasoning="Poor history, needs customer intervention"
               )

       elif context.failure_code == "expired_card":
           return RetryStrategy(
               retry_method="request_card_update",
               delay_hours=0.0,
               probability_success=0.90,
               reasoning="Card update required"
           )

       else:
           # Default strategy
           return RetryStrategy(
               retry_method="same_card",
               delay_hours=12.0,
               probability_success=0.55,
               reasoning="Generic retry strategy"
           )

   @app.get("/health")
   def health():
       return {"status": "healthy"}
   ```

2. **Containerize ML Service**
   ```dockerfile
   # ml_service/Dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir \
       fastapi \
       uvicorn \
       pydantic

   COPY . .

   CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

3. **Deploy ML Service to Kubernetes**
   ```yaml
   # k8s/ml-service-deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ml-retry-service
     namespace: lakehouse
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: ml-service
     template:
       metadata:
         labels:
           app: ml-service
       spec:
         containers:
         - name: ml-service
           image: ml-retry-service:latest
           ports:
           - containerPort: 8000
           resources:
             requests:
               memory: "128Mi"
               cpu: "100m"
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: ml-retry-service
     namespace: lakehouse
   spec:
     selector:
       app: ml-service
     ports:
     - port: 8000
       targetPort: 8000
   ```

4. **Update Temporal Workflow to Call ML Service**
   ```python
   @activity.defn
   async def get_retry_strategy(payment_data: dict, failure_reason: str) -> dict:
       """Call ML inference service"""
       import httpx

       # Build context from payment data and history
       context = {
           "customer_id": payment_data["customer_id"],
           "failure_code": failure_reason,
           "amount": payment_data["amount"],
           "currency": payment_data["currency"],
           "previous_attempts": payment_data.get("attempts", 0),
           "time_since_last_attempt_hours": 0.0,
           "customer_lifetime_value": get_customer_clv(payment_data["customer_id"]),
           "payment_history_success_rate": get_success_rate(payment_data["customer_id"])
       }

       async with httpx.AsyncClient() as client:
           response = await client.post(
               "http://ml-retry-service.lakehouse.svc.cluster.local:8000/predict_retry_strategy",
               json=context,
               timeout=5.0
           )
           response.raise_for_status()

       return response.json()
   ```

5. **Feature Engineering in DBT**
   ```sql
   -- models/gold/customer_payment_metrics.sql
   {{ config(materialized='table') }}

   WITH payment_history AS (
       SELECT
           customer_id,
           COUNT(*) as total_payments,
           SUM(CASE WHEN type = 'charge.succeeded' THEN 1 ELSE 0 END) as successful_payments,
           SUM(CASE WHEN type = 'charge.failed' THEN 1 ELSE 0 END) as failed_payments,
           SUM(amount_cents) / 100.0 as lifetime_value,
           AVG(amount_cents) / 100.0 as avg_payment_amount,
           MAX(created) as last_payment_date
       FROM {{ ref('stg_payments') }}
       GROUP BY customer_id
   )

   SELECT
       customer_id,
       total_payments,
       successful_payments,
       failed_payments,
       CAST(successful_payments AS DOUBLE) / NULLIF(total_payments, 0) as success_rate,
       lifetime_value,
       avg_payment_amount,
       last_payment_date,
       CASE
           WHEN lifetime_value > 10000 THEN 'high'
           WHEN lifetime_value > 1000 THEN 'medium'
           ELSE 'low'
       END as clv_segment
   FROM payment_history
   ```

6. **Optional: Train Simple Model**
   ```python
   # notebooks/train_retry_model.py
   """
   Optional: Train a simple model on synthetic data
   """
   import pandas as pd
   from sklearn.ensemble import RandomForestClassifier
   import joblib

   # Load historical payment data from Gold layer
   df = pd.read_sql("""
       SELECT
           p.failure_code,
           p.amount_cents,
           p.currency,
           c.success_rate,
           c.lifetime_value,
           -- Target: did retry succeed?
           LEAD(p.type) OVER (PARTITION BY p.customer_id ORDER BY p.created) = 'charge.succeeded' as retry_succeeded
       FROM lakehouse.stg_payments p
       JOIN lakehouse.customer_payment_metrics c ON p.customer_id = c.customer_id
       WHERE p.type = 'charge.failed'
   """, engine)

   # Train model
   features = ['amount_cents', 'success_rate', 'lifetime_value']
   X = df[features]
   y = df['retry_succeeded']

   model = RandomForestClassifier()
   model.fit(X, y)

   # Save model
   joblib.dump(model, 'retry_model.pkl')
   ```

**Success Criteria:**
- [ ] ML service responds in <100ms
- [ ] Temporal workflows call ML service successfully
- [ ] Different failure codes get different strategies
- [ ] Customer metrics available for context
- [ ] Optional: Trained model deployed

**Deliverables:**
- ML inference service with API
- Feature engineering DBT models
- Integration with Temporal workflows
- Optional: Jupyter notebook with model training

---

### Phase 5: Multi-Provider Support (Week 9)

**Objective:** Demonstrate normalizing different payment provider schemas

**Tasks:**

1. **Add Square Payment Schema**
   ```json
   {
     "payment_id": "{{key \"sqpay_\" 1000000}}",
     "order_id": "{{key \"sqord_\" 100000}}",
     "status": "{{randoms \"COMPLETED|FAILED|CANCELED\"}}",
     "amount_money": {
       "amount": {{amount 1 500 ""}},
       "currency": "{{randoms \"USD|CAD|GBP\"}}"
     },
     "created_at": "{{format_timestamp now \"2006-01-02T15:04:05Z\"}}",
     "buyer_email_address": "user{{random 1 3000}}@example.com",
     "card_details": {
       "status": "{{randoms \"CAPTURED|FAILED\"}}",
       "card_brand": "{{randoms \"VISA|MASTERCARD|AMEX\"}}",
       "last_4": "{{random 1000 9999}}"
     }
   }
   ```

2. **Create Provider-Specific Bronze Tables**
   ```sql
   -- Flink: Separate Kafka topics per provider
   CREATE TABLE stripe_bronze (
       event_id STRING,
       type STRING,
       created TIMESTAMP(3),
       amount_cents BIGINT,
       currency STRING,
       customer_id STRING,
       failure_code STRING
   );

   CREATE TABLE square_bronze (
       payment_id STRING,
       status STRING,
       created_at TIMESTAMP(3),
       amount_dollars DECIMAL(10, 2),
       currency STRING,
       buyer_email STRING,
       card_status STRING
   );
   ```

3. **DBT Provider Normalization**
   ```sql
   -- models/intermediate/int_stripe_normalized.sql
   {{ config(materialized='view') }}

   SELECT
       'stripe' as provider,
       event_id as transaction_id,
       type as event_type,
       created as transaction_timestamp,
       amount_cents / 100.0 as amount_dollars,
       UPPER(currency) as currency_code,
       customer_id,
       CASE
           WHEN type = 'charge.succeeded' THEN 'SUCCESS'
           WHEN type = 'charge.failed' THEN 'FAILED'
           ELSE 'OTHER'
       END as normalized_status,
       failure_code as failure_reason
   FROM {{ source('bronze', 'stripe_payments') }}
   ```

   ```sql
   -- models/intermediate/int_square_normalized.sql
   {{ config(materialized='view') }}

   SELECT
       'square' as provider,
       payment_id as transaction_id,
       status as event_type,
       created_at as transaction_timestamp,
       amount_dollars,
       UPPER(currency) as currency_code,
       buyer_email as customer_id,
       CASE
           WHEN status = 'COMPLETED' THEN 'SUCCESS'
           WHEN status = 'FAILED' THEN 'FAILED'
           ELSE 'OTHER'
       END as normalized_status,
       card_status as failure_reason
   FROM {{ source('bronze', 'square_payments') }}
   ```

   ```sql
   -- models/silver/unified_payments.sql
   {{ config(
       materialized='incremental',
       unique_key='transaction_id'
   ) }}

   WITH all_providers AS (
       SELECT * FROM {{ ref('int_stripe_normalized') }}
       UNION ALL
       SELECT * FROM {{ ref('int_square_normalized') }}
   )

   SELECT
       transaction_id,
       provider,
       event_type,
       transaction_timestamp,
       amount_dollars,
       currency_code,
       customer_id,
       normalized_status,
       failure_reason
   FROM all_providers
   {% if is_incremental() %}
   WHERE transaction_timestamp > (SELECT MAX(transaction_timestamp) FROM {{ this }})
   {% endif %}
   ```

4. **Provider-Specific Validation Rules**
   ```yaml
   # dbt/models/silver/schema.yml
   models:
     - name: unified_payments
       tests:
         - dbt_utils.expression_is_true:
             expression: "provider IN ('stripe', 'square')"
       columns:
         - name: transaction_id
           tests:
             - unique
             - not_null
         - name: amount_dollars
           tests:
             - not_null
             # Stripe has cent precision, Square has dollar precision
             - dbt_utils.expression_is_true:
                 expression: "> 0"
   ```

**Success Criteria:**
- [ ] Both Stripe and Square data in Bronze
- [ ] Unified schema in Silver layer
- [ ] Provider-agnostic analytics queries work
- [ ] Validation rules account for provider differences

**Deliverables:**
- Multiple JR templates for providers
- Provider normalization DBT models
- Documentation on schema differences
- Example analytics queries

---

### Phase 6: Monitoring & Documentation (Week 10)

**Objective:** Production-ready observability and comprehensive documentation

**Tasks:**

1. **Dagster Dashboard Assets**
   ```python
   @asset(group_name="monitoring")
   def pipeline_health_metrics():
       """Overall pipeline health dashboard"""
       return {
           "kafka_lag": get_kafka_consumer_lag(),
           "flink_backpressure": check_flink_backpressure(),
           "iceberg_write_rate": get_iceberg_write_rate(),
           "validation_pass_rate": get_validation_pass_rate(),
           "quarantine_volume": get_quarantine_count()
       }

   @asset(group_name="monitoring")
   def temporal_workflow_metrics():
       """Temporal workflow statistics"""
       return {
           "workflows_started": get_temporal_metric("workflows_started"),
           "workflows_completed": get_temporal_metric("workflows_completed"),
           "workflows_failed": get_temporal_metric("workflows_failed"),
           "avg_workflow_duration_ms": get_temporal_metric("avg_duration")
       }

   @asset(group_name="monitoring")
   def payment_success_metrics():
       """Business KPIs"""
       query = """
       SELECT
           COUNT(*) as total_payments,
           SUM(CASE WHEN type = 'charge.succeeded' THEN 1 ELSE 0 END) as successful,
           SUM(CASE WHEN type = 'charge.failed' THEN 1 ELSE 0 END) as failed,
           AVG(amount_cents) / 100.0 as avg_amount
       FROM lakehouse.stg_payments
       WHERE created > current_timestamp - INTERVAL '1' HOUR
       """
       return execute_trino_query(query)
   ```

2. **Create Architecture Diagrams**
   - Overall system architecture
   - Data flow diagram (Temporal → Kafka → Flink → Iceberg → Dagster → DBT)
   - Validation layers diagram
   - Temporal workflow state diagram

3. **Comprehensive README**
   ```markdown
   # Payment Processing Data Lakehouse

   ## Overview
   Production-grade streaming data platform demonstrating real-time payment
   processing with multi-layer validation and ML-driven retry optimization.

   **Inspired by:** Butter Payments' payment recovery architecture

   ## Key Features

   ### 1. Real-Time Streaming Pipeline
   - Kafka for event buffering
   - Flink for stream processing
   - Iceberg for ACID-compliant storage
   - Sub-second latency from event to query

   ### 2. Multi-Layer Upstream Validation
   **Layer 1 (Flink):** Stream-level validation
   - Null normalization (null vs NULL vs 'null')
   - Currency code validation (ISO 4217)
   - Amount bounds checking
   - Invalid records → Quarantine tables

   **Layer 2 (DBT):** Business logic validation
   - Complex business rules
   - Cross-table referential integrity
   - Statistical anomaly detection
   - 99.9% clean data reaching Gold layer

   ### 3. Per-Payment Workflow Orchestration
   - Temporal workflows for stateful processing
   - ML-driven retry strategies
   - Durable timers for delayed retries
   - Compensation logic for refunds

   ### 4. Multi-Provider Normalization
   - Stripe, Square payment schemas
   - Unified data model in Silver layer
   - Provider-agnostic analytics

   ## Architecture

   [Include diagram here]

   ## Metrics
   - **Throughput:** 2,000 events/sec
   - **Validation pass rate:** 99.1%
   - **Query latency (p95):** <100ms
   - **Workflow success rate:** 97.3%
   ```

4. **Technical Blog Post**
   Write companion blog post:

   **Title:** "Building a Production-Grade Payment Data Pipeline: Multi-Layer Validation at Scale"

   **Sections:**
   - Why upstream validation matters in payment systems
   - The "null" problem: Handling data type inconsistencies
   - Streaming vs batch: When to use each
   - Temporal for stateful workflows vs Dagster for data pipelines
   - ML-driven retry optimization
   - Dead letter queues and quarantine patterns
   - Lessons learned

5. **Video Walkthrough**
   Record 5-10 minute demo showing:
   - Payment workflows in Temporal UI
   - Real-time validation in action
   - Quarantine table analysis
   - End-to-end data flow
   - Analytics queries on Gold layer

**Success Criteria:**
- [ ] All components monitored via Dagster
- [ ] Architecture diagrams complete
- [ ] README covers all features
- [ ] Blog post published (Medium/Dev.to)
- [ ] Video demo recorded

**Deliverables:**
- Comprehensive README.md
- Architecture diagrams (draw.io/Excalidraw)
- Technical blog post
- Video walkthrough
- Grafana/Dagster dashboards

---

## Technical Requirements

### Infrastructure
- Kubernetes cluster (Docker Desktop, minikube, or k3s)
- 16GB RAM minimum (32GB recommended)
- 50GB disk space

### Core Components
- **Polaris** (existing): Iceberg REST catalog
- **MinIO** (existing): S3-compatible storage
- **Dagster** (existing): Data orchestration
- **DBT** (existing): SQL transformations
- **Kafka**: Event streaming (new)
- **Flink**: Stream processing (new)
- **Temporal**: Workflow orchestration (new)

### Development Tools
- Python 3.11+
- Docker & docker-compose
- kubectl & Helm
- JR CLI tool
- Trino CLI

---

## Testing Strategy

### Unit Tests
- DBT model tests (schema.yml)
- Python workflow logic tests
- Activity function tests

### Integration Tests
- End-to-end data flow tests
- Kafka → Flink → Iceberg integration
- Temporal workflow execution
- ML service integration

### Data Quality Tests
- DBT expectations on all models
- Quarantine volume monitoring
- Schema evolution tests
- Partition pruning validation

### Performance Tests
- Throughput: 1000+ events/sec
- Query latency: p95 < 200ms
- Workflow duration: avg < 2s
- Resource utilization under load

---

## Success Metrics

### Technical Metrics
- [ ] 99%+ data validation pass rate
- [ ] <1% quarantine rate
- [ ] Sub-second ingestion latency
- [ ] 97%+ workflow success rate
- [ ] Zero data loss (ACID guarantees)

### Portfolio Metrics
- [ ] GitHub stars/forks
- [ ] Blog post views/engagement
- [ ] Video demo views
- [ ] Interview conversions

### Learning Outcomes
- [ ] Understand Kafka producer/consumer patterns
- [ ] Master Flink SQL and streaming concepts
- [ ] Implement Temporal workflows with retries
- [ ] Build multi-layer validation systems
- [ ] Design ML inference integration
- [ ] Production monitoring and observability

---

## Risk Mitigation

### Technical Risks

**Risk:** Kafka/Flink resource consumption
**Mitigation:** Set resource limits, use single-replica configs for dev

**Risk:** Temporal workflows accumulating state
**Mitigation:** Implement workflow timeouts and cleanup jobs

**Risk:** Data quality issues reaching Gold layer
**Mitigation:** Comprehensive validation at each layer, alerts on quarantine spikes

**Risk:** Complex setup deterring portfolio viewers
**Mitigation:** One-command deployment script, excellent documentation

### Timeline Risks

**Risk:** Learning curve for Temporal/Flink
**Mitigation:** Start with basic examples, iterate complexity

**Risk:** Scope creep adding features
**Mitigation:** Stick to roadmap, mark extras as "future work"

**Risk:** Infrastructure issues on local machine
**Mitigation:** Cloud deployment option (k3s on EC2)

---

## Future Enhancements

### Phase 7+ (Optional)
- Real ML model training pipeline
- Multiple deployment environments (dev/staging/prod)
- CI/CD with GitHub Actions
- Grafana dashboards for metrics
- dbt documentation site
- API layer for querying analytics
- Real-time fraud detection with Flink CEP
- Cost optimization analysis

---

## Portfolio Presentation Strategy

### GitHub README Structure
1. Hero section with key metrics
2. Architecture diagram (visual impact)
3. Quick start guide (make it easy to run)
4. Technical deep-dives (show expertise)
5. Screenshots/GIFs (show don't tell)

### Job Application Talking Points
- "Built production-grade payment processing pipeline"
- "Implemented Butter-style upstream validation"
- "Orchestrated 10,000+ workflows with Temporal"
- "Achieved 99.9% data quality through multi-layer validation"
- "Designed ML-driven retry optimization system"

### Interview Preparation
- Explain validation layer decisions
- Discuss Temporal vs Dagster trade-offs
- Walk through failure scenario handling
- Describe schema evolution strategy
- Demo live system if possible

---

## References

### Documentation
- [Apache Kafka](https://kafka.apache.org/documentation/)
- [Apache Flink](https://nightlies.apache.org/flink/flink-docs-master/)
- [Temporal](https://docs.temporal.io/)
- [Apache Iceberg](https://iceberg.apache.org/docs/latest/)
- [DBT](https://docs.getdbt.com/)
- [JR Tool](https://jrnd.io/)

### Inspiration
- [Butter Payments Website](https://www.butterpayments.com/)
- [Medium: Streaming Data Lakehouse](https://medium.com/@gilles.philippart/build-a-streaming-data-lakehouse-with-apache-flink-kafka-iceberg-and-polaris-473c47e04525)
- [Temporal Payment Processing Examples](https://github.com/temporalio/samples-python)

### Community
- #data-engineering on relevant Slack communities
- r/dataengineering on Reddit
- Temporal community forum
- DBT community Slack

---

## Project Timeline

| Week | Phase | Key Deliverables | Status |
|------|-------|------------------|--------|
| 1-2 | Streaming Foundation | Kafka, Flink, JR pipeline | ✅ Completed |
| 3-4 | Upstream Validation | Multi-layer validation, quarantine | ✅ Completed |
| 5-6 | Temporal Integration | Workflows, retry logic | ⏳ Not Started |
| 7-8 | ML Simulation | Inference service, feature eng | ⏳ Not Started |
| 9 | Multi-Provider | Schema normalization | ⏳ Not Started |
| 10 | Documentation | README, blog, video | ⏳ Not Started |

---

## Next Steps

1. **Immediate (This Week)**
   - [ ] Review and approve this implementation plan
   - [ ] Set up dedicated project directory
   - [ ] Install JR CLI tool
   - [ ] Review Medium article in detail

2. **Week 1**
   - [ ] Add Kafka to Kubernetes
   - [ ] Create Flink custom image
   - [ ] Test Flink → Polaris connectivity
   - [ ] Create first JR payment template

3. **Week 2**
   - [ ] End-to-end streaming pipeline
   - [ ] Basic validation in Flink
   - [ ] Query payment events via Trino
   - [ ] Document architecture v1

---

## Contact & Support

**Project Owner:** Sean
**Target Company:** Butter Payments
**Timeline:** 10 weeks
**Start Date:** [To be determined]

**Questions or issues?**
- Review this plan section by section
- Start with Phase 1 and iterate
- Document learnings as you go
- Reach out for technical guidance as needed

---

**Document Version:** 1.0
**Last Updated:** 2025-11-17
**Next Review:** Start of Phase 1

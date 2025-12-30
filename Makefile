# Payment Pipeline Platform - Makefile
# Docker Compose automation for payment processing and analytics

.PHONY: help guide docker-up docker-down docker-build docker-restart docker-status docker-logs docker-polaris-init \
	all-up all-down all-status streaming-up streaming-down streaming-status \
	datalake-up datalake-down analytics-up analytics-down analytics-status ml-up ml-down dagster-refresh \
	pipeline-up pipeline-down pipeline-status pipeline-logs \
	gateway-up gateway-down gateway-logs gateway-simulator simulator-stop simulator-logs gateway-build gateway-test gateway-status gateway-test-send \
	transformer-up transformer-down transformer-logs transformer-build transformer-status transformer-counts \
	temporal-worker-up temporal-worker-down temporal-worker-logs temporal-worker-build temporal-worker-status temporal-logs inference-logs inference-build \
	superset-up superset-down superset-logs superset-status \
	mlops-up mlops-down mlops-logs mlops-status mlops-build feast-apply feast-status mlflow-ui

# Variables
DOCKER_DIR := infrastructure/docker
DOCKER_COMPOSE := docker compose -f $(DOCKER_DIR)/docker-compose.yml
# Services directories
SERVICES_DIR := services
GATEWAY_DIR := $(SERVICES_DIR)/gateway
TRANSFORMER_DIR := $(SERVICES_DIR)/transformer
TEMPORAL_DIR := $(SERVICES_DIR)/temporal
INFERENCE_DIR := $(SERVICES_DIR)/inference
DAGSTER_DIR := $(SERVICES_DIR)/dagster
FEAST_DIR := $(SERVICES_DIR)/feast
DBT_DIR := dbt
TOOLS_DIR := tools
SIMULATOR_DIR := $(TOOLS_DIR)/simulator

# Default target - show help
help:
	@echo "Payment Pipeline Platform - Available Commands"
	@echo ""
	@echo "3 Independent Stacks:"
	@echo ""
	@echo "  A) STREAMING - Real-time payment pipeline (self-contained)"
	@echo "     make streaming-up        - Start Kafka, Gateways, Transformers, Temporal Worker"
	@echo "     make streaming-down      - Stop streaming services"
	@echo "     make streaming-status    - Show streaming service status"
	@echo ""
	@echo "  B) DATALAKE - Batch analytics (MinIO, Polaris, Trino, Dagster)"
	@echo "     make datalake-up         - Start full lakehouse stack"
	@echo "     make datalake-down       - Stop datalake services"
	@echo "     make analytics-status    - Show datalake service status"
	@echo "     make dagster-refresh     - Rebuild Dagster user code after changes"
	@echo ""
	@echo "  C) ML - Feature store and experiment tracking (auto-starts Datalake)"
	@echo "     make ml-up               - Start Feast, MLflow (+ Datalake)"
	@echo "     make ml-down             - Stop ML services"
	@echo ""
	@echo "  ALL - Start everything"
	@echo "     make all-up              - Start all services"
	@echo "     make all-down            - Stop all services"
	@echo "     make all-status          - Show status of all services"
	@echo ""
	@echo "Add-ons:"
	@echo "  make superset-up            - Start Superset BI (requires datalake)"
	@echo "  make superset-down          - Stop Superset"
	@echo "  make gateway-simulator      - Start webhook traffic generator"
	@echo "  make simulator-stop         - Stop webhook simulator"
	@echo ""
	@echo "Utilities:"
	@echo "  make docker-build           - Build/rebuild all images"
	@echo "  make docker-status          - Show running containers"
	@echo "  make docker-logs            - View logs from all containers"
	@echo "  make transformer-counts     - Show Kafka message counts"
	@echo ""
	@echo "Run 'make guide' for step-by-step workflows and examples."
	@echo ""

# Step-by-step workflows and examples
guide:
	@echo "=========================================="
	@echo "   Workflows and Examples"
	@echo "=========================================="
	@echo ""
	@echo "Datalake Only (Batch Analytics):"
	@echo "---------------------------------"
	@echo "  1. make datalake-up                  # Start MinIO, Polaris, Trino, Dagster"
	@echo "  2. Open Dagster: http://localhost:3000"
	@echo "  3. Materialize payment_events asset  # Batch ingest to Iceberg"
	@echo "  4. Run DBT transformations           # Build star schema"
	@echo "  5. Query via Trino: http://localhost:8080"
	@echo ""
	@echo "Streaming Only (Real-time Processing):"
	@echo "---------------------------------------"
	@echo "  1. make streaming-up                 # Start Kafka, Gateway, Temporal"
	@echo "  2. make gateway-simulator            # Generate webhook traffic"
	@echo "  3. Open Temporal: http://localhost:8088"
	@echo "  4. make streaming-status             # Check streaming components"
	@echo ""
	@echo "Full Pipeline (Streaming + Datalake):"
	@echo "--------------------------------------"
	@echo "  1. make all-up                       # Start everything"
	@echo "  2. make gateway-simulator            # Generate webhook traffic"
	@echo "  3. make all-status                   # Check all components"
	@echo "  4. make docker-logs                  # View all logs"
	@echo ""
	@echo "ML Development (Feature Store + Experiment Tracking):"
	@echo "------------------------------------------------------"
	@echo "  1. make ml-up                        # Start Feast, MLflow (+ Datalake)"
	@echo "  2. make feast-apply                  # Apply feature definitions"
	@echo "  3. Open MLflow: http://localhost:5001"
	@echo "  4. make feast-status                 # Check feature store"
	@echo ""
	@echo "BI Dashboards (Superset):"
	@echo "--------------------------"
	@echo "  1. make datalake-up                  # Ensure Trino is running"
	@echo "  2. make superset-up                  # Start Superset"
	@echo "  3. Open Superset: http://localhost:8089"
	@echo "  4. Login: admin / admin"
	@echo ""
	@echo "Access URLs:"
	@echo "------------"
	@echo "  Gateway API:        http://localhost:8000"
	@echo "  Dagster:            http://localhost:3000"
	@echo "  Trino:              http://localhost:8080"
	@echo "  Temporal UI:        http://localhost:8088"
	@echo "  Superset:           http://localhost:8089"
	@echo "  MinIO Console:      http://localhost:9001 (admin/password)"
	@echo "  Polaris API:        http://localhost:8181"
	@echo "  MLflow UI:          http://localhost:5001"
	@echo "  Feast Server:       http://localhost:6566"
	@echo ""

##################################################
# GRANULAR STARTUP COMMANDS
##################################################

# ==========================================
# A) STREAMING - Payment pipeline (self-contained)
# ==========================================
streaming-up:
	@echo "=========================================="
	@echo "   Starting Streaming Stack"
	@echo "=========================================="
	@echo ""
	@echo "Components: Kafka, Gateways, Transformers, Temporal, Temporal Worker"
	@echo ""
	@cd $(DOCKER_DIR) && docker compose up -d kafka-broker
	@echo "Waiting for Kafka..."
	@sleep 5
	@cd $(DOCKER_DIR) && docker compose --profile gateway up -d traefik stripe-gateway square-gateway adyen-gateway braintree-gateway
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer up -d stripe-transformer square-transformer adyen-transformer braintree-transformer
	@cd $(DOCKER_DIR) && docker compose --profile temporal up -d temporal-db temporal temporal-ui payments-db inference-service temporal-worker
	@echo ""
	@echo "Streaming stack started!"
	@echo "  Temporal UI: http://localhost:8088"
	@echo "  Gateway:     http://localhost:8000"

streaming-down:
	@echo "Stopping Streaming Stack..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator stop
	@cd $(DOCKER_DIR) && docker compose stop kafka-broker
	@echo "Streaming stopped"

# ==========================================
# B) DATALAKE - Batch analytics (MinIO + Polaris + Trino + Dagster)
# ==========================================
datalake-up:
	@echo "=========================================="
	@echo "   Starting Datalake Stack"
	@echo "=========================================="
	@echo ""
	@echo "Components: MinIO, Polaris, Payments DB, Trino, Dagster"
	@echo ""
	@cd $(DOCKER_DIR) && docker compose up -d minio minio-client polaris polaris-init
	@cd $(DOCKER_DIR) && docker compose --profile temporal up -d payments-db
	@cd $(DOCKER_DIR) && docker compose up -d postgres trino dbt-init dagster-user-code dagster-webserver dagster-daemon
	@echo ""
	@echo "Datalake started!"
	@echo "  Dagster:      http://localhost:3000"
	@echo "  Trino:        http://localhost:8080"
	@echo "  MinIO:        http://localhost:9001"
	@echo "  Polaris:      http://localhost:8181"
	@echo "  Payments DB:  localhost:5433"

datalake-down:
	@echo "Stopping Datalake Stack..."
	@cd $(DOCKER_DIR) && docker compose stop dagster-webserver dagster-daemon dagster-user-code trino dbt-init postgres
	@cd $(DOCKER_DIR) && docker compose --profile temporal stop payments-db
	@cd $(DOCKER_DIR) && docker compose stop minio minio-client polaris polaris-init
	@echo "Datalake stopped"

# analytics-up/down are aliases for datalake (backwards compatibility)
analytics-up: datalake-up
analytics-down: datalake-down

# ==========================================
# C) ML - Feature store & experiment tracking (requires Datalake)
# ==========================================
ml-up: datalake-up
	@echo "=========================================="
	@echo "   Starting ML Stack"
	@echo "=========================================="
	@echo ""
	@echo "Components: Feast (feature store), MLflow (tracking)"
	@echo ""
	@cd $(DOCKER_DIR) && docker compose --profile mlops up -d
	@echo ""
	@echo "ML stack started!"
	@echo "  MLflow:  http://localhost:5001"
	@echo "  Feast:   http://localhost:6566"

ml-down:
	@echo "Stopping ML Stack..."
	@cd $(DOCKER_DIR) && docker compose --profile mlops stop
	@echo "ML stopped"

# ==========================================
# ALL - Start everything
# ==========================================
all-up:
	@echo "=========================================="
	@echo "   Starting ALL Services"
	@echo "=========================================="
	@echo ""
	@echo "This starts the complete stack:"
	@echo "  - Streaming: Kafka, Gateway, Transformer, Temporal Worker"
	@echo "  - Analytics: MinIO, Polaris, Trino, Dagster"
	@echo "  - MLOps: Feast, Redis, MLflow"
	@echo "  - Simulators: Webhook traffic generators (all providers)"
	@echo "  - Storage: Payments DB, Dagster DB"
	@echo ""
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator --profile mlops up -d --build
	@echo ""
	@echo "=========================================="
	@echo "   All Services Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URLs:"
	@echo "  Gateway API:        http://localhost:8000"
	@echo "  Dagster:            http://localhost:3000"
	@echo "  Trino:              http://localhost:8080"
	@echo "  MinIO Console:      http://localhost:9001"
	@echo "  Polaris API:        http://localhost:8181"
	@echo "  Temporal UI:        http://localhost:8088"
	@echo "  Inference Service:  http://localhost:8002"
	@echo "  MLflow UI:          http://localhost:5001"
	@echo "  Feast Server:       http://localhost:6566"
	@echo ""
	@echo "Next steps:"
	@echo "  make all-status          - Check all services"
	@echo "  make docker-logs         - View all logs"

# Stop ALL services
all-down:
	@echo "Stopping ALL services..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator --profile mlops down
	@echo "All services stopped"

# Show streaming pipeline status
streaming-status:
	@echo "=========================================="
	@echo "   Streaming Pipeline Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q kafka-broker; then echo "  [OK] Kafka Broker"; else echo "  [--] Kafka Broker"; fi
	@if docker ps | grep -q stripe-gateway; then echo "  [OK] Stripe Gateway"; else echo "  [--] Stripe Gateway"; fi
	@if docker ps | grep -q stripe-transformer; then echo "  [OK] Stripe Transformer"; else echo "  [--] Stripe Transformer"; fi
	@if docker ps | grep -q payments-db; then echo "  [OK] Payments DB"; else echo "  [--] Payments DB"; fi
	@if docker ps | grep -q "temporal$$"; then echo "  [OK] Temporal"; else echo "  [--] Temporal"; fi
	@if docker ps | grep -q temporal-ui; then echo "  [OK] Temporal UI"; else echo "  [--] Temporal UI"; fi
	@if docker ps | grep -q inference-service; then echo "  [OK] Inference Service"; else echo "  [--] Inference Service"; fi
	@if docker ps | grep -q temporal-worker; then echo "  [OK] Temporal Worker"; else echo "  [--] Temporal Worker"; fi
	@echo ""
	@echo "Commands:"
	@echo "  make streaming-up       - Start streaming pipeline"
	@echo "  make streaming-down     - Stop streaming pipeline"
	@echo "  make pipeline-logs      - View logs"

# Rebuild and restart Dagster user code (after code changes)
dagster-refresh:
	@echo "Refreshing Dagster user code..."
	@echo "Step 1/3: Stopping Dagster services..."
	@cd $(DOCKER_DIR) && docker compose stop dagster-daemon dagster-webserver dagster-user-code
	@echo "Step 2/3: Rebuilding user code image..."
	@cd $(DOCKER_DIR) && docker compose build --no-cache dagster-user-code
	@echo "Step 3/3: Starting Dagster services..."
	@cd $(DOCKER_DIR) && docker compose up -d dagster-user-code dagster-webserver dagster-daemon
	@echo ""
	@echo "Dagster user code refreshed. Waiting for services to be ready..."
	@sleep 5
	@if docker ps | grep -q dagster_user_code; then echo "  [OK] Dagster User Code"; else echo "  [FAIL] Dagster User Code"; fi
	@if docker ps | grep -q dagster-webserver; then echo "  [OK] Dagster Webserver"; else echo "  [FAIL] Dagster Webserver"; fi
	@if docker ps | grep -q dagster-daemon; then echo "  [OK] Dagster Daemon"; else echo "  [FAIL] Dagster Daemon"; fi
	@echo ""
	@echo "Access Dagster at: http://localhost:3000"

# Show batch analytics status
analytics-status:
	@echo "=========================================="
	@echo "   Batch Analytics Stack Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q minio; then echo "  [OK] MinIO"; else echo "  [--] MinIO"; fi
	@if docker ps | grep -q polaris; then echo "  [OK] Polaris"; else echo "  [--] Polaris"; fi
	@if docker ps | grep -q trino; then echo "  [OK] Trino"; else echo "  [--] Trino"; fi
	@if docker ps | grep -q payments-db; then echo "  [OK] Payments DB"; else echo "  [--] Payments DB"; fi
	@if docker ps | grep -q "postgres$$"; then echo "  [OK] Dagster DB"; else echo "  [--] Dagster DB"; fi
	@if docker ps | grep -q dagster_user_code; then echo "  [OK] Dagster User Code"; else echo "  [--] Dagster User Code"; fi
	@if docker ps | grep -q dagster-webserver; then echo "  [OK] Dagster Webserver"; else echo "  [--] Dagster Webserver"; fi
	@if docker ps | grep -q dagster-daemon; then echo "  [OK] Dagster Daemon"; else echo "  [--] Dagster Daemon"; fi
	@if docker ps --format "{{.Names}}" | grep -q "^superset$$"; then echo "  [OK] Superset"; else echo "  [--] Superset (run: make superset-up)"; fi
	@echo ""
	@echo "Access URLs:"
	@echo "  Dagster:            http://localhost:3000"
	@echo "  Trino:              http://localhost:8080"
	@echo "  Superset:           http://localhost:8089"
	@echo "  MinIO Console:      http://localhost:9001"
	@echo "  Polaris API:        http://localhost:8181"
	@echo ""
	@echo "Commands:"
	@echo "  make analytics-up       - Start analytics stack"
	@echo "  make analytics-down     - Stop analytics stack"
	@echo "  make dagster-refresh    - Rebuild Dagster user code"
	@echo "  make superset-up        - Start Superset BI"
	@echo "  make docker-logs        - View all logs"

# Show status of all services
all-status: streaming-status analytics-status
	@echo ""
	@echo "=========================================="
	@echo "   Combined Status Complete"
	@echo "=========================================="

##################################################
# DOCKER COMPOSE COMMANDS
##################################################

# Start all Docker Compose services (same as all-up)
docker-up: all-up

# Stop and remove all Docker Compose services
docker-down: all-down

# Build/rebuild Docker images
docker-build:
	@echo "Building Docker images..."
	@cd $(DOCKER_DIR) && docker compose build
	@echo "Images built"

# Restart all Docker Compose services
docker-restart:
	@echo "Restarting Docker Compose stack..."
	@cd $(DOCKER_DIR) && docker compose restart
	@echo "Stack restarted"

# Show detailed status of Docker Compose services
docker-status:
	@echo "=========================================="
	@echo "   Docker Compose Services Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "----------------"
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile superset --profile mlops ps
	@echo ""
	@echo "Service URLs & Ports:"
	@echo "---------------------"
	@echo "  Gateway API:       http://localhost:8000"
	@echo "  Dagster:           http://localhost:3000"
	@echo "  Trino:             http://localhost:8080"
	@echo "  Temporal UI:       http://localhost:8088"
	@echo "  Superset:          http://localhost:8089"
	@echo "  Polaris API:       http://localhost:8181"
	@echo "  Inference Service: http://localhost:8002"
	@echo "  Kafka Broker:      localhost:9092"
	@echo "  MinIO S3 API:      http://localhost:9000"
	@echo "  MinIO Console:     http://localhost:9001 (admin/password)"
	@echo ""
	@echo "MLOps Services:"
	@echo "---------------"
	@echo "  MLflow UI:         http://localhost:5001"
	@echo "  Feast Server:      http://localhost:6566"
	@echo ""

# View logs from all Docker Compose services
docker-logs:
	@echo "Viewing Docker Compose logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose logs -f

# Initialize Polaris warehouse (Docker Compose setup)
docker-polaris-init:
	@echo "Initializing Polaris warehouse..."
	@if ! docker ps | grep -q polaris; then \
		echo "Error: Polaris container not running"; \
		echo "   Start Docker Compose first: make analytics-up"; \
		exit 1; \
	fi
	@echo "Running Polaris initialization script..."
	@bash $(DOCKER_DIR)/polaris/init-polaris.sh
	@echo ""
	@echo "Polaris warehouse initialized!"

##################################################
# PAYMENT PIPELINE COMMANDS
##################################################

# Start full payment pipeline
pipeline-up:
	@echo "=========================================="
	@echo "   Starting Payment Pipeline"
	@echo "=========================================="
	@echo ""
	@echo "Components:"
	@echo "  - Kafka Broker (message queue)"
	@echo "  - Payment Gateway (webhook receiver)"
	@echo "  - Transformer (validation & normalization)"
	@echo "  - Temporal (workflow orchestration)"
	@echo "  - Inference Service (ML mock endpoints)"
	@echo "  - Temporal Worker (Temporal workflows)"
	@echo ""
	@echo "Starting Kafka..."
	@cd $(DOCKER_DIR) && docker compose up -d kafka-broker
	@echo "Waiting for Kafka to be ready..."
	@sleep 5
	@echo ""
	@echo "Starting Gateways..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway up -d traefik stripe-gateway square-gateway adyen-gateway braintree-gateway
	@sleep 3
	@echo ""
	@echo "Starting Transformers..."
	@cd $(DOCKER_DIR) && docker compose --profile transformer up -d stripe-transformer square-transformer adyen-transformer braintree-transformer
	@sleep 2
	@echo ""
	@echo "Starting Temporal..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal up -d temporal-db temporal temporal-ui payments-db
	@echo "Waiting for Temporal to be ready..."
	@sleep 10
	@echo ""
	@echo "Starting Inference Service and Temporal Worker..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal up -d inference-service temporal-worker
	@sleep 3
	@echo ""
	@echo "=========================================="
	@echo "   Payment Pipeline Started!"
	@echo "=========================================="
	@echo ""
	@echo "Services:"
	@echo "  Gateway API:        http://localhost:8000"
	@echo "  Gateway Health:     http://localhost:8000/health"
	@echo "  Inference Service:  http://localhost:8002"
	@echo "  Temporal UI:        http://localhost:8088"
	@echo "  Kafka Broker:       localhost:9092"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Start simulator:  make gateway-simulator"
	@echo "  2. View logs:        make pipeline-logs"
	@echo "  3. Check status:     make pipeline-status"
	@echo "  4. View counts:      make transformer-counts"

# Stop full payment pipeline
pipeline-down:
	@echo "Stopping Payment Pipeline..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator stop \
		temporal-worker inference-service temporal-ui temporal temporal-db \
		stripe-transformer square-transformer adyen-transformer braintree-transformer \
		traefik stripe-gateway square-gateway adyen-gateway braintree-gateway \
		stripe-simulator square-simulator adyen-simulator braintree-simulator \
		kafka-broker 2>/dev/null || true
	@echo "Payment Pipeline stopped"

# Show all pipeline component status
pipeline-status: gateway-status transformer-status temporal-worker-status

# View all pipeline logs
pipeline-logs:
	@echo "Viewing Pipeline logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal logs -f \
		kafka-broker traefik stripe-gateway square-gateway adyen-gateway braintree-gateway \
		stripe-transformer square-transformer adyen-transformer braintree-transformer \
		temporal-worker inference-service temporal

##################################################
# PAYMENT GATEWAY COMMANDS
##################################################

# Start payment gateways with Kafka
gateway-up:
	@echo "Starting Payment Gateways with Kafka..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway up -d kafka-broker traefik stripe-gateway square-gateway adyen-gateway braintree-gateway
	@echo ""
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@echo ""
	@echo "Payment Gateway started!"
	@echo ""
	@echo "Access URLs:"
	@echo "  Gateway API:     http://localhost:8000"
	@echo "  Gateway Health:  http://localhost:8000/health"
	@echo "  Kafka Broker:    localhost:9092"
	@echo ""
	@echo "Webhook Endpoints:"
	@echo "  Stripe:  POST http://localhost:8000/webhooks/stripe/"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Send test webhook:     make gateway-test-send"
	@echo "  2. Start simulator:       make gateway-simulator"
	@echo "  3. View logs:             make gateway-logs"

# Stop payment gateway
gateway-down:
	@echo "Stopping Payment Gateways..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile simulator stop \
		traefik stripe-gateway square-gateway adyen-gateway braintree-gateway \
		stripe-simulator square-simulator adyen-simulator braintree-simulator
	@echo "Payment Gateways stopped"

# View payment gateway logs
gateway-logs:
	@echo "Viewing Payment Gateway logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose logs -f traefik stripe-gateway square-gateway adyen-gateway braintree-gateway

# Start webhook simulators (all providers)
gateway-simulator:
	@echo "Starting Webhook Simulators (all providers)..."
	@echo ""
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator up -d \
		stripe-simulator square-simulator adyen-simulator braintree-simulator
	@echo ""
	@echo "Simulators started! Generating webhooks at 2/sec per provider"
	@echo ""
	@echo "Commands:"
	@echo "  make simulator-stop   - Stop all simulators"
	@echo "  make simulator-logs   - View simulator logs"

# Stop webhook simulators
simulator-stop:
	@echo "Stopping Webhook Simulators..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator stop \
		stripe-simulator square-simulator adyen-simulator braintree-simulator
	@echo "Webhook Simulators stopped"

# View webhook simulator logs
simulator-logs:
	@echo "Viewing Simulator logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal --profile simulator logs -f \
		stripe-simulator square-simulator adyen-simulator braintree-simulator

# Build payment gateway Docker images (all providers)
gateway-build:
	@echo "Building Payment Gateway Docker images..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway build \
		stripe-gateway square-gateway adyen-gateway braintree-gateway
	@echo "Payment Gateway images built"

# Run payment gateway unit tests
gateway-test:
	@echo "Running Payment Gateway unit tests..."
	@cd $(GATEWAY_DIR) && uv sync && uv run pytest tests/ -v
	@echo "Tests completed"

# Send a single test webhook
gateway-test-send:
	@echo "Sending test webhook to gateway..."
	@if ! docker ps | grep -q stripe-gateway; then \
		echo "Error: Stripe Gateway not running"; \
		echo "   Start it first: make gateway-up"; \
		exit 1; \
	fi
	@cd $(SIMULATOR_DIR) && python -m simulator.main send --type payment_intent.succeeded
	@echo ""
	@echo "Test webhook sent!"

# Show payment gateway status
gateway-status:
	@echo "=========================================="
	@echo "   Payment Gateway Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q traefik; then \
		echo "  [OK] Traefik (Router): running"; \
	else \
		echo "  [--] Traefik (Router): not running"; \
	fi
	@if docker ps | grep -q stripe-gateway; then \
		echo "  [OK] Stripe Gateway: running"; \
	else \
		echo "  [--] Stripe Gateway: not running"; \
	fi
	@if docker ps | grep -q square-gateway; then \
		echo "  [OK] Square Gateway: running"; \
	else \
		echo "  [--] Square Gateway: not running"; \
	fi
	@if docker ps | grep -q adyen-gateway; then \
		echo "  [OK] Adyen Gateway: running"; \
	else \
		echo "  [--] Adyen Gateway: not running"; \
	fi
	@if docker ps | grep -q braintree-gateway; then \
		echo "  [OK] Braintree Gateway: running"; \
	else \
		echo "  [--] Braintree Gateway: not running"; \
	fi
	@if docker ps | grep -q stripe-simulator; then \
		echo "  [OK] Stripe Simulator: running"; \
	else \
		echo "  [--] Stripe Simulator: not running"; \
	fi
	@echo ""
	@echo "Health Check:"
	@echo "-------------"
	@if docker ps | grep -q traefik; then \
		curl -s http://localhost:8000/webhooks/stripe/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  Stripe Gateway not responding"; \
	else \
		echo "  Traefik not running"; \
	fi
	@echo ""
	@echo "Kafka Topics (webhooks.*):"
	@echo "--------------------------"
	@if docker ps | grep -q kafka-broker; then \
		docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
			/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092 2>/dev/null | grep "webhooks" || echo "  No webhook topics found"; \
	else \
		echo "  Kafka not running"; \
	fi
	@echo ""
	@echo "Commands:"
	@echo "  make gateway-up          - Start gateway"
	@echo "  make gateway-logs        - View logs"
	@echo "  make gateway-simulator   - Start traffic generator"
	@echo "  make gateway-test-send   - Send single test webhook"

##################################################
# TRANSFORMER COMMANDS
##################################################

# Build transformer Docker image
transformer-build:
	@echo "Building Transformer Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer build transformer
	@echo "Transformer image built"

# Start transformer with gateway
transformer-up: gateway-up
	@echo ""
	@echo "Starting Transformer..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer up -d stripe-transformer
	@echo ""
	@echo "Transformer started!"
	@echo ""
	@echo "Access URLs:"
	@echo "  Gateway API:      http://localhost:8000"
	@echo ""
	@echo "Kafka Topics:"
	@echo "  Input:   webhooks.stripe.payment_intent"
	@echo "           webhooks.stripe.charge"
	@echo "           webhooks.stripe.refund"
	@echo "  Output:  payments.normalized"
	@echo "  DLQ:     payments.validation.dlq"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Start simulator:  make gateway-simulator"
	@echo "  2. View logs:        make transformer-logs"
	@echo "  3. Check status:     make transformer-status"

# Stop transformer
transformer-down:
	@echo "Stopping Transformer..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer stop stripe-transformer
	@echo "Transformer stopped"

# View transformer logs
transformer-logs:
	@echo "Viewing Transformer logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer logs -f stripe-transformer

# Show transformer status
transformer-status:
	@echo "=========================================="
	@echo "   Transformer Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -qE "(stripe|square|adyen|braintree)-transformer"; then \
		echo "  [OK] Transformer: running"; \
	else \
		echo "  [--] Transformer: not running"; \
	fi
	@if docker ps | grep -q stripe-gateway; then \
		echo "  [OK] Gateway: running"; \
	else \
		echo "  [--] Gateway: not running"; \
	fi
	@if docker ps | grep -q kafka-broker; then \
		echo "  [OK] Kafka: running"; \
	else \
		echo "  [--] Kafka: not running"; \
	fi
	@echo ""
	@echo "Kafka Topics:"
	@echo "-------------"
	@if docker ps | grep -q kafka-broker; then \
		docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
			/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092 2>/dev/null | grep -E "(payments\.|webhooks\.)" || echo "  No payment topics found"; \
	else \
		echo "  Kafka not running"; \
	fi
	@echo ""
	@echo "Commands:"
	@echo "  make transformer-up      - Start transformer with gateway"
	@echo "  make transformer-logs    - View transformer logs"
	@echo "  make transformer-counts  - Show message counts"
	@echo "  make transformer-down    - Stop transformer"

# Check message counts
transformer-counts:
	@echo "Kafka Topic Message Counts:"
	@echo "==========================="
	@if docker ps | grep -q kafka-broker; then \
		echo ""; \
		echo "Input Topics:"; \
		for topic in webhooks.stripe.payment_intent webhooks.stripe.charge webhooks.stripe.refund; do \
			count=$$(docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
				/opt/kafka/bin/kafka-run-class.sh kafka.tools.GetOffsetShell \
				--broker-list localhost:9092 --topic $$topic --time -1 2>/dev/null | \
				awk -F: '{sum += $$3} END {print sum}' 2>/dev/null || echo "0"); \
			printf "  %-35s %s messages\n" "$$topic:" "$$count"; \
		done; \
		echo ""; \
		echo "Output Topics:"; \
		for topic in payments.normalized payments.validation.dlq; do \
			count=$$(docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
				/opt/kafka/bin/kafka-run-class.sh kafka.tools.GetOffsetShell \
				--broker-list localhost:9092 --topic $$topic --time -1 2>/dev/null | \
				awk -F: '{sum += $$3} END {print sum}' 2>/dev/null || echo "0"); \
			printf "  %-35s %s messages\n" "$$topic:" "$$count"; \
		done; \
	else \
		echo "Kafka not running"; \
	fi

##################################################
# TEMPORAL WORKER COMMANDS
##################################################

# Build temporal worker Docker image
temporal-worker-build:
	@echo "Building Temporal Worker Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal build temporal-worker
	@echo "Temporal Worker image built"

# Build inference service Docker image
inference-build:
	@echo "Building Inference Service Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal build inference-service
	@echo "Inference Service image built"

# Start temporal worker with all dependencies
temporal-worker-up: transformer-up
	@echo ""
	@echo "Starting Temporal and Temporal Worker..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile transformer --profile temporal up -d temporal-db temporal temporal-ui inference-service temporal-worker
	@echo ""
	@echo "Temporal Worker started!"
	@echo ""
	@echo "Access Points:"
	@echo "  - Temporal UI:        http://localhost:8088"
	@echo "  - Inference Service:  http://localhost:8002"
	@echo ""
	@echo "Commands:"
	@echo "  make temporal-worker-logs    - View temporal worker logs"
	@echo "  make temporal-worker-status  - Show temporal worker status"
	@echo "  make temporal-worker-down    - Stop temporal worker"

# Stop temporal worker
temporal-worker-down:
	@echo "Stopping Temporal Worker and Temporal..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal stop temporal-worker inference-service temporal-ui temporal temporal-db
	@echo "Temporal Worker stopped"

# View temporal worker logs
temporal-worker-logs:
	@echo "Viewing Temporal Worker logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal logs -f temporal-worker

# View temporal logs
temporal-logs:
	@echo "Viewing Temporal logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal logs -f temporal

# View inference service logs
inference-logs:
	@echo "Viewing Inference Service logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile temporal logs -f inference-service

# Show temporal worker status
temporal-worker-status:
	@echo "=========================================="
	@echo "   Temporal Worker Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q temporal-worker; then \
		echo "  [OK] Temporal Worker: running"; \
	else \
		echo "  [--] Temporal Worker: not running"; \
	fi
	@if docker ps | grep -q inference-service; then \
		echo "  [OK] Inference Service: running"; \
	else \
		echo "  [--] Inference Service: not running"; \
	fi
	@if docker ps | grep -q temporal-ui; then \
		echo "  [OK] Temporal UI: running"; \
	else \
		echo "  [--] Temporal UI: not running"; \
	fi
	@if docker ps | grep -q "temporal$$"; then \
		echo "  [OK] Temporal: running"; \
	else \
		echo "  [--] Temporal: not running"; \
	fi
	@if docker ps | grep -q temporal-db; then \
		echo "  [OK] Temporal DB: running"; \
	else \
		echo "  [--] Temporal DB: not running"; \
	fi
	@echo ""
	@echo "Access Points:"
	@echo "--------------"
	@echo "  - Temporal UI:        http://localhost:8088"
	@echo "  - Inference Service:  http://localhost:8002/health"
	@echo ""
	@echo "Commands:"
	@echo "  make temporal-worker-up      - Start temporal worker with dependencies"
	@echo "  make temporal-worker-logs    - View temporal worker logs"
	@echo "  make temporal-logs           - View temporal logs"
	@echo "  make inference-logs          - View inference service logs"
	@echo "  make temporal-worker-down    - Stop temporal worker"

##################################################
# APACHE SUPERSET COMMANDS
##################################################

# Start Superset with analytics stack
superset-up:
	@echo "=========================================="
	@echo "   Starting Apache Superset"
	@echo "=========================================="
	@echo ""
	@echo "Components:"
	@echo "  - Superset DB (PostgreSQL metadata store)"
	@echo "  - Superset Redis (caching & async tasks)"
	@echo "  - Superset Init (migrations & admin user)"
	@echo "  - Superset (web application)"
	@echo "  - Superset Worker (async tasks/alerts)"
	@echo ""
	@echo "NOTE: Analytics stack (Trino, Polaris, MinIO) must be running."
	@echo "      Run 'make analytics-up' first if not already started."
	@echo ""
	@echo "Starting Superset infrastructure (DB + Redis)..."
	@cd $(DOCKER_DIR) && docker compose --profile superset up -d superset-db superset-redis
	@echo "Waiting for database to be ready..."
	@sleep 10
	@echo ""
	@echo "Running initialization (migrations + admin user)..."
	@cd $(DOCKER_DIR) && docker compose --profile superset up -d superset-init
	@sleep 30
	@echo ""
	@echo "Starting Superset application..."
	@cd $(DOCKER_DIR) && docker compose --profile superset up -d superset superset-worker
	@echo ""
	@echo "=========================================="
	@echo "   Apache Superset Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URL:"
	@echo "  Superset:  http://localhost:8089"
	@echo ""
	@echo "Login:"
	@echo "  Username: admin"
	@echo "  Password: admin"
	@echo ""
	@echo "Pre-configured Connection:"
	@echo "  Database: Lakehouse (Trino)"
	@echo "  Schema:   data"
	@echo ""
	@echo "Available Analytics Tables:"
	@echo "  - analytics_payment_summary    (KPI dashboard)"
	@echo "  - analytics_payment_trends     (time-series charts)"
	@echo "  - analytics_customer_segments  (segmentation analysis)"
	@echo "  - analytics_risk_overview      (fraud monitoring)"
	@echo "  - analytics_provider_comparison (provider analysis)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Login to Superset"
	@echo "  2. Go to SQL Lab and select 'Lakehouse (Trino)' database"
	@echo "  3. Run: SELECT * FROM data.analytics_payment_summary"
	@echo "  4. Create datasets and build dashboards!"

# Stop Superset
superset-down:
	@echo "Stopping Apache Superset..."
	@cd $(DOCKER_DIR) && docker compose --profile superset stop \
		superset superset-worker superset-init superset-redis superset-db 2>/dev/null || true
	@echo "Apache Superset stopped"

# View Superset logs
superset-logs:
	@echo "Viewing Superset logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile superset logs -f superset superset-init superset-worker

# Show Superset status
superset-status:
	@echo "=========================================="
	@echo "   Apache Superset Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q superset-db; then echo "  [OK] Superset DB"; else echo "  [--] Superset DB"; fi
	@if docker ps | grep -q superset-redis; then echo "  [OK] Superset Redis"; else echo "  [--] Superset Redis"; fi
	@if docker ps --format "{{.Names}}" | grep -q "^superset$$"; then echo "  [OK] Superset"; else echo "  [--] Superset"; fi
	@if docker ps | grep -q superset-worker; then echo "  [OK] Superset Worker"; else echo "  [--] Superset Worker"; fi
	@echo ""
	@echo "Trino Connection (required):"
	@echo "----------------------------"
	@if docker ps | grep -q trino; then echo "  [OK] Trino: running"; else echo "  [--] Trino: not running (run: make analytics-up)"; fi
	@echo ""
	@echo "Access URL:"
	@echo "  Superset:  http://localhost:8089"
	@echo ""
	@echo "Commands:"
	@echo "  make superset-up      - Start Superset"
	@echo "  make superset-logs    - View logs"
	@echo "  make superset-down    - Stop Superset"

##################################################
# MLOPS COMMANDS (Feast + MLflow)
##################################################

# Start MLOps stack (Feast + MLflow)
mlops-up:
	@echo "=========================================="
	@echo "   Starting MLOps Stack"
	@echo "=========================================="
	@echo ""
	@echo "Components:"
	@echo "  - Feast Redis (online feature store)"
	@echo "  - Feast Server (feature serving)"
	@echo "  - MLflow DB (experiment metadata)"
	@echo "  - MLflow Server (tracking & model registry)"
	@echo ""
	@echo "NOTE: MinIO must be running for MLflow artifacts."
	@echo "      Run 'make analytics-up' first if not already started."
	@echo ""
	@echo "Starting MinIO (if not running)..."
	@cd $(DOCKER_DIR) && docker compose up -d minio minio-client
	@sleep 3
	@echo ""
	@echo "Starting MLOps infrastructure..."
	@cd $(DOCKER_DIR) && docker compose --profile mlops up -d
	@echo ""
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo ""
	@echo "=========================================="
	@echo "   MLOps Stack Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URLs:"
	@echo "  MLflow UI:          http://localhost:5001"
	@echo "  Feast Server:       http://localhost:6566"
	@echo "  MinIO Console:      http://localhost:9001"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Apply Feast features:  make feast-apply"
	@echo "  2. Check status:          make mlops-status"
	@echo "  3. View MLflow UI:        make mlflow-ui"

# Stop MLOps stack
mlops-down:
	@echo "Stopping MLOps stack..."
	@cd $(DOCKER_DIR) && docker compose --profile mlops stop \
		feast-server feast-redis mlflow-server mlflow-db mlflow-init 2>/dev/null || true
	@echo "MLOps stack stopped"

# View MLOps logs
mlops-logs:
	@echo "Viewing MLOps logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile mlops logs -f \
		feast-server feast-redis mlflow-server mlflow-db

# Build MLOps Docker images
mlops-build:
	@echo "Building MLOps Docker images..."
	@cd $(DOCKER_DIR) && docker compose --profile mlops build feast-server
	@echo "MLOps images built"

# Show MLOps status
mlops-status:
	@echo "=========================================="
	@echo "   MLOps Stack Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q feast-redis; then echo "  [OK] Feast Redis"; else echo "  [--] Feast Redis"; fi
	@if docker ps | grep -q feast-server; then echo "  [OK] Feast Server"; else echo "  [--] Feast Server"; fi
	@if docker ps | grep -q mlflow-db; then echo "  [OK] MLflow DB"; else echo "  [--] MLflow DB"; fi
	@if docker ps | grep -q mlflow-server; then echo "  [OK] MLflow Server"; else echo "  [--] MLflow Server"; fi
	@echo ""
	@echo "MinIO (required for MLflow artifacts):"
	@echo "--------------------------------------"
	@if docker ps | grep -q minio; then echo "  [OK] MinIO: running"; else echo "  [--] MinIO: not running (run: make analytics-up)"; fi
	@echo ""
	@echo "Access URLs:"
	@echo "  MLflow UI:      http://localhost:5001"
	@echo "  Feast Server:   http://localhost:6566"
	@echo ""
	@echo "Commands:"
	@echo "  make mlops-up       - Start MLOps stack"
	@echo "  make mlops-logs     - View logs"
	@echo "  make feast-apply    - Apply Feast features"
	@echo "  make mlops-down     - Stop MLOps stack"

# Apply Feast feature definitions
feast-apply:
	@echo "Applying Feast feature definitions..."
	@if ! docker ps | grep -q feast-server; then \
		echo "Error: Feast server not running"; \
		echo "   Start it first: make mlops-up"; \
		exit 1; \
	fi
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec feast-server feast apply
	@echo ""
	@echo "Feast features applied!"

# Show Feast feature store status
feast-status:
	@echo "=========================================="
	@echo "   Feast Feature Store Status"
	@echo "=========================================="
	@echo ""
	@if docker ps | grep -q feast-server; then \
		echo "Feature Views:"; \
		docker compose -f $(DOCKER_DIR)/docker-compose.yml exec feast-server feast feature-views list 2>/dev/null || echo "  Run 'make feast-apply' first"; \
		echo ""; \
		echo "Feature Services:"; \
		docker compose -f $(DOCKER_DIR)/docker-compose.yml exec feast-server feast feature-services list 2>/dev/null || echo "  Run 'make feast-apply' first"; \
	else \
		echo "Feast server not running. Start with: make mlops-up"; \
	fi

# Show MLflow UI info
mlflow-ui:
	@echo "=========================================="
	@echo "   MLflow Tracking Server"
	@echo "=========================================="
	@echo ""
	@if docker ps | grep -q mlflow-server; then \
		echo "MLflow UI:        http://localhost:5001"; \
		echo ""; \
		echo "To use MLflow from Python:"; \
		echo "  import mlflow"; \
		echo "  mlflow.set_tracking_uri('http://localhost:5001')"; \
		echo ""; \
		echo "Environment variables for training containers:"; \
		echo "  MLFLOW_TRACKING_URI=http://mlflow-server:5000"; \
		echo "  MLFLOW_S3_ENDPOINT_URL=http://minio:9000"; \
	else \
		echo "MLflow server not running. Start with: make mlops-up"; \
	fi

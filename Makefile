# Payment Pipeline Platform - Makefile
# Docker Compose automation for payment processing and analytics

.PHONY: help docker-up docker-down docker-build docker-restart docker-status docker-logs docker-polaris-init \
	all-up all-down all-status streaming-up streaming-down streaming-status analytics-up analytics-down analytics-status \
	pipeline-up pipeline-down pipeline-status pipeline-logs \
	gateway-up gateway-down gateway-logs gateway-simulator simulator-stop simulator-logs gateway-build gateway-test gateway-status gateway-test-send \
	normalizer-up normalizer-down normalizer-logs normalizer-build normalizer-status normalizer-counts \
	orchestrator-up orchestrator-down orchestrator-logs orchestrator-build orchestrator-status temporal-logs inference-logs inference-build \
	superset-up superset-down superset-logs superset-status

# Variables
DOCKER_DIR := infrastructure/docker
DOCKER_COMPOSE := docker compose -f $(DOCKER_DIR)/docker-compose.yml
PAYMENT_PIPELINE_DIR := payment-pipeline

# Default target - show help
help:
	@echo "Payment Pipeline Platform - Available Commands"
	@echo ""
	@echo "Quick Start:"
	@echo "  make analytics-up           - Start batch analytics (Dagster, Trino, Polaris, MinIO)"
	@echo "  make streaming-up           - Start streaming pipeline (Kafka, Gateway, Normalizer, Temporal)"
	@echo "  make all-up                 - Start everything (streaming + analytics)"
	@echo ""
	@echo "Granular Startup (Choose What You Need):"
	@echo "  make all-up                 - Start ALL services (streaming + analytics)"
	@echo "  make all-down               - Stop ALL services"
	@echo "  make all-status             - Show status of all services"
	@echo "  make streaming-up           - Start streaming only (Kafka, Gateway, Normalizer, Temporal)"
	@echo "  make streaming-down         - Stop streaming services"
	@echo "  make streaming-status       - Show streaming service status"
	@echo "  make analytics-up           - Start batch analytics only (Dagster, Trino, Polaris, MinIO)"
	@echo "  make analytics-down         - Stop analytics services"
	@echo "  make analytics-status       - Show analytics service status"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make docker-up              - Start full stack (same as all-up)"
	@echo "  make docker-down            - Stop and remove all containers"
	@echo "  make docker-build           - Build/rebuild all images"
	@echo "  make docker-restart         - Restart all services"
	@echo "  make docker-status          - Show running containers"
	@echo "  make docker-logs            - View logs from all containers"
	@echo "  make docker-polaris-init    - Manually initialize Polaris catalog"
	@echo ""
	@echo "Payment Pipeline (Full Stack):"
	@echo "  make pipeline-up            - Start full pipeline (Kafka + Gateway + Normalizer + Temporal)"
	@echo "  make pipeline-down          - Stop full pipeline"
	@echo "  make pipeline-status        - Show all pipeline component status"
	@echo "  make pipeline-logs          - View all pipeline logs"
	@echo ""
	@echo "Payment Gateway (Webhook Receiver):"
	@echo "  make gateway-up             - Start payment gateway with Kafka"
	@echo "  make gateway-down           - Stop payment gateway"
	@echo "  make gateway-logs           - View payment gateway logs"
	@echo "  make gateway-simulator      - Start webhook simulator (continuous traffic)"
	@echo "  make simulator-stop         - Stop webhook simulator"
	@echo "  make simulator-logs         - View simulator logs"
	@echo "  make gateway-build          - Build payment gateway Docker image"
	@echo "  make gateway-test           - Run payment gateway unit tests"
	@echo "  make gateway-status         - Show payment gateway status"
	@echo "  make gateway-test-send      - Send a single test webhook"
	@echo ""
	@echo "Normalizer (Kafka Consumer):"
	@echo "  make normalizer-up          - Start normalizer with gateway"
	@echo "  make normalizer-down        - Stop normalizer"
	@echo "  make normalizer-logs        - View normalizer logs"
	@echo "  make normalizer-build       - Build normalizer Docker image"
	@echo "  make normalizer-status      - Show normalizer status"
	@echo "  make normalizer-counts      - Show message counts per topic"
	@echo ""
	@echo "Orchestrator (Temporal Workflows):"
	@echo "  make orchestrator-up        - Start orchestrator with all dependencies"
	@echo "  make orchestrator-down      - Stop orchestrator and Temporal"
	@echo "  make orchestrator-logs      - View orchestrator logs"
	@echo "  make orchestrator-build     - Build orchestrator Docker image"
	@echo "  make orchestrator-status    - Show orchestrator status"
	@echo "  make temporal-logs          - View Temporal server logs"
	@echo "  make inference-logs         - View inference service logs"
	@echo "  make inference-build        - Build inference service Docker image"
	@echo ""
	@echo "Apache Superset (BI Dashboard):"
	@echo "  make superset-up            - Start Superset with Trino connection"
	@echo "  make superset-down          - Stop Superset services"
	@echo "  make superset-logs          - View Superset logs"
	@echo "  make superset-status        - Show Superset service status"
	@echo ""
	@echo "Workflows:"
	@echo ""
	@echo "  Batch Analytics Only (No Streaming):"
	@echo "    1. make analytics-up                 # Start Dagster, Trino, Polaris, MinIO"
	@echo "    2. Open Dagster: http://localhost:3000"
	@echo "    3. Materialize payment_events asset  # Batch ingest to Iceberg"
	@echo "    4. Run DBT transformations           # Build star schema"
	@echo "    5. Query via Trino: http://localhost:8080"
	@echo ""
	@echo "  Full Pipeline (Streaming + Analytics):"
	@echo "    1. make all-up                       # Start everything"
	@echo "    2. make gateway-simulator            # Generate webhook traffic"
	@echo "    3. make all-status                   # Check all components"
	@echo "    4. make docker-logs                  # View all logs"
	@echo ""

##################################################
# GRANULAR STARTUP COMMANDS
##################################################

# Start ALL services (streaming + analytics)
all-up:
	@echo "=========================================="
	@echo "   Starting ALL Services"
	@echo "=========================================="
	@echo ""
	@echo "This starts the complete stack:"
	@echo "  - Streaming: Kafka, Gateway, Normalizer, Temporal, Orchestrator"
	@echo "  - Analytics: MinIO, Polaris, Trino, Dagster"
	@echo "  - Storage: Payments DB, Dagster DB"
	@echo ""
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator up -d --build
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
	@echo ""
	@echo "Next steps:"
	@echo "  make gateway-simulator   - Start webhook traffic"
	@echo "  make all-status          - Check all services"
	@echo "  make docker-logs         - View all logs"

# Stop ALL services
all-down:
	@echo "Stopping ALL services..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator --profile simulator down
	@echo "All services stopped"

# Start streaming pipeline only (Kafka + Gateway + Normalizer + Temporal + Orchestrator)
streaming-up:
	@echo "=========================================="
	@echo "   Starting Streaming Pipeline Only"
	@echo "=========================================="
	@echo ""
	@echo "This starts streaming components:"
	@echo "  - Kafka Broker (message queue)"
	@echo "  - Payment Gateway (webhook receiver)"
	@echo "  - Normalizer (validation)"
	@echo "  - Temporal (workflow orchestration)"
	@echo "  - Orchestrator (Temporal workflows)"
	@echo "  - Inference Service (ML endpoints)"
	@echo "  - Payments DB (event storage)"
	@echo ""
	@echo "Starting Kafka..."
	@cd $(DOCKER_DIR) && docker compose up -d kafka-broker
	@echo "Waiting for Kafka to be ready..."
	@sleep 5
	@echo ""
	@echo "Starting Gateway, Normalizer, and Orchestrator stack..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator up -d \
		payment-gateway normalizer \
		payments-db temporal-db temporal temporal-ui inference-service orchestrator
	@echo ""
	@echo "=========================================="
	@echo "   Streaming Pipeline Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URLs:"
	@echo "  Gateway API:        http://localhost:8000"
	@echo "  Temporal UI:        http://localhost:8088"
	@echo "  Inference Service:  http://localhost:8002"
	@echo "  Kafka Broker:       localhost:9092"
	@echo ""
	@echo "Database:"
	@echo "  Payments DB:        localhost:5433 (payments/payments)"
	@echo ""
	@echo "Next steps:"
	@echo "  make gateway-simulator   - Start webhook traffic"
	@echo "  make streaming-status    - Check streaming services"
	@echo "  make pipeline-logs       - View logs"

# Stop streaming pipeline only
streaming-down:
	@echo "Stopping streaming pipeline..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator --profile simulator stop \
		orchestrator inference-service temporal-ui temporal temporal-db payments-db \
		normalizer payment-gateway webhook-simulator kafka-broker 2>/dev/null || true
	@echo "Streaming pipeline stopped"

# Show streaming pipeline status
streaming-status:
	@echo "=========================================="
	@echo "   Streaming Pipeline Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q kafka-broker; then echo "  [OK] Kafka Broker"; else echo "  [--] Kafka Broker"; fi
	@if docker ps | grep -q payment-gateway; then echo "  [OK] Payment Gateway"; else echo "  [--] Payment Gateway"; fi
	@if docker ps | grep -q payment-normalizer; then echo "  [OK] Normalizer"; else echo "  [--] Normalizer"; fi
	@if docker ps | grep -q payments-db; then echo "  [OK] Payments DB"; else echo "  [--] Payments DB"; fi
	@if docker ps | grep -q "temporal$$"; then echo "  [OK] Temporal"; else echo "  [--] Temporal"; fi
	@if docker ps | grep -q temporal-ui; then echo "  [OK] Temporal UI"; else echo "  [--] Temporal UI"; fi
	@if docker ps | grep -q inference-service; then echo "  [OK] Inference Service"; else echo "  [--] Inference Service"; fi
	@if docker ps | grep -q payment-orchestrator; then echo "  [OK] Orchestrator"; else echo "  [--] Orchestrator"; fi
	@echo ""
	@echo "Commands:"
	@echo "  make streaming-up       - Start streaming pipeline"
	@echo "  make streaming-down     - Stop streaming pipeline"
	@echo "  make pipeline-logs      - View logs"

# Start batch analytics only (Payments DB + Dagster + MinIO + Polaris + Trino)
analytics-up:
	@echo "=========================================="
	@echo "   Starting Batch Analytics Stack"
	@echo "=========================================="
	@echo ""
	@echo "This starts batch analytics components:"
	@echo "  - Payments DB (source data - payment_events tables)"
	@echo "  - Dagster (orchestration for batch ingestion + DBT)"
	@echo "  - MinIO (S3 storage for Iceberg)"
	@echo "  - Polaris (Iceberg REST catalog)"
	@echo "  - Trino (SQL query engine)"
	@echo ""
	@echo "NOTE: Streaming services (Kafka, Gateway, Normalizer, Temporal)"
	@echo "      are NOT started. Use 'make all-up' for full stack."
	@echo ""
	@echo "Starting MinIO and Polaris..."
	@cd $(DOCKER_DIR) && docker compose up -d minio minio-client polaris polaris-init
	@echo "Waiting for storage services..."
	@sleep 5
	@echo ""
	@echo "Starting Payments DB and Dagster DB..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator up -d payments-db
	@cd $(DOCKER_DIR) && docker compose up -d postgres
	@echo "Waiting for databases..."
	@sleep 5
	@echo ""
	@echo "Starting Dagster..."
	@cd $(DOCKER_DIR) && docker compose up -d dagster-user-code dagster-webserver dagster-daemon
	@echo "Waiting for Dagster..."
	@sleep 5
	@echo ""
	@echo "Starting Trino..."
	@cd $(DOCKER_DIR) && docker compose up -d trino
	@echo ""
	@echo "=========================================="
	@echo "   Batch Analytics Stack Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URLs:"
	@echo "  Dagster:            http://localhost:3000"
	@echo "  Trino:              http://localhost:8080"
	@echo "  MinIO Console:      http://localhost:9001"
	@echo "  Polaris API:        http://localhost:8181"
	@echo ""
	@echo "Databases:"
	@echo "  Payments DB:        localhost:5433 (source data)"
	@echo "  Dagster DB:         postgres container (metadata)"
	@echo ""
	@echo "Workflow:"
	@echo "  1. Dagster reads from Payments DB (payment_events tables)"
	@echo "  2. Dagster writes to Iceberg via Polaris"
	@echo "  3. DBT transforms data in Iceberg"
	@echo "  4. Query results via Trino"
	@echo ""
	@echo "Next steps:"
	@echo "  make analytics-status    - Check analytics services"
	@echo "  make docker-logs         - View all logs"

# Stop batch analytics only
analytics-down:
	@echo "Stopping batch analytics stack..."
	@cd $(DOCKER_DIR) && docker compose stop trino dagster-daemon dagster-webserver dagster-user-code postgres
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator stop payments-db 2>/dev/null || true
	@cd $(DOCKER_DIR) && docker compose stop polaris-init polaris minio-client minio
	@echo "Batch analytics stack stopped"

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
	@echo ""
	@echo "Access URLs:"
	@echo "  Dagster:            http://localhost:3000"
	@echo "  Trino:              http://localhost:8080"
	@echo "  MinIO Console:      http://localhost:9001"
	@echo "  Polaris API:        http://localhost:8181"
	@echo ""
	@echo "Commands:"
	@echo "  make analytics-up       - Start analytics stack"
	@echo "  make analytics-down     - Stop analytics stack"
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
	@cd $(DOCKER_DIR) && docker compose ps
	@echo ""
	@echo "Service URLs & Ports:"
	@echo "---------------------"
	@echo "  Kafka Broker:      localhost:9092"
	@echo "  Polaris API:       http://localhost:8181"
	@echo "  MinIO Console:     http://localhost:9001 (admin/password)"
	@echo "  MinIO S3 API:      http://localhost:9000"
	@echo "  Trino:             http://localhost:8080"
	@echo "  Dagster:           http://localhost:3000"
	@echo "  Gateway API:       http://localhost:8000"
	@echo "  Temporal UI:       http://localhost:8088"
	@echo "  Inference Service: http://localhost:8002"
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
	@echo "  - Normalizer (validation & transformation)"
	@echo "  - Temporal (workflow orchestration)"
	@echo "  - Inference Service (ML mock endpoints)"
	@echo "  - Orchestrator (Temporal workflows)"
	@echo ""
	@echo "Starting Kafka..."
	@cd $(DOCKER_DIR) && docker compose up -d kafka-broker
	@echo "Waiting for Kafka to be ready..."
	@sleep 5
	@echo ""
	@echo "Starting Gateway..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway up -d payment-gateway
	@sleep 3
	@echo ""
	@echo "Starting Normalizer..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer up -d normalizer
	@sleep 2
	@echo ""
	@echo "Starting Temporal..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator up -d temporal-db temporal temporal-ui
	@echo "Waiting for Temporal to be ready..."
	@sleep 10
	@echo ""
	@echo "Starting Inference Service and Orchestrator..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator up -d inference-service orchestrator
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
	@echo "  4. View counts:      make normalizer-counts"

# Stop full payment pipeline
pipeline-down:
	@echo "Stopping Payment Pipeline..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator --profile simulator stop \
		orchestrator inference-service temporal-ui temporal temporal-db \
		normalizer payment-gateway webhook-simulator kafka-broker 2>/dev/null || true
	@echo "Payment Pipeline stopped"

# Show all pipeline component status
pipeline-status: gateway-status normalizer-status orchestrator-status

# View all pipeline logs
pipeline-logs:
	@echo "Viewing Pipeline logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator logs -f kafka-broker payment-gateway normalizer orchestrator inference-service temporal

##################################################
# PAYMENT GATEWAY COMMANDS
##################################################

# Start payment gateway with Kafka
gateway-up:
	@echo "Starting Payment Gateway with Kafka..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway up -d kafka-broker payment-gateway
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
	@echo "Stopping Payment Gateway..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile simulator stop payment-gateway webhook-simulator
	@echo "Payment Gateway stopped"

# View payment gateway logs
gateway-logs:
	@echo "Viewing Payment Gateway logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose logs -f payment-gateway

# Start webhook simulator
gateway-simulator:
	@echo "Starting Webhook Simulator..."
	@echo ""
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile simulator up -d webhook-simulator
	@echo ""
	@echo "Webhook Simulator started! Generating webhooks at 2/sec for 5 minutes"
	@echo ""
	@echo "Commands:"
	@echo "  make simulator-stop   - Stop simulator"
	@echo "  make simulator-logs   - View simulator logs"

# Stop webhook simulator
simulator-stop:
	@echo "Stopping Webhook Simulator..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile simulator stop webhook-simulator
	@echo "Webhook Simulator stopped"

# View webhook simulator logs
simulator-logs:
	@echo "Viewing Simulator logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile simulator logs -f webhook-simulator

# Build payment gateway Docker image
gateway-build:
	@echo "Building Payment Gateway Docker image..."
	@cd $(PAYMENT_PIPELINE_DIR) && docker build -t payment-gateway:latest .
	@echo "Payment Gateway image built: payment-gateway:latest"

# Run payment gateway unit tests
gateway-test:
	@echo "Running Payment Gateway unit tests..."
	@cd $(PAYMENT_PIPELINE_DIR) && pip install -e ".[dev]" -q && pytest tests/ -v
	@echo "Tests completed"

# Send a single test webhook
gateway-test-send:
	@echo "Sending test webhook to gateway..."
	@if ! docker ps | grep -q payment-gateway; then \
		echo "Error: Payment Gateway not running"; \
		echo "   Start it first: make gateway-up"; \
		exit 1; \
	fi
	@cd $(PAYMENT_PIPELINE_DIR) && pip install -e . -q && \
		python -m simulator.main send --type payment_intent.succeeded
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
	@if docker ps | grep -q payment-gateway; then \
		echo "  [OK] Payment Gateway: running"; \
		docker ps --filter "name=payment-gateway" --format "    {{.Status}}  {{.Ports}}"; \
	else \
		echo "  [--] Payment Gateway: not running"; \
	fi
	@if docker ps | grep -q webhook-simulator; then \
		echo "  [OK] Webhook Simulator: running"; \
	else \
		echo "  [--] Webhook Simulator: not running"; \
	fi
	@echo ""
	@echo "Health Check:"
	@echo "-------------"
	@if docker ps | grep -q payment-gateway; then \
		curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  Gateway not responding"; \
	else \
		echo "  Gateway not running"; \
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
# NORMALIZER COMMANDS
##################################################

# Build normalizer Docker image
normalizer-build:
	@echo "Building Normalizer Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer build normalizer
	@echo "Normalizer image built"

# Start normalizer with gateway
normalizer-up: gateway-up
	@echo ""
	@echo "Starting Normalizer..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer up -d normalizer
	@echo ""
	@echo "Normalizer started!"
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
	@echo "  2. View logs:        make normalizer-logs"
	@echo "  3. Check status:     make normalizer-status"

# Stop normalizer
normalizer-down:
	@echo "Stopping Normalizer..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer stop normalizer
	@echo "Normalizer stopped"

# View normalizer logs
normalizer-logs:
	@echo "Viewing Normalizer logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer logs -f normalizer

# Show normalizer status
normalizer-status:
	@echo "=========================================="
	@echo "   Normalizer Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q payment-normalizer; then \
		echo "  [OK] Normalizer: running"; \
	else \
		echo "  [--] Normalizer: not running"; \
	fi
	@if docker ps | grep -q payment-gateway; then \
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
	@echo "  make normalizer-up      - Start normalizer with gateway"
	@echo "  make normalizer-logs    - View normalizer logs"
	@echo "  make normalizer-counts  - Show message counts"
	@echo "  make normalizer-down    - Stop normalizer"

# Check normalized message counts
normalizer-counts:
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
# ORCHESTRATOR COMMANDS
##################################################

# Build orchestrator Docker image
orchestrator-build:
	@echo "Building Orchestrator Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator build orchestrator
	@echo "Orchestrator image built"

# Build inference service Docker image
inference-build:
	@echo "Building Inference Service Docker image..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator build inference-service
	@echo "Inference Service image built"

# Start orchestrator with all dependencies
orchestrator-up: normalizer-up
	@echo ""
	@echo "Starting Temporal and Orchestrator..."
	@cd $(DOCKER_DIR) && docker compose --profile gateway --profile normalizer --profile orchestrator up -d temporal-db temporal temporal-ui inference-service orchestrator
	@echo ""
	@echo "Orchestrator started!"
	@echo ""
	@echo "Access Points:"
	@echo "  - Temporal UI:        http://localhost:8088"
	@echo "  - Inference Service:  http://localhost:8002"
	@echo ""
	@echo "Commands:"
	@echo "  make orchestrator-logs    - View orchestrator logs"
	@echo "  make orchestrator-status  - Show orchestrator status"
	@echo "  make orchestrator-down    - Stop orchestrator"

# Stop orchestrator
orchestrator-down:
	@echo "Stopping Orchestrator and Temporal..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator stop orchestrator inference-service temporal-ui temporal temporal-db
	@echo "Orchestrator stopped"

# View orchestrator logs
orchestrator-logs:
	@echo "Viewing Orchestrator logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator logs -f orchestrator

# View temporal logs
temporal-logs:
	@echo "Viewing Temporal logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator logs -f temporal

# View inference service logs
inference-logs:
	@echo "Viewing Inference Service logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose --profile orchestrator logs -f inference-service

# Show orchestrator status
orchestrator-status:
	@echo "=========================================="
	@echo "   Orchestrator Status"
	@echo "=========================================="
	@echo ""
	@echo "Container Status:"
	@echo "-----------------"
	@if docker ps | grep -q payment-orchestrator; then \
		echo "  [OK] Orchestrator: running"; \
	else \
		echo "  [--] Orchestrator: not running"; \
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
	@echo "  make orchestrator-up      - Start orchestrator with dependencies"
	@echo "  make orchestrator-logs    - View orchestrator logs"
	@echo "  make temporal-logs        - View temporal logs"
	@echo "  make inference-logs       - View inference service logs"
	@echo "  make orchestrator-down    - Stop orchestrator"

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
	@echo "Starting Superset stack..."
	@cd $(DOCKER_DIR) && docker compose --profile superset up -d
	@echo ""
	@echo "Waiting for initialization (this may take 30-60 seconds)..."
	@sleep 30
	@echo ""
	@echo "=========================================="
	@echo "   Apache Superset Started!"
	@echo "=========================================="
	@echo ""
	@echo "Access URL:"
	@echo "  Superset:  http://localhost:8088"
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
	@echo "  Superset:  http://localhost:8088"
	@echo ""
	@echo "Commands:"
	@echo "  make superset-up      - Start Superset"
	@echo "  make superset-logs    - View logs"
	@echo "  make superset-down    - Stop Superset"

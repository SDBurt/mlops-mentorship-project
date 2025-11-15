# Kubernetes Lakehouse Platform - Makefile
# Simplified deployment automation for lakehouse namespace architecture

.PHONY: help check setup validate-secrets generate-user-secrets configure-trino-polaris build-dagster-image deploy-dagster-code install deploy destroy nuke clean-old port-forward port-forward-start port-forward-stop port-forward-status restart-dagster restart-trino restart-polaris restart-all status polaris-status polaris-logs init-polaris setup-polaris-rbac polaris-test docker-up docker-down docker-build docker-restart docker-status docker-logs jr-charges jr-refunds jr-disputes jr-subscriptions jr-all jr-create-topics jr-stop jr-help

# Variables
NAMESPACE := lakehouse
HELM_TIMEOUT := 10m
MINIO_VALUES := infrastructure/kubernetes/minio/values.yaml
DAGSTER_VALUES := infrastructure/kubernetes/dagster/values.yaml
TRINO_VALUES := infrastructure/kubernetes/trino/values.yaml
TRINO_VALUES_MINIMAL := infrastructure/kubernetes/trino/values-minimal.yaml
POLARIS_VALUES := infrastructure/kubernetes/polaris/values.yaml
POLARIS_SECRETS := infrastructure/kubernetes/polaris/polaris-secrets.yaml
POLARIS_REPO := infrastructure/helm/polaris

# Docker Compose Variables
DOCKER_DIR := infrastructure/docker
DOCKER_COMPOSE := docker compose -f $(DOCKER_DIR)/docker-compose.yml
JR_DIR := $(DOCKER_DIR)/jr
JR_KAFKA_CONFIG := $(JR_DIR)/kafka.client.properties

# Required secret files (checked before deployment)
MINIO_SECRETS := infrastructure/kubernetes/minio/minio-secrets.yaml
DAGSTER_USER_SECRETS := infrastructure/kubernetes/dagster/user-code-secrets.yaml
TRINO_SECRETS := infrastructure/kubernetes/trino/secrets.yaml

# Default target - show help
help:
	@echo "Kubernetes Lakehouse Platform - Available Commands"
	@echo ""
	@echo "Quick Start (First Time Setup):"
	@echo "  1. Configure secrets (see docs/guides/GETTING-STARTED.md)"
	@echo "  2. make setup                 - Complete setup: check, configure repos, deploy"
	@echo "  3. make init-polaris          - Initialize Polaris catalog with RBAC"
	@echo "  4. make configure-trino-polaris  - Connect Trino to Polaris"
	@echo ""
	@echo "Complete Guide: docs/guides/GETTING-STARTED.md (step-by-step walkthrough)"
	@echo ""
	@echo "Prerequisites & Setup:"
	@echo "  make check                  - Verify kubectl and helm are installed"
	@echo "  make validate-secrets       - Validate required secret files exist"
	@echo "  make generate-user-secrets  - Auto-generate user-code-secrets.yaml from sources"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy                 - Deploy all services to lakehouse namespace (full pipeline)"
	@echo "  make install                - Install services only (called by deploy)"
	@echo ""
	@echo "Management:"
	@echo "  make destroy                - Tear down lakehouse cluster"
	@echo "  make nuke                   - Complete reset: destroy everything and clean local files"
	@echo "  make clean-old              - One-time cleanup of old separate namespaces (migration only)"
	@echo "  make status                 - Show cluster status"
	@echo ""
	@echo "Polaris Operations:"
	@echo "  make init-polaris              - Initialize Polaris catalog with RBAC (run after deploy)"
	@echo "  make configure-trino-polaris   - Configure Trino-Polaris integration (run after init-polaris)"
	@echo "  make setup-polaris-rbac        - Setup RBAC and namespaces (catalog/principal must exist)"
	@echo "  make polaris-test              - Test Polaris catalog connectivity"
	@echo "  make polaris-status            - Show Polaris pod status and logs summary"
	@echo "  make polaris-logs              - Tail Polaris logs (live)"
	@echo ""
	@echo "Port-forwarding:"
	@echo "  make port-forward-start     - Start all port-forwards in background"
	@echo "  make port-forward-stop      - Stop all running port-forwards"
	@echo "  make port-forward-status    - Show active port-forwards"
	@echo "  make port-forward           - Alias for port-forward-start"
	@echo ""
	@echo "Service Restarts:"
	@echo "  make restart-dagster        - Restart Dagster deployments"
	@echo "  make restart-trino          - Restart Trino deployments"
	@echo "  make restart-polaris        - Restart Polaris deployment"
	@echo "  make restart-all            - Restart all service deployments"
	@echo ""
	@echo "Dagster User Code:"
	@echo "  make build-dagster-image    - Build orchestration-dagster Docker image"
	@echo "  make deploy-dagster-code    - Deploy user code (ConfigMap + scale deployment)"
	@echo ""
	@echo "Docker Compose (Local Streaming Stack):"
	@echo "  make docker-up              - Start all services (Kafka, Flink, etc.)"
	@echo "  make docker-down            - Stop and remove all containers"
	@echo "  make docker-build           - Build/rebuild Flink image"
	@echo "  make docker-restart         - Restart all services"
	@echo "  make docker-status          - Show running containers"
	@echo "  make docker-logs            - View logs from all containers"
	@echo ""
	@echo "JR Data Generation (Stripe-like Payment Events):"
	@echo "  make jr-create-topics       - Create Kafka topics (run once after docker-up)"
	@echo "  make jr-charges             - Generate charge events (requires JR installed)"
	@echo "  make jr-refunds             - Generate refund events"
	@echo "  make jr-disputes            - Generate dispute events"
	@echo "  make jr-subscriptions       - Generate subscription events"
	@echo "  make jr-all                 - Generate all event types simultaneously"
	@echo "  make jr-stop                - Stop all running JR processes"
	@echo "  make jr-help                - Show JR installation and usage help"
	@echo ""
	@echo "Complete Workflow:"
	@echo "  1. make setup                       # One command: setup repos and deploy everything"
	@echo "  2. make build-dagster-image         # Build user code Docker image"
	@echo "  3. make deploy-dagster-code         # Deploy user code to Dagster"
	@echo "  4. make init-polaris                # Initialize Polaris catalog"
	@echo "  5. make configure-trino-polaris     # Connect Trino to Polaris"
	@echo "  6. make port-forward-start          # Access services locally"
	@echo ""
	@echo "Streaming Workflow (Docker Compose):"
	@echo "  1. make docker-up                   # Start Kafka + Flink stack"
	@echo "  2. make jr-create-topics            # Create Kafka topics"
	@echo "  3. make jr-charges                  # Generate payment events"
	@echo "  4. docker compose attach flink-sql-client  # Configure Flink pipeline"
	@echo ""

# Check prerequisites
check:
	@echo "Checking prerequisites..."
	@command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl not found"; exit 1; }
	@command -v helm >/dev/null 2>&1 || { echo "Error: helm not found"; exit 1; }
	@kubectl cluster-info >/dev/null 2>&1 || { echo "Error: kubectl not connected to cluster"; exit 1; }
	@echo "✓ kubectl: $$(kubectl version --client --short 2>/dev/null | head -n1)"
	@echo "✓ helm: $$(helm version --short)"
	@echo "✓ cluster: $$(kubectl config current-context)"
	@echo "Prerequisites check passed!"

# Setup Helm repositories, clone dependencies, and deploy platform
setup:
	@echo "=========================================="
	@echo "   Lakehouse Platform Setup"
	@echo "=========================================="
	@echo ""
	@echo "This will:"
	@echo "  1. Verify prerequisites (kubectl, helm, cluster)"
	@echo "  2. Configure Helm repositories"
	@echo "  3. Clone Apache Polaris repository"
	@echo "  4. Deploy the entire lakehouse platform"
	@echo ""
	@echo "Step 1/4: Checking prerequisites..."
	@$(MAKE) check
	@echo ""
	@echo "Step 2/4: Setting up Helm repositories and dependencies..."
	@helm repo add dagster https://dagster-io.github.io/helm 2>/dev/null || true
	@helm repo add trino https://trinodb.github.io/charts 2>/dev/null || true
	@helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
	@helm repo update
	@echo "✓ Helm repositories configured"
	@echo ""
	@echo "Step 3/4: Cloning Apache Polaris repository (if needed)..."
	@if [ ! -d "$(POLARIS_REPO)" ]; then \
		git clone https://github.com/apache/polaris.git $(POLARIS_REPO); \
		echo "✓ Polaris repository cloned"; \
	else \
		echo "✓ Polaris repository already exists"; \
	fi
	@echo ""
	@echo "Step 4/4: Deploying platform..."
	@$(MAKE) deploy
	@echo ""
	@echo "=========================================="
	@echo "   Setup Complete!"
	@echo "=========================================="
	@echo ""
	@echo "Platform is deployed and running!"
	@echo ""
	@echo "Next Steps:"
	@echo "  1. Initialize Polaris catalog:"
	@echo "     make init-polaris"
	@echo ""
	@echo "  2. Connect Trino to Polaris:"
	@echo "     make configure-trino-polaris"
	@echo ""
	@echo "  3. (Optional) Deploy Dagster user code:"
	@echo "     make deploy-dagster-code"
	@echo ""
	@echo "  4. Access services locally:"
	@echo "     make port-forward-start"
	@echo ""
	@echo "  5. Check platform status:"
	@echo "     make status"
	@echo ""

# Validate that all required secret files exist before deployment
validate-secrets:
	@echo "Validating required secret files..."
	@MISSING=0; \
	if [ ! -f "$(MINIO_SECRETS)" ]; then \
		echo "❌ Missing: $(MINIO_SECRETS)"; \
		echo "   → Copy from: infrastructure/kubernetes/minio/minio-secrets.yaml.example"; \
		MISSING=1; \
	else \
		echo "✓ MinIO secrets found"; \
	fi; \
	if [ ! -f "$(DAGSTER_USER_SECRETS)" ]; then \
		echo "❌ Missing: $(DAGSTER_USER_SECRETS)"; \
		echo "   → Copy from: infrastructure/kubernetes/dagster/user-code-secrets.yaml.example"; \
		MISSING=1; \
	else \
		echo "✓ Dagster user-code secrets found"; \
		if grep -q "REPLACE_WITH" "$(DAGSTER_USER_SECRETS)"; then \
			echo "⚠️  Warning: $(DAGSTER_USER_SECRETS) contains REPLACE_WITH placeholders"; \
			echo "   → Update with actual credentials before deployment"; \
		fi; \
	fi; \
	if [ ! -f "$(TRINO_SECRETS)" ]; then \
		echo "❌ Missing: $(TRINO_SECRETS)"; \
		echo "   → Copy from: infrastructure/kubernetes/trino/secrets.yaml.example"; \
		MISSING=1; \
	else \
		echo "✓ Trino secrets found"; \
	fi; \
	if [ ! -f "$(POLARIS_SECRETS)" ]; then \
		echo "❌ Missing: $(POLARIS_SECRETS)"; \
		echo "   → Copy from: infrastructure/kubernetes/polaris/polaris-secrets.yaml.example"; \
		MISSING=1; \
	else \
		echo "✓ Polaris secrets found"; \
	fi; \
	if [ $$MISSING -eq 1 ]; then \
		echo ""; \
		echo "========================================"; \
		echo "Secret files are missing!"; \
		echo "========================================"; \
		echo ""; \
		echo "Please create missing secret files from .example templates:"; \
		echo "  1. Copy .example files: cp *-secrets.yaml.example *-secrets.yaml"; \
		echo "  2. Edit and replace placeholders with actual values"; \
		echo "  3. Run 'make validate-secrets' again"; \
		echo ""; \
		exit 1; \
	fi; \
	echo "✓ All required secrets validated"

# Generate user-code-secrets.yaml from credential sources
generate-user-secrets:
	@echo "Generating user-code-secrets.yaml from sources..."
	@if [ ! -f "$(MINIO_SECRETS)" ]; then \
		echo "❌ Error: minio-secrets.yaml not found"; \
		exit 1; \
	fi
	@if [ ! -f "infrastructure/kubernetes/polaris/.credentials/dagster_user.txt" ]; then \
		echo "❌ Error: Polaris credentials not found"; \
		echo "   Run 'make init-polaris' first to generate credentials"; \
		exit 1; \
	fi
	@echo "Reading MinIO credentials from minio-secrets.yaml..."
	@MINIO_ACCESS_KEY=$$(grep 'access-key-id:' $(MINIO_SECRETS) | awk -F'"' '{print $$2}'); \
	MINIO_SECRET_KEY=$$(grep 'secret-access-key:' $(MINIO_SECRETS) | awk -F'"' '{print $$2}'); \
	echo "Reading Polaris credentials from .credentials/dagster_user.txt..."; \
	. infrastructure/kubernetes/polaris/.credentials/dagster_user.txt; \
	echo "Updating user-code-secrets.yaml..."; \
	if [ -f "$(DAGSTER_USER_SECRETS)" ]; then \
		REDDIT_ID=$$(grep 'REDDIT_CLIENT_ID:' $(DAGSTER_USER_SECRETS) | awk -F'"' '{print $$2}'); \
		REDDIT_SECRET=$$(grep 'REDDIT_CLIENT_SECRET:' $(DAGSTER_USER_SECRETS) | awk -F'"' '{print $$2}'); \
		REDDIT_AGENT=$$(grep 'REDDIT_USER_AGENT:' $(DAGSTER_USER_SECRETS) | awk -F'"' '{print $$2}'); \
	else \
		REDDIT_ID="REPLACE_WITH_REDDIT_CLIENT_ID"; \
		REDDIT_SECRET="REPLACE_WITH_REDDIT_CLIENT_SECRET"; \
		REDDIT_AGENT="REPLACE_WITH_REDDIT_USER_AGENT"; \
	fi; \
	sed -e "s|POLARIS_CLIENT_ID:.*|POLARIS_CLIENT_ID: \"$$POLARIS_CLIENT_ID\"|" \
	    -e "s|POLARIS_CLIENT_SECRET:.*|POLARIS_CLIENT_SECRET: \"$$POLARIS_CLIENT_SECRET\"|" \
	    -e "s|PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID:.*|PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID: \"$$MINIO_ACCESS_KEY\"|" \
	    -e "s|PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY:.*|PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY: \"$$MINIO_SECRET_KEY\"|" \
	    -e "s|AWS_ACCESS_KEY_ID:.*|AWS_ACCESS_KEY_ID: \"$$MINIO_ACCESS_KEY\"|" \
	    -e "s|AWS_SECRET_ACCESS_KEY:.*|AWS_SECRET_ACCESS_KEY: \"$$MINIO_SECRET_KEY\"|" \
	    -e "s|REDDIT_CLIENT_ID:.*|REDDIT_CLIENT_ID: \"$$REDDIT_ID\"|" \
	    -e "s|REDDIT_CLIENT_SECRET:.*|REDDIT_CLIENT_SECRET: \"$$REDDIT_SECRET\"|" \
	    -e "s|REDDIT_USER_AGENT:.*|REDDIT_USER_AGENT: \"$$REDDIT_AGENT\"|" \
	    infrastructure/kubernetes/dagster/user-code-secrets.yaml.example > $(DAGSTER_USER_SECRETS)
	@echo "✓ user-code-secrets.yaml generated successfully"
	@echo ""
	@echo "Credentials populated from:"
	@echo "  - MinIO: minio-secrets.yaml"
	@echo "  - Polaris: .credentials/dagster_user.txt"
	@echo "  - Reddit: preserved from existing file (or needs manual update)"

# Configure Trino to connect to Polaris catalog (run after init-polaris)
configure-trino-polaris:
	@echo "Configuring Trino-Polaris integration..."
	@if [ ! -f "infrastructure/kubernetes/polaris/.credentials/dagster_user.txt" ]; then \
		echo "❌ Error: Polaris credentials not found"; \
		echo "   Run 'make init-polaris' first to generate credentials"; \
		exit 1; \
	fi
	@echo "Reading Polaris credentials..."
	@POLARIS_CRED=$$( . infrastructure/kubernetes/polaris/.credentials/dagster_user.txt && echo "$$POLARIS_CLIENT_ID:$$POLARIS_CLIENT_SECRET"); \
	echo "Adding POLARIS_OAUTH_CREDENTIAL to trino-env-secrets..."; \
	kubectl patch secret trino-env-secrets -n $(NAMESPACE) --type merge -p "{\"stringData\":{\"POLARIS_OAUTH_CREDENTIAL\":\"$$POLARIS_CRED\"}}"; \
	echo "✓ Polaris credentials added to trino-env-secrets"
	@echo ""
	@echo "Updating Trino with full catalog configuration..."
	@helm upgrade trino trino/trino \
		-f $(TRINO_VALUES) \
		-n $(NAMESPACE)
	@echo "✓ Trino upgraded with lakehouse catalog"
	@echo ""
	@echo "Restarting Trino to apply changes..."
	@kubectl rollout restart deployment -n $(NAMESPACE) -l app.kubernetes.io/name=trino
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=trino,app.kubernetes.io/component=coordinator -n $(NAMESPACE) --timeout=120s 2>/dev/null || true
	@echo "✓ Trino configured with Polaris catalog"
	@echo ""
	@echo "Lakehouse catalog is now available in Trino!"
	@echo "Test with: SHOW SCHEMAS FROM lakehouse;"

# Build Dagster user code Docker image
build-dagster-image:
	@echo "Building Dagster user code image..."
	@cd orchestration-dagster && docker build -t orchestration-dagster:latest .
	@echo "✓ Dagster image built: orchestration-dagster:latest"

# Deploy full lakehouse platform (orchestration)
deploy:
	@echo "=========================================="
	@echo "   Deploying Lakehouse Platform"
	@echo "=========================================="
	@echo ""
	@$(MAKE) validate-secrets
	@echo ""
	@$(MAKE) install
	@echo ""
	@echo "=========================================="
	@echo "   Deployment Complete!"
	@echo "=========================================="
	@echo ""
	@echo "MinIO is ready with default bucket 'lakehouse'"
	@echo "Polaris REST catalog is available for unified Iceberg table management"
	@echo ""
	@echo "Next steps:"
	@echo "  1. make build-dagster-image   # Build user code Docker image"
	@echo "  2. make deploy-dagster-code   # Deploy user code to Dagster"
	@echo "  3. make port-forward-start    # Access services locally"
	@echo "  4. make status                # Check deployment status"

# Install all services to lakehouse namespace
install:
	@echo "Step 1/7: Creating lakehouse namespace..."
	@kubectl apply -f infrastructure/kubernetes/namespace.yaml
	@echo ""
	@echo "Step 2/7: Applying secrets..."
	@kubectl apply -f infrastructure/kubernetes/minio/minio-secrets.yaml 2>/dev/null || echo "  MinIO secrets not found (optional)"
	# Note: dagster-postgresql-secret is managed by Helm (generatePostgresqlPasswordSecret: true)
	@kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml 2>/dev/null || echo "  Dagster user-code secrets not found (optional)"
	@kubectl apply -f infrastructure/kubernetes/trino/secrets.yaml 2>/dev/null || echo "  Trino secrets not found (optional)"
	@kubectl apply -f $(POLARIS_SECRETS) 2>/dev/null || echo "  Polaris secrets not found (optional)"
	@echo "✓ Secrets applied"
	@echo ""
	@echo "Step 3/7: Deploying MinIO (S3 storage)..."
	@kubectl apply -f infrastructure/kubernetes/minio/minio-standalone.yaml
	@echo "Waiting for MinIO to be ready..."
	@kubectl wait --for=condition=ready pod -l app=minio -n $(NAMESPACE) --timeout=120s
	@echo "✓ MinIO deployed"
	@echo ""
	@echo "Step 4/7: Deploying Dagster (orchestration)..."
	@helm upgrade --install dagster dagster/dagster \
		-f $(DAGSTER_VALUES) \
		-n $(NAMESPACE)
	@echo "Waiting for Dagster core components..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=dagster,app.kubernetes.io/component=dagster-webserver -n $(NAMESPACE) --timeout=120s 2>/dev/null || true
	@kubectl scale deployment -n $(NAMESPACE) dagster-dagster-user-deployments-orchestration-dagster --replicas=0 2>/dev/null || true
	@echo "✓ Dagster deployed"
	@echo ""
	@echo "Step 5/6: Deploying Trino (query engine - minimal, no lakehouse catalog)..."
	@helm upgrade --install trino trino/trino \
		-f $(TRINO_VALUES_MINIMAL) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)
	@echo "✓ Trino deployed (without lakehouse catalog)"
	@echo "   Run 'make configure-trino-polaris' after 'make init-polaris' to add lakehouse catalog"
	@echo ""
	@echo "Step 6/6: Deploying Polaris (Apache Iceberg REST catalog with in-memory persistence)..."
	@helm upgrade --install polaris $(POLARIS_REPO)/helm/polaris \
		-f $(POLARIS_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)
	@echo "✓ Polaris deployed"


# Teardown lakehouse cluster
destroy:
	@echo "Tearing down lakehouse cluster..."
	@echo ""
	@echo "This will destroy all services and data in lakehouse namespace."
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@echo ""
	@echo "Stopping port-forwards..."
	@$(MAKE) port-forward-stop 2>/dev/null || true
	@echo ""
	@echo "Uninstalling Polaris (if deployed)..."
	@helm uninstall polaris -n $(NAMESPACE) 2>/dev/null || echo "Polaris not found"
	@echo "Uninstalling Trino..."
	@helm uninstall trino -n $(NAMESPACE) 2>/dev/null || echo "Trino not found"
	@echo "Uninstalling Dagster..."
	@helm uninstall dagster -n $(NAMESPACE) 2>/dev/null || echo "Dagster not found"
	@echo "Uninstalling MinIO..."
	@kubectl delete -f infrastructure/kubernetes/minio/minio-standalone.yaml 2>/dev/null || echo "MinIO not found"
	@echo ""
	@echo "Deleting lakehouse namespace..."
	@kubectl delete namespace $(NAMESPACE) --wait=true 2>/dev/null || echo "Namespace $(NAMESPACE) not found"
	@echo ""
	@echo "Teardown complete!"

# Complete reset: destroy everything and clean local files
nuke:
	@echo "=========================================="
	@echo "   NUKE: Complete Platform Reset"
	@echo "=========================================="
	@echo ""
	@echo "⚠️  WARNING: This will:"
	@echo "  - Destroy ALL services and data in lakehouse namespace"
	@echo "  - Stop all port-forwards"
	@echo "  - Delete local credential files (.credentials/)"
	@echo "  - Remove all Helm releases"
	@echo "  - Delete the entire namespace"
	@echo ""
	@echo "This is IRREVERSIBLE. All data will be lost!"
	@echo ""
	@echo "Press Ctrl+C within 10 seconds to cancel..."
	@sleep 10
	@echo ""
	@echo "Step 1/5: Stopping all port-forwards..."
	@$(MAKE) port-forward-stop 2>/dev/null || true
	@echo "✓ Port-forwards stopped"
	@echo ""
	@echo "Step 2/5: Uninstalling all Helm releases..."
	@helm uninstall polaris -n $(NAMESPACE) 2>/dev/null || echo "  Polaris: not found"
	@helm uninstall trino -n $(NAMESPACE) 2>/dev/null || echo "  Trino: not found"
	@helm uninstall dagster -n $(NAMESPACE) 2>/dev/null || echo "  Dagster: not found"
	@echo "✓ Helm releases uninstalled"
	@echo ""
	@echo "Step 3/5: Deleting all resources..."
	@kubectl delete -f infrastructure/kubernetes/minio/minio-standalone.yaml 2>/dev/null || echo "  MinIO: not found"
	@kubectl delete job -n $(NAMESPACE) --all 2>/dev/null || true
	@kubectl delete pvc -n $(NAMESPACE) --all 2>/dev/null || true
	@echo "✓ Resources deleted"
	@echo ""
	@echo "Step 4/5: Deleting namespace..."
	@kubectl delete namespace $(NAMESPACE) --wait=true --timeout=120s 2>/dev/null || echo "  Namespace $(NAMESPACE): not found"
	@echo "✓ Namespace deleted"
	@echo ""
	@echo "Step 5/5: Cleaning local credential files..."
	@rm -rf infrastructure/kubernetes/polaris/.credentials 2>/dev/null || true
	@echo "✓ Local credentials cleaned"
	@echo ""
	@echo "=========================================="
	@echo "   NUKE Complete!"
	@echo "=========================================="
	@echo ""
	@echo "Everything has been reset. You can now run:"
	@echo "  make deploy"
	@echo ""
	@echo "to start fresh!"

# One-time cleanup of old separate namespaces (for migration from old architecture)
clean-old:
	@echo "Cleaning up old separate namespaces..."
	@echo ""
	@echo "This is a one-time migration step to remove the old namespace architecture."
	@echo "Only run this if you have old installations in separate namespaces."
	@echo ""
	@echo "Uninstalling from old namespaces..."
	@helm uninstall dagster -n dagster 2>/dev/null || echo "dagster namespace not found"
	@helm uninstall trino -n trino 2>/dev/null || echo "trino namespace not found"
	@helm uninstall minio -n minio 2>/dev/null || echo "minio namespace not found (old separate namespace cleanup)"
	@echo ""
	@echo "Deleting old namespaces..."
	@kubectl delete namespace dagster --wait=false 2>/dev/null || echo "dagster namespace already deleted"
	@kubectl delete namespace trino --wait=false 2>/dev/null || echo "trino namespace already deleted"
	@kubectl delete namespace minio --wait=false 2>/dev/null || echo "minio namespace already deleted (old separate namespace cleanup)"
	@echo ""
	@echo "Old namespace cleanup complete!"

# Port-forward all service UIs (starts in background)
port-forward-start:
	@echo "Starting port-forwards in background..."
	@echo ""
	@kubectl port-forward -n $(NAMESPACE) svc/dagster-dagster-webserver 3001:80 > /dev/null 2>&1 &
	@kubectl port-forward -n $(NAMESPACE) svc/trino 8080:8080 > /dev/null 2>&1 &
	@kubectl port-forward -n $(NAMESPACE) svc/minio 9000:9000 > /dev/null 2>&1 &
	@kubectl port-forward -n $(NAMESPACE) svc/minio 9001:9001 > /dev/null 2>&1 &
	@if kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		kubectl port-forward -n $(NAMESPACE) svc/polaris 8181:8181 > /dev/null 2>&1 & \
	fi
	@sleep 1
	@echo "Port-forwards started!"
	@echo ""
	@echo "Access URLs:"
	@echo "  Dagster:       http://localhost:3001 (Orchestration UI)"
	@echo "  Trino:         http://localhost:8080 (Query Engine)"
	@echo "  MinIO API:     http://localhost:9000 (S3 API)"
	@echo "  MinIO Console: http://localhost:9001 (Storage Web UI)"
	@if kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		echo "  Polaris:       http://localhost:8181 (REST Catalog API)"; \
	fi
	@echo ""
	@echo "Run 'make port-forward-status' to check status"
	@echo "Run 'make port-forward-stop' to stop all port-forwards"

# Stop all port-forwards (finds processes by name)
port-forward-stop:
	@echo "Stopping all port-forwards..."
	@ps aux | grep "[k]ubectl port-forward.*$(NAMESPACE)" | awk '{print $$2}' | xargs -r kill 2>/dev/null || true
	@echo "All port-forwards stopped!"

# Show status of running port-forwards
port-forward-status:
	@echo "Active port-forwards for $(NAMESPACE) namespace:"
	@echo ""
	@ps aux | grep "[k]ubectl port-forward.*$(NAMESPACE)" || echo "No port-forwards running"

# Alias for backward compatibility
port-forward: port-forward-start

# Restart Dagster deployments
restart-dagster:
	@echo "Restarting Dagster deployments..."
	@kubectl rollout restart deployment -n $(NAMESPACE) -l app.kubernetes.io/instance=dagster
	@echo "Waiting for Dagster webserver to be ready..."
	@kubectl rollout status deployment -n $(NAMESPACE) dagster-dagster-webserver --timeout=120s
	@echo "✓ Dagster restarted successfully!"

# Restart Trino deployments
restart-trino:
	@echo "Restarting Trino deployments..."
	@kubectl rollout restart deployment -n $(NAMESPACE) -l app=trino
	@echo "Waiting for Trino coordinator to be ready..."
	@kubectl rollout status deployment -n $(NAMESPACE) -l app=trino,component=coordinator --timeout=120s
	@echo "✓ Trino restarted successfully!"

# Restart Polaris deployment
restart-polaris:
	@echo "Restarting Polaris deployment..."
	@if kubectl get deployment -n $(NAMESPACE) -l app.kubernetes.io/name=polaris > /dev/null 2>&1; then \
		kubectl rollout restart deployment -n $(NAMESPACE) -l app.kubernetes.io/name=polaris; \
		echo "Waiting for Polaris to be ready..."; \
		kubectl rollout status deployment -n $(NAMESPACE) -l app.kubernetes.io/name=polaris --timeout=120s; \
		echo "✓ Polaris restarted successfully!"; \
	else \
		echo "Polaris not found. Run 'make deploy' to install."; \
	fi

# Restart all services
restart-all:
	@echo "Restarting all services..."
	@echo ""
	@$(MAKE) restart-dagster
	@echo ""
	@$(MAKE) restart-trino
	@echo ""
	@$(MAKE) restart-polaris
	@echo ""
	@echo "✓ All services restarted!"

# Show cluster status
status:
	@echo "Lakehouse Cluster Status"
	@echo "======================="
	@echo ""
	@echo "Namespace:"
	@kubectl get namespace $(NAMESPACE) 2>/dev/null || echo "Namespace $(NAMESPACE) not found"
	@echo ""
	@echo "Helm Releases:"
	@helm list -n $(NAMESPACE) 2>/dev/null || echo "No releases found"
	@echo ""
	@echo "Pods:"
	@kubectl get pods -n $(NAMESPACE) 2>/dev/null || echo "No pods found"
	@echo ""
	@echo "Services:"
	@kubectl get svc -n $(NAMESPACE) 2>/dev/null || echo "No services found"
	@echo ""
	@echo "Persistent Volume Claims:"
	@kubectl get pvc -n $(NAMESPACE) 2>/dev/null || echo "No PVCs found"

# Show Polaris-specific status
polaris-status:
	@echo "Polaris Catalog Status"
	@echo "====================="
	@echo ""
	@echo "Polaris Pods:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=polaris 2>/dev/null || echo "Polaris not deployed"
	@echo ""
	@echo "Polaris Service:"
	@kubectl get svc -n $(NAMESPACE) polaris 2>/dev/null || echo "Polaris service not found"
	@echo ""
	@echo "Recent Events:"
	@kubectl get events -n $(NAMESPACE) --field-selector involvedObject.name=polaris --sort-by='.lastTimestamp' 2>/dev/null | tail -n 5 || echo "No events found"
	@echo ""
	@echo "Recent Logs (last 20 lines):"
	@kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/name=polaris --tail=20 2>/dev/null || echo "No logs available"

# Tail Polaris logs (live)
polaris-logs:
	@echo "Tailing Polaris logs (Ctrl+C to exit)..."
	@kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/name=polaris --tail=50 -f

# Initialize Polaris catalog with RBAC setup
init-polaris:
	@echo "Initializing Polaris catalog with RBAC..."
	@echo ""
	@echo "This will create:"
	@echo "  - lakehouse catalog"
	@echo "  - dagster_user service account"
	@echo "  - Principal and catalog roles"
	@echo "  - CATALOG_MANAGE_CONTENT privileges"
	@echo "  - Namespaces: raw, staging, intermediate, marts"
	@echo ""
	@if ! kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		echo "Error: Polaris not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi
	@if [ -z "$$POLARIS_BOOTSTRAP_CLIENT_ID" ] || [ -z "$$POLARIS_BOOTSTRAP_CLIENT_SECRET" ]; then \
		echo "⚠️  Warning: Bootstrap credentials not set via environment variables."; \
		echo ""; \
		echo "Please provide credentials:"; \
		echo "  export POLARIS_BOOTSTRAP_CLIENT_ID=\"polaris_admin\""; \
		echo "  export POLARIS_BOOTSTRAP_CLIENT_SECRET=\"your_secret\""; \
		echo ""; \
		echo "Or use command-line flags:"; \
		echo "  make init-polaris BOOTSTRAP_ID=polaris_admin BOOTSTRAP_SECRET=your_secret"; \
		echo ""; \
		read -p "Continue anyway? (y/N) " -n 1 -r; \
		echo ""; \
		if [[ ! $$REPLY =~ ^[Yy]$$ ]]; then \
			exit 1; \
		fi; \
	fi
	@if ! ps aux | grep -q "[k]ubectl port-forward.*polaris.*8181"; then \
		echo "Starting port-forward to Polaris..."; \
		kubectl port-forward -n $(NAMESPACE) svc/polaris 8181:8181 > /dev/null 2>&1 & \
		sleep 2; \
	fi
	@echo "Running initialization script..."
	@chmod +x infrastructure/kubernetes/polaris/init-polaris.sh
	@if [ -n "$$BOOTSTRAP_ID" ] && [ -n "$$BOOTSTRAP_SECRET" ]; then \
		infrastructure/kubernetes/polaris/init-polaris.sh --host http://localhost:8181 \
			--bootstrap-client-id "$$BOOTSTRAP_ID" \
			--bootstrap-client-secret "$$BOOTSTRAP_SECRET"; \
	else \
		POLARIS_BOOTSTRAP_CLIENT_ID="$$POLARIS_BOOTSTRAP_CLIENT_ID" \
		POLARIS_BOOTSTRAP_CLIENT_SECRET="$$POLARIS_BOOTSTRAP_CLIENT_SECRET" \
		infrastructure/kubernetes/polaris/init-polaris.sh http://localhost:8181; \
	fi
	@echo ""
	@echo "IMPORTANT: Update orchestration-dagster/set_pyiceberg_env.sh with the new credentials!"

# Setup Polaris RBAC and namespaces (assumes catalog and principal exist)
setup-polaris-rbac:
	@echo "Setting up Polaris RBAC and namespaces..."
	@echo ""
	@echo "This will:"
	@echo "  - Create principal and catalog roles"
	@echo "  - Grant roles and privileges"
	@echo "  - Create namespaces: data"
	@echo ""
	@if ! kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		echo "Error: Polaris not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi
	@if [ -z "$$POLARIS_BOOTSTRAP_CLIENT_ID" ] || [ -z "$$POLARIS_BOOTSTRAP_CLIENT_SECRET" ]; then \
		echo "⚠️  Warning: Bootstrap credentials not set via environment variables."; \
		echo ""; \
		echo "Please provide credentials:"; \
		echo "  export POLARIS_BOOTSTRAP_CLIENT_ID=\"polaris_admin\""; \
		echo "  export POLARIS_BOOTSTRAP_CLIENT_SECRET=\"your_secret\""; \
		echo ""; \
		echo "Or use command-line flags:"; \
		echo "  make setup-polaris-rbac BOOTSTRAP_ID=polaris_admin BOOTSTRAP_SECRET=your_secret"; \
		echo ""; \
		read -p "Continue anyway? (y/N) " -n 1 -r; \
		echo ""; \
		if [[ ! $$REPLY =~ ^[Yy]$$ ]]; then \
			exit 1; \
		fi; \
	fi
	@if ! ps aux | grep -q "[k]ubectl port-forward.*polaris.*8181"; then \
		echo "Starting port-forward to Polaris..."; \
		kubectl port-forward -n $(NAMESPACE) svc/polaris 8181:8181 > /dev/null 2>&1 & \
		sleep 2; \
	fi
	@echo "Running RBAC and namespace setup script..."
	@chmod +x infrastructure/kubernetes/polaris/setup-rbac-namespaces.sh
	@if [ -n "$$BOOTSTRAP_ID" ] && [ -n "$$BOOTSTRAP_SECRET" ]; then \
		infrastructure/kubernetes/polaris/setup-rbac-namespaces.sh --host http://localhost:8181 \
			--bootstrap-client-id "$$BOOTSTRAP_ID" \
			--bootstrap-client-secret "$$BOOTSTRAP_SECRET"; \
	else \
		POLARIS_BOOTSTRAP_CLIENT_ID="$$POLARIS_BOOTSTRAP_CLIENT_ID" \
		POLARIS_BOOTSTRAP_CLIENT_SECRET="$$POLARIS_BOOTSTRAP_CLIENT_SECRET" \
		infrastructure/kubernetes/polaris/setup-rbac-namespaces.sh http://localhost:8181; \
	fi
	@echo ""
	@echo "RBAC and namespace setup complete!"

# Test Polaris catalog connectivity
polaris-test:
	@echo "Testing Polaris catalog connectivity..."
	@echo ""
	@if ! kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		echo "Error: Polaris not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi
	@if ! ps aux | grep -q "[k]ubectl port-forward.*polaris.*8181"; then \
		echo "Starting port-forward to Polaris..."; \
		kubectl port-forward -n $(NAMESPACE) svc/polaris 8181:8181 > /dev/null 2>&1 & \
		sleep 2; \
	fi
	@echo "Testing REST API endpoint..."
	@curl -s http://localhost:8181/api/catalog/v1/config | jq '.' || echo "Failed to connect"
	@echo ""
	@echo "Testing OAuth token endpoint..."
	@if [ -z "$$POLARIS_BOOTSTRAP_CLIENT_ID" ] || [ -z "$$POLARIS_BOOTSTRAP_CLIENT_SECRET" ]; then \
		echo "⚠️  Warning: Bootstrap credentials not set. Skipping OAuth test."; \
		echo "   Set POLARIS_BOOTSTRAP_CLIENT_ID and POLARIS_BOOTSTRAP_CLIENT_SECRET to test authentication."; \
	else \
		curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
			--user "$$POLARIS_BOOTSTRAP_CLIENT_ID:$$POLARIS_BOOTSTRAP_CLIENT_SECRET" \
			-d 'grant_type=client_credentials' \
			-d 'scope=PRINCIPAL_ROLE:ALL' | jq '.access_token' || echo "Failed to authenticate"; \
	fi
	@echo ""
	@echo "Polaris catalog is accessible!"

# Rebuild and deploy Dagster user code
deploy-dagster-code:
	@echo "Rebuilding and deploying orchestration-dagster user code..."
	@echo ""
	@echo "Step 1/4: Building Docker image..."
	@cd orchestration-dagster && docker build -t orchestration-dagster:latest .
	@echo "✓ Docker image built"
	@echo ""
	@echo "Step 2/4: Applying ConfigMap..."
	@kubectl apply -f infrastructure/kubernetes/dagster/user-code-env-configmap.yaml
	@echo "✓ ConfigMap applied"
	@echo ""
	@echo "Step 3/5: Applying Secrets..."
	@if [ ! -f infrastructure/kubernetes/dagster/user-code-secrets.yaml ]; then \
		echo "⚠️  user-code-secrets.yaml not found."; \
		echo "   Generating from sources..."; \
		$(MAKE) generate-user-secrets; \
	fi
	@kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml
	@echo "✓ Secrets applied"
	@echo ""
	@echo "Step 4/5: Scaling user code deployment to 1 replica..."
	@kubectl scale deployment -n $(NAMESPACE) dagster-dagster-user-deployments-orchestration-dagster --replicas=1
	@echo "✓ Deployment scaled up"
	@echo ""
	@echo "Step 5/5: Restarting Dagster user code deployment..."
	@kubectl rollout restart deployment/dagster-dagster-user-deployments-orchestration-dagster -n $(NAMESPACE)
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=dagster,component=user-deployments -n $(NAMESPACE) --timeout=120s
	@echo "✓ Dagster user code deployed successfully!"
	@echo ""
	@echo "Deployment complete! Access Dagster at http://localhost:3001"

##################################################
# DOCKER COMPOSE COMMANDS (Local Streaming Stack)
##################################################

# Start all Docker Compose services
docker-up:
	@echo "Starting Docker Compose stack (Kafka, Flink, Polaris, MinIO, Trino, Dagster)..."
	@cd $(DOCKER_DIR) && docker compose up -d --build
	@echo ""
	@echo "✓ Stack started successfully!"
	@echo ""
	@echo "Access URLs:"
	@echo "  Flink Web UI:  http://localhost:8081"
	@echo "  Kafka Broker:  localhost:9092"
	@echo "  Polaris API:   http://localhost:8181"
	@echo "  MinIO Console: http://localhost:9001 (admin/password)"
	@echo "  MinIO S3 API:  http://localhost:9000"
	@echo "  Trino:         http://localhost:8080"
	@echo "  Dagster:       http://localhost:3000"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Attach to Flink SQL client:"
	@echo "     docker compose -f $(DOCKER_DIR)/docker-compose.yml attach flink-sql-client"
	@echo "  2. Generate payment events:"
	@echo "     make jr-charges"
	@echo ""

# Stop and remove all Docker Compose services
docker-down:
	@echo "Stopping Docker Compose stack..."
	@cd $(DOCKER_DIR) && docker compose down
	@echo "✓ Stack stopped"

# Build/rebuild Docker images (especially Flink)
docker-build:
	@echo "Building Docker images..."
	@cd $(DOCKER_DIR) && docker compose build
	@echo "✓ Images built"

# Restart all Docker Compose services
docker-restart:
	@echo "Restarting Docker Compose stack..."
	@cd $(DOCKER_DIR) && docker compose restart
	@echo "✓ Stack restarted"

# Show status of Docker Compose services
docker-status:
	@echo "Docker Compose Services Status:"
	@echo "================================"
	@cd $(DOCKER_DIR) && docker compose ps

# View logs from all Docker Compose services
docker-logs:
	@echo "Viewing Docker Compose logs (Ctrl+C to exit)..."
	@cd $(DOCKER_DIR) && docker compose logs -f

##################################################
# JR DATA GENERATION COMMANDS (Payment Events)
##################################################

# Generate payment charge events
jr-charges:
	@if ! command -v jr >/dev/null 2>&1; then \
		echo "❌ Error: JR tool not found"; \
		echo ""; \
		echo "Install JR:"; \
		echo "  brew install jr"; \
		echo "  or: sudo snap install jrnd && sudo snap alias jrnd.jr jr"; \
		echo ""; \
		echo "Or see: make jr-help"; \
		exit 1; \
	fi
	@$(JR_DIR)/generate-charges.sh

# Generate payment refund events
jr-refunds:
	@if ! command -v jr >/dev/null 2>&1; then \
		echo "❌ Error: JR tool not found. Run 'make jr-help' for installation."; \
		exit 1; \
	fi
	@$(JR_DIR)/generate-refunds.sh

# Generate payment dispute events
jr-disputes:
	@if ! command -v jr >/dev/null 2>&1; then \
		echo "❌ Error: JR tool not found. Run 'make jr-help' for installation."; \
		exit 1; \
	fi
	@$(JR_DIR)/generate-disputes.sh

# Generate subscription events
jr-subscriptions:
	@if ! command -v jr >/dev/null 2>&1; then \
		echo "❌ Error: JR tool not found. Run 'make jr-help' for installation."; \
		exit 1; \
	fi
	@$(JR_DIR)/generate-subscriptions.sh

# Generate all event types simultaneously (background processes)
jr-all:
	@if ! command -v jr >/dev/null 2>&1; then \
		echo "❌ Error: JR tool not found. Run 'make jr-help' for installation."; \
		exit 1; \
	fi
	@$(JR_DIR)/generate-all.sh

# Create Kafka topics for payment events
jr-create-topics:
	@echo "Creating Kafka topics for payment events..."
	@echo ""
	@if ! docker ps | grep -q kafka-broker; then \
		echo "❌ Error: Kafka broker not running"; \
		echo "   Start Docker Compose first: make docker-up"; \
		exit 1; \
	fi
	@echo "Creating topic: payment_charges"
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
		/opt/kafka/bin/kafka-topics.sh --create --topic payment_charges \
		--bootstrap-server localhost:9092 \
		--replication-factor 1 --partitions 1 \
		--if-not-exists 2>/dev/null || true
	@echo "Creating topic: payment_refunds"
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
		/opt/kafka/bin/kafka-topics.sh --create --topic payment_refunds \
		--bootstrap-server localhost:9092 \
		--replication-factor 1 --partitions 1 \
		--if-not-exists 2>/dev/null || true
	@echo "Creating topic: payment_disputes"
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
		/opt/kafka/bin/kafka-topics.sh --create --topic payment_disputes \
		--bootstrap-server localhost:9092 \
		--replication-factor 1 --partitions 1 \
		--if-not-exists 2>/dev/null || true
	@echo "Creating topic: payment_subscriptions"
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
		/opt/kafka/bin/kafka-topics.sh --create --topic payment_subscriptions \
		--bootstrap-server localhost:9092 \
		--replication-factor 1 --partitions 1 \
		--if-not-exists 2>/dev/null || true
	@echo ""
	@echo "✓ Topics created successfully"
	@echo ""
	@echo "List topics:"
	@docker compose -f $(DOCKER_DIR)/docker-compose.yml exec -T kafka-broker \
		/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Stop all running JR processes
jr-stop:
	@echo "Stopping all JR processes..."
	@pkill -f "jr run" 2>/dev/null || echo "No JR processes found"
	@echo "✓ All JR processes stopped"

# Show JR installation and usage help
jr-help:
	@echo "JR - Random Data Generator"
	@echo "=========================="
	@echo ""
	@echo "Installation:"
	@echo "  macOS/Linux (Homebrew):"
	@echo "    brew install jr"
	@echo ""
	@echo "  Manual installation:"
	@echo "    See: https://github.com/ugol/jr"
	@echo ""
	@echo "Important: JR Configuration Fix"
	@echo "================================"
	@echo "After installing JR via Homebrew, delete the default config:"
	@echo "  rm /opt/homebrew/etc/jr/jrconfig.json"
	@echo ""
	@echo "This prevents JSON Schema format conflicts with our setup."
	@echo ""
	@echo "Available Commands:"
	@echo "  make jr-charges       - Generate charge events"
	@echo "  make jr-refunds       - Generate refund events"
	@echo "  make jr-disputes      - Generate dispute events"
	@echo "  make jr-subscriptions - Generate subscription events"
	@echo "  make jr-all           - Generate all events simultaneously"
	@echo "  make jr-stop          - Stop all JR processes"
	@echo ""
	@echo "Event Templates Location:"
	@echo "  $(JR_DIR)/"
	@echo ""
	@echo "Kafka Topics (created automatically):"
	@echo "  - payment_charges"
	@echo "  - payment_refunds"
	@echo "  - payment_disputes"
	@echo "  - payment_subscriptions"
	@echo ""
	@echo "View Kafka topics:"
	@echo "  docker compose -f $(DOCKER_DIR)/docker-compose.yml exec kafka-broker \\"
	@echo "    kafka-topics.sh --list --bootstrap-server localhost:9092"
	@echo ""
	@echo "Consume events (example):"
	@echo "  docker compose -f $(DOCKER_DIR)/docker-compose.yml exec kafka-broker \\"
	@echo "    kafka-console-consumer.sh --bootstrap-server localhost:9092 \\"
	@echo "    --topic payment_charges --from-beginning"

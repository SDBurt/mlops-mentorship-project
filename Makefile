# Kubernetes Lakehouse Platform - Makefile
# Simplified deployment automation for lakehouse namespace architecture

.PHONY: help check setup deploy destroy clean-old clean-nessie port-forward port-forward-start port-forward-stop port-forward-status restart-dagster restart-trino restart-polaris restart-all status polaris-status polaris-logs init-polaris polaris-test deploy-dagster-code

# Variables
NAMESPACE := lakehouse
HELM_TIMEOUT := 10m
MINIO_VALUES := infrastructure/kubernetes/minio/values.yaml
DAGSTER_VALUES := infrastructure/kubernetes/dagster/values.yaml
TRINO_VALUES := infrastructure/kubernetes/trino/values.yaml
POLARIS_VALUES := infrastructure/kubernetes/polaris/values.yaml
POLARIS_SECRETS := infrastructure/kubernetes/polaris/secrets.yaml

# Default target - show help
help:
	@echo "Kubernetes Lakehouse Platform - Available Commands"
	@echo ""
	@echo "Prerequisites (run once):"
	@echo "  make check              - Verify kubectl and helm are installed"
	@echo "  make setup              - Add/update Helm repositories"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy                 - Deploy all services to lakehouse namespace"
	@echo ""
	@echo "Management:"
	@echo "  make destroy                - Tear down lakehouse cluster"
	@echo "  make clean-old              - One-time cleanup of old separate namespaces (migration only)"
	@echo "  make clean-nessie           - Remove Nessie (if previously deployed) - MIGRATION ONLY"
	@echo "  make status                 - Show cluster status"
	@echo ""
	@echo "Polaris Operations:"
	@echo "  make init-polaris           - Initialize Polaris catalog with RBAC (run after deploy)"
	@echo "  make polaris-test           - Test Polaris catalog connectivity"
	@echo "  make polaris-status         - Show Polaris pod status and logs summary"
	@echo "  make polaris-logs           - Tail Polaris logs (live)"
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
	@echo "  make deploy-dagster-code    - Rebuild and deploy orchestration-dagster user code"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make check && make setup"
	@echo "  2. make deploy"
	@echo "  3. make port-forward-start (runs in background)"
	@echo "  4. make port-forward-stop (when done)"
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

# Setup Helm repositories
setup:
	@echo "Setting up Helm repositories..."
	@helm repo add dagster https://dagster-io.github.io/helm
	@helm repo add trino https://trinodb.github.io/charts
	@helm repo add polaris https://apache.github.io/polaris
	@helm repo update
	@echo "✓ Helm repositories configured"

# Deploy all services to lakehouse namespace
deploy:
	@echo "Deploying lakehouse platform..."
	@echo ""
	@echo "Step 1/4: Creating lakehouse namespace..."
	@kubectl apply -f infrastructure/kubernetes/namespace.yaml
	@echo ""
	@echo "Step 2/4: Deploying MinIO (S3 storage)..."
	@kubectl apply -f infrastructure/kubernetes/minio/minio-standalone.yaml
	@echo "Waiting for MinIO to be ready..."
	@kubectl wait --for=condition=ready pod -l app=minio -n $(NAMESPACE) --timeout=120s
	@echo "✓ MinIO deployed"
	@echo ""
	@echo "Step 3/4: Deploying Dagster (orchestration)..."
	@helm upgrade --install dagster dagster/dagster \
		-f $(DAGSTER_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT) || true
	@kubectl scale deployment -n $(NAMESPACE) dagster-dagster-user-deployments-dagster-user-code --replicas=0 2>/dev/null || true
	@echo "✓ Dagster deployed"
	@echo ""
	@echo "Step 4/5: Deploying Trino (query engine)..."
	@helm upgrade --install trino trino/trino \
		-f $(TRINO_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)
	@echo "✓ Trino deployed"
	@echo ""
	@echo "Step 5/5: Deploying Polaris (Apache Iceberg REST catalog)..."
	@kubectl apply -f $(POLARIS_SECRETS)
	@helm upgrade --install polaris polaris/polaris \
		-f $(POLARIS_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)
	@echo "✓ Polaris deployed"
	@echo ""
	@echo "Deployment complete! MinIO is ready with default bucket 'lakehouse'."
	@echo "Polaris REST catalog is available for unified Iceberg table management."


# Teardown lakehouse cluster
destroy:
	@echo "Tearing down lakehouse cluster..."
	@echo ""
	@echo "This will destroy all services and data in lakehouse namespace."
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
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
	@if ! ps aux | grep -q "[k]ubectl port-forward.*polaris.*8181"; then \
		echo "Starting port-forward to Polaris..."; \
		kubectl port-forward -n $(NAMESPACE) svc/polaris 8181:8181 > /dev/null 2>&1 & \
		sleep 2; \
	fi
	@echo "Running initialization script..."
	@chmod +x infrastructure/kubernetes/polaris/init-polaris.sh
	@infrastructure/kubernetes/polaris/init-polaris.sh http://localhost:8181
	@echo ""
	@echo "IMPORTANT: Update orchestration-dagster/set_pyiceberg_env.sh with the new credentials!"

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
	@curl -s http://localhost:8181/api/catalog/v1/oauth/tokens \
		--user polaris_admin:polaris_admin_secret \
		-d 'grant_type=client_credentials' \
		-d 'scope=PRINCIPAL_ROLE:ALL' | jq '.access_token' || echo "Failed to authenticate"
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
	@echo "Step 3/4: Applying Secrets..."
	@kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml
	@echo "✓ Secrets applied"
	@echo ""
	@echo "Step 4/4: Restarting Dagster user code deployment..."
	@kubectl rollout restart deployment/dagster-dagster-user-deployments-orchestration-dagster -n $(NAMESPACE)
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=dagster,component=user-deployments -n $(NAMESPACE) --timeout=120s
	@echo "✓ Dagster user code deployed successfully!"
	@echo ""
	@echo "Deployment complete! Access Dagster at http://localhost:3001"

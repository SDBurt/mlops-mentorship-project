# Kubernetes Lakehouse Platform - Makefile
# Simplified deployment automation for lakehouse namespace architecture

.PHONY: help check setup deploy destroy clean-old port-forward port-forward-start port-forward-stop port-forward-status restart-dagster restart-trino restart-all status

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
	@echo "  make status                 - Show cluster status"
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
	@echo "  make restart-all            - Restart all service deployments"
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
	@echo "Note: Polaris chart is installed from GitHub repo (no official Helm repo yet)"
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
	@echo "Step 5/5: Deploying Polaris (REST catalog - optional Phase 3)..."
	@echo "Note: Polaris requires secrets file. Skipping if not present."
	@if [ -f $(POLARIS_SECRETS) ]; then \
		kubectl apply -f $(POLARIS_SECRETS) && \
		echo "Polaris deployment requires cloning the chart from GitHub:" && \
		echo "  git clone https://github.com/apache/polaris.git /tmp/polaris-repo" && \
		echo "  helm upgrade --install polaris /tmp/polaris-repo/helm/polaris -f $(POLARIS_VALUES) -n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)" && \
		echo "✓ Polaris ready to deploy (run commands above)"; \
	else \
		echo "⊘ Polaris secrets not found at $(POLARIS_SECRETS) - skipping (Phase 3)"; \
	fi
	@echo ""
	@echo "Deployment complete! MinIO is ready with default bucket 'lakehouse'."


# Teardown lakehouse cluster
destroy:
	@echo "Tearing down lakehouse cluster..."
	@echo ""
	@echo "This will destroy all services and data in lakehouse namespace."
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@echo ""
	@echo "Uninstalling Polaris (if deployed)..."
	@helm uninstall polaris -n $(NAMESPACE) 2>/dev/null || echo "Polaris not found (Phase 3)"
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
	@helm uninstall minio -n minio 2>/dev/null || echo "minio namespace not found (old Garage namespace cleanup)"
	@echo ""
	@echo "Deleting old namespaces..."
	@kubectl delete namespace dagster --wait=false 2>/dev/null || echo "dagster namespace already deleted"
	@kubectl delete namespace trino --wait=false 2>/dev/null || echo "trino namespace already deleted"
	@kubectl delete namespace minio --wait=false 2>/dev/null || echo "minio namespace already deleted (old Garage namespace cleanup)"
	@echo ""
	@echo "Old namespace cleanup complete!"

# Port-forward all service UIs (starts in background)
port-forward-start:
	@echo "Starting port-forwards in background..."
	@echo ""
	@kubectl port-forward -n $(NAMESPACE) svc/dagster-dagster-webserver 3000:80 > /dev/null 2>&1 &
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
	@echo "  Dagster:       http://localhost:3000"
	@echo "  Trino:         http://localhost:8080"
	@echo "  MinIO API:     http://localhost:9000 (S3 API)"
	@echo "  MinIO Console: http://localhost:9001 (Web UI)"
	@if kubectl get svc polaris -n $(NAMESPACE) > /dev/null 2>&1; then \
		echo "  Polaris:       http://localhost:8181 (REST Catalog - Phase 3)"; \
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

# Restart all services
restart-all:
	@echo "Restarting all services..."
	@echo ""
	@$(MAKE) restart-dagster
	@echo ""
	@$(MAKE) restart-trino
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

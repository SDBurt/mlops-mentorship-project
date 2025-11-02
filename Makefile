# Kubernetes Lakehouse Platform - Makefile
# Simplified deployment automation for lakehouse namespace architecture

.PHONY: help check setup fetch-garage-chart deploy init destroy clean-old port-forward port-forward-start port-forward-stop port-forward-status restart-dagster restart-trino restart-all status

# Variables
NAMESPACE := lakehouse
HELM_TIMEOUT := 10m
GARAGE_CHART_PATH := infrastructure/helm/garage
GARAGE_VALUES := infrastructure/kubernetes/garage/values.yaml
DAGSTER_VALUES := infrastructure/kubernetes/dagster/values.yaml
TRINO_VALUES := infrastructure/kubernetes/trino/values.yaml

# Default target - show help
help:
	@echo "Kubernetes Lakehouse Platform - Available Commands"
	@echo ""
	@echo "Prerequisites (run once):"
	@echo "  make check              - Verify kubectl and helm are installed"
	@echo "  make setup              - Add/update Helm repositories"
	@echo "  make fetch-garage-chart - Clone Garage Helm chart from git"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy                 - Deploy all services to lakehouse namespace"
	@echo "  make init                   - Initialize Garage cluster (run after deploy)"
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
	@echo "  1. make check && make setup && make fetch-garage-chart"
	@echo "  2. make deploy"
	@echo "  3. make init"
	@echo "  4. make port-forward-start (runs in background)"
	@echo "  5. make port-forward-stop (when done)"
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
	@helm repo update
	@echo "✓ Helm repositories configured"

# Fetch Garage chart from git (no public Helm repo available)
fetch-garage-chart:
	@echo "Fetching Garage Helm chart..."
	@mkdir -p infrastructure/helm
	@if [ -d "$(GARAGE_CHART_PATH)" ]; then \
		echo "✓ Garage chart already exists at $(GARAGE_CHART_PATH)"; \
	else \
		echo "Cloning Garage repository..."; \
		git clone --depth 1 https://git.deuxfleurs.fr/Deuxfleurs/garage.git /tmp/garage-repo; \
		cp -r /tmp/garage-repo/script/helm/garage $(GARAGE_CHART_PATH); \
		rm -rf /tmp/garage-repo; \
		echo "✓ Garage chart fetched to $(GARAGE_CHART_PATH)"; \
	fi

# Deploy all services to lakehouse namespace
deploy:
	@echo "Deploying lakehouse platform..."
	@echo ""
	@echo "Step 1/4: Creating lakehouse namespace..."
	@kubectl apply -f infrastructure/kubernetes/namespace.yaml
	@echo ""
	@echo "Step 2/4: Deploying Garage (S3 storage)..."
	@helm upgrade --install garage $(GARAGE_CHART_PATH) \
		-f $(GARAGE_VALUES) \
		-n $(NAMESPACE) --wait
	@echo "✓ Garage deployed"
	@echo ""
	@echo "Step 3/4: Deploying Dagster (orchestration)..."
	@helm upgrade --install dagster dagster/dagster \
		-f $(DAGSTER_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT) || true
	@kubectl scale deployment -n $(NAMESPACE) dagster-dagster-user-deployments-dagster-user-code --replicas=0 2>/dev/null || true
	@echo "✓ Dagster deployed"
	@echo ""
	@echo "Step 4/4: Deploying Trino (query engine)..."
	@helm upgrade --install trino trino/trino \
		-f $(TRINO_VALUES) \
		-n $(NAMESPACE) --wait --timeout $(HELM_TIMEOUT)
	@echo "✓ Trino deployed"
	@echo ""
	@echo "Deployment complete! Run 'make init' to initialize Garage cluster."

# Initialize Garage cluster (CRITICAL POST-DEPLOYMENT STEP)
init:
	@echo "Initializing Garage cluster..."
	@echo ""
	@echo "This step configures Garage to accept data storage."
	@echo "Without initialization, Garage cannot store any data!"
	@echo ""
	@GARAGE_POD=$$(kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=garage -o jsonpath='{.items[0].metadata.name}'); \
	echo "Using Garage pod: $$GARAGE_POD"; \
	echo ""; \
	echo "Step 1/5: Checking cluster status..."; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage status; \
	echo ""; \
	echo "Step 2/5: Extracting node ID..."; \
	NODE_ID=$$(kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage status 2>/dev/null | grep -A 2 "HEALTHY NODES" | tail -1 | awk '{print $$1}'); \
	echo "Node ID: $$NODE_ID"; \
	echo ""; \
	echo "Step 3/5: Assigning storage role (10GB capacity)..."; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage layout assign -z garage-dc -c 10G $$NODE_ID; \
	echo ""; \
	echo "Step 4/5: Applying layout (version 1)..."; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage layout apply --version 1; \
	echo ""; \
	echo "Step 5/5: Creating S3 bucket and access keys..."; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage bucket create lakehouse 2>/dev/null || echo "Bucket 'lakehouse' already exists"; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage key create lakehouse-access 2>/dev/null || echo "Key 'lakehouse-access' already exists (run 'kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage key list' to view)"; \
	kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage bucket allow --read --write lakehouse --key lakehouse-access; \
	echo ""; \
	echo "Garage initialization complete!"; \
	echo ""; \
	echo "To view your access credentials:"; \
	echo "  kubectl exec -n $(NAMESPACE) $$GARAGE_POD -- /garage key info lakehouse-access"
	@echo ""
	@echo "Initialization complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Configure Meltano for data ingestion"
	@echo "  2. Run 'make port-forward-start' to access UIs"

# Teardown lakehouse cluster
destroy:
	@echo "Tearing down lakehouse cluster..."
	@echo ""
	@echo "This will destroy all services and data in lakehouse namespace."
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@echo ""
	@echo "Uninstalling Dagster..."
	@helm uninstall dagster -n $(NAMESPACE) 2>/dev/null || echo "Dagster not found"
	@echo "Uninstalling Trino..."
	@helm uninstall trino -n $(NAMESPACE) 2>/dev/null || echo "Trino not found"
	@echo "Uninstalling Garage..."
	@helm uninstall garage -n $(NAMESPACE) 2>/dev/null || echo "Garage not found"
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
	@helm uninstall garage -n garage 2>/dev/null || echo "garage namespace not found"
	@echo ""
	@echo "Deleting old namespaces..."
	@kubectl delete namespace dagster --wait=false 2>/dev/null || echo "dagster namespace already deleted"
	@kubectl delete namespace trino --wait=false 2>/dev/null || echo "trino namespace already deleted"
	@kubectl delete namespace garage --wait=false 2>/dev/null || echo "garage namespace already deleted"
	@echo ""
	@echo "Old namespace cleanup complete!"

# Port-forward all service UIs (starts in background)
port-forward-start:
	@echo "Starting port-forwards in background..."
	@echo ""
	@kubectl port-forward -n $(NAMESPACE) svc/dagster-dagster-webserver 3000:80 > /dev/null 2>&1 &
	@kubectl port-forward -n $(NAMESPACE) svc/trino 8080:8080 > /dev/null 2>&1 &
	@kubectl port-forward -n $(NAMESPACE) svc/garage 3900:3900 > /dev/null 2>&1 &
	@sleep 1
	@echo "Port-forwards started!"
	@echo ""
	@echo "Access URLs:"
	@echo "  Dagster: http://localhost:3000"
	@echo "  Trino:   http://localhost:8080"
	@echo "  Garage:  http://localhost:3900 (S3 API)"
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

#!/bin/bash
# Polaris Catalog Initialization Script
#
# This script initializes Apache Polaris with proper RBAC configuration for Dagster.
# It creates a service account principal with necessary permissions for catalog management.
#
# Prerequisites:
# - Polaris deployed and accessible (kubectl port-forward to localhost:8181)
# - Bootstrap credentials provided via environment variables or command-line flags
# - curl and jq installed
#
# Usage:
#   # Using environment variables (recommended):
#   export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
#   export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"
#   ./init-polaris.sh [--host http://localhost:8181]
#
#   # Using command-line flags:
#   ./init-polaris.sh --host http://localhost:8181 \
#     --bootstrap-client-id polaris_admin \
#     --bootstrap-client-secret your_secret

set -e  # Exit on error

# Configuration - Parse command line arguments
POLARIS_HOST=""
POS_ARG=""
BOOTSTRAP_CLIENT_ID=""
BOOTSTRAP_CLIENT_SECRET=""

# Parse arguments: handle --host, --bootstrap-client-id, --bootstrap-client-secret flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            shift
            POLARIS_HOST="$1"
            shift
            ;;
        --host=*)
            POLARIS_HOST="${1#--host=}"
            shift
            ;;
        --bootstrap-client-id)
            shift
            BOOTSTRAP_CLIENT_ID="$1"
            shift
            ;;
        --bootstrap-client-id=*)
            BOOTSTRAP_CLIENT_ID="${1#--bootstrap-client-id=}"
            shift
            ;;
        --bootstrap-client-secret)
            shift
            BOOTSTRAP_CLIENT_SECRET="$1"
            shift
            ;;
        --bootstrap-client-secret=*)
            BOOTSTRAP_CLIENT_SECRET="${1#--bootstrap-client-secret=}"
            shift
            ;;
        *)
            if [ -z "$POS_ARG" ]; then
                POS_ARG="$1"
            fi
            shift
            ;;
    esac
done

# Set POLARIS_HOST from flag, positional argument, or default
if [ -z "$POLARIS_HOST" ]; then
    POLARIS_HOST="${POS_ARG:-http://localhost:8181}"
fi

# Get bootstrap credentials from flags, environment variables, or fail
if [ -z "$BOOTSTRAP_CLIENT_ID" ]; then
    BOOTSTRAP_CLIENT_ID="${POLARIS_BOOTSTRAP_CLIENT_ID:-}"
fi

if [ -z "$BOOTSTRAP_CLIENT_SECRET" ]; then
    BOOTSTRAP_CLIENT_SECRET="${POLARIS_BOOTSTRAP_CLIENT_SECRET:-}"
fi

CATALOG_NAME="lakehouse"
PRINCIPAL_NAME="dagster_user"
PRINCIPAL_ROLE_NAME="dagster_role"
CATALOG_ROLE_NAME="catalog_admin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate bootstrap credentials are provided
if [ -z "$BOOTSTRAP_CLIENT_ID" ] || [ -z "$BOOTSTRAP_CLIENT_SECRET" ]; then
    log_error "Bootstrap credentials are required!"
    echo ""
    echo "Provide credentials via:"
    echo "  1. Environment variables:"
    echo "     export POLARIS_BOOTSTRAP_CLIENT_ID=\"polaris_admin\""
    echo "     export POLARIS_BOOTSTRAP_CLIENT_SECRET=\"your_secret\""
    echo ""
    echo "  2. Command-line flags:"
    echo "     --bootstrap-client-id polaris_admin --bootstrap-client-secret your_secret"
    echo ""
    echo "  3. Kubernetes Secret (for in-cluster use):"
    echo "     kubectl get secret polaris-bootstrap-secret -n lakehouse -o jsonpath='{.data.credentials}' | base64 -d"
    echo ""
    exit 1
fi

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed. Please install curl."
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed. Please install jq."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Get OAuth token from Polaris
get_token() {
    local client_id="$1"
    local client_secret="$2"

    local response=$(curl -s -w "\n%{http_code}" "${POLARIS_HOST}/api/catalog/v1/oauth/tokens" \
        --user "${client_id}:${client_secret}" \
        -d 'grant_type=client_credentials' \
        -d 'scope=PRINCIPAL_ROLE:ALL')

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" != "200" ]; then
        log_error "Failed to get OAuth token (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi

    echo "$body" | jq -r '.access_token'
}

# Test Polaris connectivity
test_connectivity() {
    log_info "Testing connectivity to Polaris at ${POLARIS_HOST}..."

    # Test connectivity by attempting to get an OAuth token with bootstrap credentials
    local response=$(curl -s -w "\n%{http_code}" "${POLARIS_HOST}/api/catalog/v1/oauth/tokens" \
        --user "${BOOTSTRAP_CLIENT_ID}:${BOOTSTRAP_CLIENT_SECRET}" \
        -d 'grant_type=client_credentials' \
        -d 'scope=PRINCIPAL_ROLE:ALL')

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" != "200" ]; then
        log_error "Cannot connect to Polaris or authentication failed (HTTP $http_code)"
        log_error "Make sure:"
        log_error "  1. Port-forward is running: kubectl port-forward -n lakehouse svc/polaris 8181:8181"
        log_error "  2. Bootstrap credentials are correct"
        log_error "  3. Credentials are provided via environment variables or command-line flags"
        exit 1
    fi

    # Check if we got a valid token
    local token=$(echo "$body" | jq -r '.access_token')
    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get OAuth token from Polaris"
        exit 1
    fi

    log_success "Connected to Polaris and authenticated"
}

# Get or create catalog
setup_catalog() {
    local token="$1"
    log_info "Setting up catalog: ${CATALOG_NAME}..."

    # Check if catalog exists
    local response=$(curl -s -w "\n%{http_code}" \
        "${POLARIS_HOST}/api/management/v1/catalogs/${CATALOG_NAME}" \
        -H "Authorization: Bearer ${token}")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "200" ]; then
        log_warn "Catalog '${CATALOG_NAME}' already exists"
        return 0
    fi

    # Create catalog
    log_info "Creating catalog '${CATALOG_NAME}'..."
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "${POLARIS_HOST}/api/management/v1/catalogs" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"catalog\": {
                \"type\": \"INTERNAL\",
                \"name\": \"${CATALOG_NAME}\",
                \"properties\": {
                    \"default-base-location\": \"s3://lakehouse/warehouse/\"
                },
                \"storageConfigInfo\": {
                    \"storageType\": \"S3\",
                    \"allowedLocations\": [\"s3://lakehouse\"]
                }
            }
        }")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
        log_error "Failed to create catalog (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi

    log_success "Catalog '${CATALOG_NAME}' created"
}

# Create principal (service account)
create_principal() {
    local token="$1"
    log_info "Creating principal: ${PRINCIPAL_NAME}..."

    local response=$(curl -s -w "\n%{http_code}" -X POST \
        "${POLARIS_HOST}/api/management/v1/principals" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"principal\": {
                \"name\": \"${PRINCIPAL_NAME}\",
                \"type\": \"SERVICE\"
            }
        }")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "409" ]; then
        log_warn "Principal '${PRINCIPAL_NAME}' already exists"
        # Get existing principal credentials
        return 0
    fi

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
        log_error "Failed to create principal (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi

    # Extract credentials from response
    local client_id=$(echo "$body" | jq -r '.credentials.clientId')
    local client_secret=$(echo "$body" | jq -r '.credentials.clientSecret')

    log_success "Principal '${PRINCIPAL_NAME}' created"
    log_info "Client ID: ${client_id}"
    log_info "Client Secret: ${client_secret}"

    # Save credentials to file
    mkdir -p "$(dirname "$0")/.credentials"
    cat > "$(dirname "$0")/.credentials/dagster_user.txt" <<EOF
# Dagster User Credentials (Generated: $(date))
export POLARIS_CLIENT_ID="${client_id}"
export POLARIS_CLIENT_SECRET="${client_secret}"
EOF

    log_success "Credentials saved to $(dirname "$0")/.credentials/dagster_user.txt"

    # Export for use in this script
    export DAGSTER_CLIENT_ID="$client_id"
    export DAGSTER_CLIENT_SECRET="$client_secret"
}

# Create principal role
create_principal_role() {
    local token="$1"
    log_info "Creating principal role: ${PRINCIPAL_ROLE_NAME}..."

    local response=$(curl -s -w "\n%{http_code}" -X POST \
        "${POLARIS_HOST}/api/management/v1/principal-roles" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"principalRole\": {
                \"name\": \"${PRINCIPAL_ROLE_NAME}\"
            }
        }")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "409" ]; then
        log_warn "Principal role '${PRINCIPAL_ROLE_NAME}' already exists"
        return 0
    fi

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
        log_error "Failed to create principal role (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi

    log_success "Principal role '${PRINCIPAL_ROLE_NAME}' created"
}

# Grant principal role to principal
grant_principal_role() {
    local token="$1"
    log_info "Granting principal role '${PRINCIPAL_ROLE_NAME}' to '${PRINCIPAL_NAME}'..."

    # Try assigning the principal role to the principal
    local response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${POLARIS_HOST}/api/management/v1/principal-roles/${PRINCIPAL_ROLE_NAME}/principals/${PRINCIPAL_NAME}" \
        -H "Authorization: Bearer ${token}")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ] && [ "$http_code" != "204" ]; then
        # Try alternative endpoint structure
        log_warn "First endpoint failed (HTTP $http_code), trying alternative..."
        response=$(curl -s -w "\n%{http_code}" -X PUT \
            "${POLARIS_HOST}/api/management/v1/principals/${PRINCIPAL_NAME}/principal-roles" \
            -H "Authorization: Bearer ${token}" \
            -H "Content-Type: application/json" \
            -d "{\"principalRole\": {\"name\": \"${PRINCIPAL_ROLE_NAME}\"}}")

        http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | head -n-1)

        # Check if it's a duplicate key error (grant already exists)
        if echo "$body" | grep -q "duplicate key value"; then
            log_warn "Principal role already granted (duplicate key - this is OK)"
            return 0
        fi

        if [ "$http_code" != "200" ] && [ "$http_code" != "201" ] && [ "$http_code" != "204" ]; then
            log_error "Failed to grant principal role (HTTP $http_code)"
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
            return 1
        fi
    fi

    log_success "Principal role granted to principal"
}

# Create catalog role
create_catalog_role() {
    local token="$1"
    log_info "Creating catalog role: ${CATALOG_ROLE_NAME}..."

    local response=$(curl -s -w "\n%{http_code}" -X POST \
        "${POLARIS_HOST}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"catalogRole\": {
                \"name\": \"${CATALOG_ROLE_NAME}\"
            }
        }")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "409" ]; then
        log_warn "Catalog role '${CATALOG_ROLE_NAME}' already exists"
        return 0
    fi

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
        log_error "Failed to create catalog role (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi

    log_success "Catalog role '${CATALOG_ROLE_NAME}' created"
}

# Grant catalog role to principal role
grant_catalog_role() {
    local token="$1"
    log_info "Granting catalog role '${CATALOG_ROLE_NAME}' to principal role '${PRINCIPAL_ROLE_NAME}'..."

    # Try various endpoint structures
    local response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${POLARIS_HOST}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles/${CATALOG_ROLE_NAME}/principal-roles/${PRINCIPAL_ROLE_NAME}" \
        -H "Authorization: Bearer ${token}")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ] && [ "$http_code" != "204" ]; then
        # Try with JSON body
        log_warn "First endpoint failed (HTTP $http_code), trying alternative with JSON body..."
        response=$(curl -s -w "\n%{http_code}" -X PUT \
            "${POLARIS_HOST}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles/${CATALOG_ROLE_NAME}/principal-roles" \
            -H "Authorization: Bearer ${token}" \
            -H "Content-Type: application/json" \
            -d "{\"principalRole\": {\"name\": \"${PRINCIPAL_ROLE_NAME}\"}}")

        http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | head -n-1)

        # Check if it's a duplicate key error (grant already exists)
        if echo "$body" | grep -q "duplicate key value"; then
            log_warn "Catalog role already granted (duplicate key - this is OK)"
            return 0
        fi

        if [ "$http_code" != "200" ] && [ "$http_code" != "201" ] && [ "$http_code" != "204" ]; then
            log_error "Failed to grant catalog role (HTTP $http_code)"
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
            return 1
        fi
    fi

    log_success "Catalog role granted to principal role"
}

# Grant catalog privileges
grant_catalog_privileges() {
    local token="$1"
    log_info "Granting CATALOG_MANAGE_CONTENT privilege to catalog role..."

    local response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${POLARIS_HOST}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles/${CATALOG_ROLE_NAME}/grants" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{
            \"type\": \"catalog\",
            \"privilege\": \"CATALOG_MANAGE_CONTENT\"
        }")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ] && [ "$http_code" != "204" ]; then
        log_error "Failed to grant catalog privileges (HTTP $http_code)"
        return 1
    fi

    log_success "CATALOG_MANAGE_CONTENT privilege granted"
}

# Create namespaces
create_namespaces() {
    local token="$1"
    local namespaces=("data")

    for ns in "${namespaces[@]}"; do
        log_info "Creating namespace: ${ns}..."

        local response=$(curl -s -w "\n%{http_code}" -X POST \
            "${POLARIS_HOST}/api/catalog/v1/${CATALOG_NAME}/namespaces" \
            -H "Authorization: Bearer ${token}" \
            -H "Content-Type: application/json" \
            -d "{
                \"namespace\": [\"${ns}\"],
                \"properties\": {}
            }")

        local http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | head -n-1)

        if [ "$http_code" = "409" ]; then
            log_warn "Namespace '${ns}' already exists"
            continue
        fi

        if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
            log_warn "Failed to create namespace '${ns}' (HTTP $http_code) - this is non-critical"
            continue
        fi

        log_success "Namespace '${ns}' created"
    done
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "   Polaris Initialization Complete!"
    echo "=========================================="
    echo ""
    log_info "Catalog: ${CATALOG_NAME}"
    log_info "Principal: ${PRINCIPAL_NAME} (service account)"
    log_info "Principal Role: ${PRINCIPAL_ROLE_NAME}"
    log_info "Catalog Role: ${CATALOG_ROLE_NAME}"
    log_info "Privileges: CATALOG_MANAGE_CONTENT"
    log_info "Namespace: data (single namespace for all tables)"
    echo ""
    log_info "Credentials saved to: $(dirname "$0")/.credentials/dagster_user.txt"
    echo ""
    log_warn "NEXT STEPS:"
    echo "  1. Source the credentials file:"
    echo "     source $(dirname "$0")/.credentials/dagster_user.txt"
    echo ""
    echo "  2. Update orchestration-dagster/set_pyiceberg_env.sh with the new credentials"
    echo ""
    echo "  3. Restart Dagster:"
    echo "     cd orchestration-dagster"
    echo "     source set_pyiceberg_env.sh"
    echo "     uv run dagster dev"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "   Polaris Catalog Initialization"
    echo "=========================================="
    echo ""

    check_prerequisites
    test_connectivity

    # Get bootstrap token
    log_info "Authenticating with bootstrap credentials..."
    BOOTSTRAP_TOKEN=$(get_token "$BOOTSTRAP_CLIENT_ID" "$BOOTSTRAP_CLIENT_SECRET")
    if [ $? -ne 0 ]; then
        log_error "Failed to authenticate with bootstrap credentials"
        exit 1
    fi
    log_success "Authenticated with bootstrap credentials"

    # Setup catalog and RBAC
    setup_catalog "$BOOTSTRAP_TOKEN"
    create_principal "$BOOTSTRAP_TOKEN"
    create_principal_role "$BOOTSTRAP_TOKEN"
    grant_principal_role "$BOOTSTRAP_TOKEN"
    create_catalog_role "$BOOTSTRAP_TOKEN"
    grant_catalog_role "$BOOTSTRAP_TOKEN"
    grant_catalog_privileges "$BOOTSTRAP_TOKEN"

    # Create namespaces (non-critical, can fail if using dagster_user token before full setup)
    if [ -n "$DAGSTER_CLIENT_ID" ] && [ -n "$DAGSTER_CLIENT_SECRET" ]; then
        log_info "Authenticating with dagster_user credentials..."
        DAGSTER_TOKEN=$(get_token "$DAGSTER_CLIENT_ID" "$DAGSTER_CLIENT_SECRET")
        if [ $? -eq 0 ]; then
            create_namespaces "$DAGSTER_TOKEN"
        else
            log_warn "Could not authenticate with dagster_user - skipping namespace creation"
            log_warn "You can create namespaces manually later via Trino or the API"
        fi
    else
        log_warn "Dagster user credentials not available - skipping namespace creation"
    fi

    print_summary
}

# Run main
main

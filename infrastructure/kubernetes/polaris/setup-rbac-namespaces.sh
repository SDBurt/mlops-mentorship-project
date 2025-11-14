#!/bin/bash
# Polaris RBAC and Namespace Setup Script
#
# This script sets up RBAC (roles, privileges) and creates namespaces in Polaris.
# It assumes the catalog and principal already exist (created by init-polaris.sh).
#
# Prerequisites:
# - Polaris deployed and accessible (kubectl port-forward to localhost:8181)
# - Catalog and principal already created (run init-polaris.sh first)
# - Bootstrap credentials provided via environment variables or command-line flags
# - curl and jq installed
#
# Usage:
#   # Using environment variables (recommended):
#   export POLARIS_BOOTSTRAP_CLIENT_ID="polaris_admin"
#   export POLARIS_BOOTSTRAP_CLIENT_SECRET="your_secret"  # pragma: allowlist secret
#   ./setup-rbac-namespaces.sh [--host http://localhost:8181]
#
#   # Using command-line flags:
#   ./setup-rbac-namespaces.sh --host http://localhost:8181 \
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
    exit 1
fi

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

    # Correct API endpoint: PUT /api/management/v1/principal-roles/{principalRole}/catalog-roles/{catalog}
    local response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${POLARIS_HOST}/api/management/v1/principal-roles/${PRINCIPAL_ROLE_NAME}/catalog-roles/${CATALOG_NAME}" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"catalogRole\": {\"name\": \"${CATALOG_ROLE_NAME}\"}}")

    local http_code=$(echo "$response" | tail -n1)
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
    # Single namespace for all tables (as per architecture)
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

# Get dagster_user credentials from saved file
get_dagster_credentials() {
    local cred_file="$(dirname "$0")/.credentials/dagster_user.txt"
    if [ -f "$cred_file" ]; then
        source "$cred_file"
        if [ -n "$POLARIS_CLIENT_ID" ] && [ -n "$POLARIS_CLIENT_SECRET" ]; then
            export DAGSTER_CLIENT_ID="$POLARIS_CLIENT_ID"
            export DAGSTER_CLIENT_SECRET="$POLARIS_CLIENT_SECRET"
            return 0
        fi
    fi
    return 1
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "   Polaris RBAC & Namespace Setup Complete!"
    echo "=========================================="
    echo ""
    log_info "Catalog: ${CATALOG_NAME}"
    log_info "Principal: ${PRINCIPAL_NAME}"
    log_info "Principal Role: ${PRINCIPAL_ROLE_NAME}"
    log_info "Catalog Role: ${CATALOG_ROLE_NAME}"
    log_info "Privileges: CATALOG_MANAGE_CONTENT"
    log_info "Namespace: data"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "   Polaris RBAC & Namespace Setup"
    echo "=========================================="
    echo ""

    # Get bootstrap token
    log_info "Authenticating with bootstrap credentials..."
    BOOTSTRAP_TOKEN=$(get_token "$BOOTSTRAP_CLIENT_ID" "$BOOTSTRAP_CLIENT_SECRET")
    if [ $? -ne 0 ]; then
        log_error "Failed to authenticate with bootstrap credentials"
        exit 1
    fi
    log_success "Authenticated with bootstrap credentials"

    # Setup RBAC
    log_info "Setting up RBAC..."
    create_principal_role "$BOOTSTRAP_TOKEN"
    grant_principal_role "$BOOTSTRAP_TOKEN"
    create_catalog_role "$BOOTSTRAP_TOKEN"
    grant_catalog_role "$BOOTSTRAP_TOKEN"
    grant_catalog_privileges "$BOOTSTRAP_TOKEN"

    # Create namespaces using dagster_user credentials (if available)
    if get_dagster_credentials; then
        log_info "Authenticating with dagster_user credentials..."
        DAGSTER_TOKEN=$(get_token "$DAGSTER_CLIENT_ID" "$DAGSTER_CLIENT_SECRET")
        if [ $? -eq 0 ]; then
            create_namespaces "$DAGSTER_TOKEN"
        else
            log_warn "Could not authenticate with dagster_user - creating namespaces with bootstrap token"
            create_namespaces "$BOOTSTRAP_TOKEN"
        fi
    else
        log_warn "Dagster user credentials not found - creating namespaces with bootstrap token"
        log_warn "Run 'make init-polaris' first to generate dagster_user credentials"
        create_namespaces "$BOOTSTRAP_TOKEN"
    fi

    print_summary
}

# Run main
main

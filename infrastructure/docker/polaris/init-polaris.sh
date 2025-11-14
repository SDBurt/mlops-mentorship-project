#!/usr/bin/env bash
set -euo pipefail

# Streamlined Polaris initialization script
# Based on: https://medium.com/@gilles.philippart/build-a-data-lakehouse-with-apache-iceberg-polaris-trino-minio-349c534ecd98

POLARIS_URL="${POLARIS_URL:-http://localhost:8181}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-admin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-password}"
MINIO_REGION="${MINIO_REGION:-dummy-region}"
CATALOG_NAME="${CATALOG_NAME:-polariscatalog}"
CLIENT_ID="${CLIENT_ID:-root}"
CLIENT_SECRET="${CLIENT_SECRET:-secret}"
SCOPE="${SCOPE:-PRINCIPAL_ROLE:ALL}"

echo "🚀 Initializing Polaris at ${POLARIS_URL}..."

# Wait for Polaris to be ready (check OAuth endpoint instead of healthcheck)
echo "Waiting for Polaris to be ready..."
for i in {1..30}; do
    if curl -sf "${POLARIS_URL}/api/catalog/v1/oauth/tokens" -X POST -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}&scope=${SCOPE}" >/dev/null 2>&1; then
        echo "✓ Polaris is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Polaris did not become ready after 60 seconds"
        exit 1
    fi
    echo "  ...waiting... ($i/30)"
    sleep 2
done

# Get access token
echo "Requesting OAuth2 access token..."
TOKEN_RESPONSE="$(curl -s -X POST \
  "${POLARIS_URL}/api/catalog/v1/oauth/tokens" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}&scope=${SCOPE}")"

if command -v jq >/dev/null 2>&1; then
  ACCESS_TOKEN="$(jq -r '.access_token' <<<"${TOKEN_RESPONSE}")"
else
  # Fallback parsing if jq is not available
  ACCESS_TOKEN="$(sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p' <<<"${TOKEN_RESPONSE}")"
fi

if [[ -z "${ACCESS_TOKEN:-}" ]] || [[ "${ACCESS_TOKEN}" == "null" ]]; then
    echo "❌ ERROR: Failed to obtain access token. Response:"
    echo "${TOKEN_RESPONSE}"
    exit 1
fi
echo "✓ Access token acquired"

# Check if catalog already exists
echo "Checking if catalog '${CATALOG_NAME}' exists..."
EXISTING_CATALOGS="$(curl -s -X GET \
  "${POLARIS_URL}/api/management/v1/catalogs" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")"

if echo "${EXISTING_CATALOGS}" | grep -q "\"name\":\"${CATALOG_NAME}\""; then
    echo "✓ Catalog '${CATALOG_NAME}' already exists"
else
    echo "Creating catalog '${CATALOG_NAME}' ..."
    CREATE_RESPONSE="$(curl -s -i -X POST \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "${POLARIS_URL}/api/management/v1/catalogs" \
      --json "{
        \"name\": \"${CATALOG_NAME}\",
        \"type\": \"INTERNAL\",
        \"properties\": {
          \"default-base-location\": \"s3://warehouse\",
          \"s3.endpoint\": \"${MINIO_ENDPOINT}\",
          \"s3.path-style-access\": \"true\",
          \"s3.access-key-id\": \"${MINIO_ACCESS_KEY}\",
          \"s3.secret-access-key\": \"${MINIO_SECRET_KEY}\",
          \"s3.region\": \"${MINIO_REGION}\"
        },
        \"storageConfigInfo\": {
          \"roleArn\": \"arn:aws:iam::000000000000:role/minio-polaris-role\",
          \"storageType\": \"S3\",
          \"allowedLocations\": [ \"s3://warehouse/*\" ]
        }
      }")"

    if echo "${CREATE_RESPONSE}" | grep -q "201\|200"; then
        echo "✓ Catalog '${CATALOG_NAME}' created"
    else
        echo "⚠ Warning: Catalog creation response:"
        echo "${CREATE_RESPONSE}" | head -5
    fi
fi

# Set up permissions (idempotent - safe to run multiple times)
echo "Setting up permissions..."

# Create catalog_admin role
echo "Creating catalog_admin role..."
curl -s -X PUT \
  "${POLARIS_URL}/api/management/v1/catalogs/${CATALOG_NAME}/catalog-roles/catalog_admin/grants" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  --json '{"grant":{"type":"catalog","privilege":"CATALOG_MANAGE_CONTENT"}}' >/dev/null
echo "✓ catalog_admin role configured"

# Create data_engineer principal role (ignore if already exists)
echo "Creating data_engineer principal role..."
curl -s -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${POLARIS_URL}/api/management/v1/principal-roles" \
  --json '{"principalRole":{"name":"data_engineer"}}' >/dev/null 2>&1 || true
echo "✓ data_engineer role configured"

# Connect data_engineer to catalog_admin
echo "Linking data_engineer to catalog_admin..."
curl -s -X PUT \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${POLARIS_URL}/api/management/v1/principal-roles/data_engineer/catalog-roles/${CATALOG_NAME}" \
  --json '{"catalogRole":{"name":"catalog_admin"}}' >/dev/null
echo "✓ Roles linked"

# Grant root the data_engineer role
echo "Granting root the data_engineer role..."
curl -s -X PUT \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${POLARIS_URL}/api/management/v1/principals/root/principal-roles" \
  --json '{"principalRole":{"name":"data_engineer"}}' >/dev/null
echo "✓ root granted data_engineer role"

# Create 'data' namespace (idempotent)
echo "Creating 'data' namespace..."
NAMESPACE_RESPONSE="$(curl -s -w "\n%{http_code}" -X POST \
  "${POLARIS_URL}/api/catalog/v1/${CATALOG_NAME}/namespaces" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"namespace":["data"]}')"

HTTP_CODE=$(echo "${NAMESPACE_RESPONSE}" | tail -n1)
if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "201" ]; then
    echo "✓ Namespace 'data' created"
elif [ "${HTTP_CODE}" = "409" ]; then
    echo "✓ Namespace 'data' already exists"
else
    echo "⚠ Warning: Namespace creation returned HTTP ${HTTP_CODE}"
fi

echo ""
echo "✅ Polaris initialization complete!"
echo ""
echo "Catalog: ${CATALOG_NAME}"
echo "Namespace: data"
echo "You can now use Dagster assets to create tables in the 'data' namespace."

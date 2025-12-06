#!/bin/bash
# Superset initialization script
# Runs database migrations and creates admin user

set -e

echo "==> Starting Superset initialization..."

# Wait for database to be ready
echo "==> Waiting for database..."
sleep 5

# Initialize the database (create tables)
echo "==> Running database migrations..."
superset db upgrade

# Initialize Superset (create default roles)
echo "==> Initializing Superset..."
superset init

# Create admin user if it doesn't exist
echo "==> Creating admin user..."
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
    --firstname Admin \
    --lastname User \
    --email admin@superset.local \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || true

echo "==> Superset initialization complete!"
echo ""
echo "NOTE: Add Trino database connection manually:"
echo "  1. Login to Superset at http://localhost:8089"
echo "  2. Go to Settings > Database Connections"
echo "  3. Click '+ Database'"
echo "  4. Select 'Trino' and use this SQLAlchemy URI:"
echo "     trino://superset@trino:8080/polariscatalog/data"

-- Step 1: Create Kafka catalog
CREATE CATALOG kafka_catalog WITH ('type'='generic_in_memory');
CREATE DATABASE IF NOT EXISTS kafka_catalog.payments_db;

-- Step 2: Create Polaris catalog
CREATE CATALOG polaris_catalog WITH (
    'type'='iceberg',
    'catalog-type'='rest',
    'uri'='http://polaris:8181/api/catalog',
    'warehouse'='polariscatalog',
    'oauth2-server-uri'='http://polaris:8181/api/catalog/v1/oauth/tokens',
    'credential'='${POLARIS_USER}:${POLARIS_PASSWORD}',
    'scope'='PRINCIPAL_ROLE:ALL'
);

CREATE DATABASE IF NOT EXISTS polaris_catalog.payments_db;

-- Step 3: Enable checkpointing (required for Iceberg sinks)
SET 'execution.checkpointing.interval' = '10s';

#!/usr/bin/env bash
set -euo pipefail

COMPOSE="-f infrastructure/docker/docker-compose.yml"

echo "Running Trino smoke test (requires services up and Polaris initialized)..."

docker compose ${COMPOSE} exec -T trino trino --server localhost:8080 --catalog iceberg <<'SQL'
CREATE SCHEMA IF NOT EXISTS db;
USE db;

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGINT,
  first_name VARCHAR,
  last_name VARCHAR,
  email VARCHAR
);

INSERT INTO customers (customer_id, first_name, last_name, email)
VALUES (101, 'Ada', 'Lovelace', 'ada@example.com')
ON CONFLICT DO NOTHING;

SELECT * FROM customers LIMIT 10;
SQL

echo "Smoke test complete."

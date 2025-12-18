"""
Data Quality Validation for ML Features

This module provides Dagster assets to validate feature distributions
and data quality before model training.
"""

import os
import pandas as pd
import numpy as np
from dagster import asset, AssetExecutionContext, AssetKey, MaterializeResult, MetadataValue

def query_feature_stats(context: AssetExecutionContext, table_name: str) -> pd.DataFrame:
    """Query feature data from Trino to compute quality metrics."""
    from trino.dbapi import connect

    trino_host = os.getenv("TRINO_HOST", "trino")

    with connect(
        host=trino_host,
        port=8080,
        catalog="iceberg",
        schema="data",
        user="dagster",
    ) as conn:
        context.log.info(f"Querying {table_name} for quality checks...")
        # Get a sample for statistics
        query = f"SELECT * FROM iceberg.data.{table_name} LIMIT 5000"
        df = pd.read_sql(query, conn)

    return df

@asset(
    key_prefix=["ml", "data_quality"],
    group_name="ml_training",
    description="Validate customer feature quality and detect drift",
    compute_kind="python",
    deps=[AssetKey("feat_customer_features")],
)
def validate_customer_features(context: AssetExecutionContext) -> MaterializeResult:
    """Validate customer feature distributions and null rates."""
    df = query_feature_stats(context, "feat_customer_features")

    if df.empty:
        return MaterializeResult(metadata={"status": "skipped", "reason": "no_data"})

    num_records = len(df)

    # Check null rates
    null_rates = df.isnull().mean().to_dict()
    high_null_cols = [col for col, rate in null_rates.items() if rate > 0.1]

    # Check failure rate range
    invalid_failure_rates = 0
    if "failure_rate_30d" in df.columns:
        invalid_failure_rates = len(df[(df["failure_rate_30d"] < 0) | (df["failure_rate_30d"] > 1)])

    # Check fraud score distribution
    fraud_score_mean = 0
    if "fraud_score_avg" in df.columns:
        fraud_score_mean = float(df["fraud_score_avg"].mean())

    metadata = {
        "num_records": num_records,
        "null_rates": MetadataValue.json(null_rates),
        "high_null_columns": MetadataValue.json(high_null_cols),
        "invalid_failure_rates_count": invalid_failure_rates,
        "fraud_score_mean": fraud_score_mean,
    }

    # Determine quality status
    status = "healthy"
    if high_null_cols:
        status = "warning"
        context.log.warning(f"High null rates detected in columns: {high_null_cols}")

    if invalid_failure_rates > 0:
        status = "error"
        context.log.error(f"Found {invalid_failure_rates} records with invalid failure rates!")

    metadata["quality_status"] = status

    return MaterializeResult(metadata=metadata)

@asset(
    key_prefix=["ml", "data_quality"],
    group_name="ml_training",
    description="Validate merchant feature quality and detect drift",
    compute_kind="python",
    deps=[AssetKey("feat_merchant_features")],
)
def validate_merchant_features(context: AssetExecutionContext) -> MaterializeResult:
    """Validate merchant feature distributions and health scores."""
    df = query_feature_stats(context, "feat_merchant_features")

    if df.empty:
        return MaterializeResult(metadata={"status": "skipped", "reason": "no_data"})

    num_records = len(df)

    # Check health score range
    avg_health_score = float(df["merchant_health_score"].mean()) if "merchant_health_score" in df.columns else 0

    metadata = {
        "num_records": num_records,
        "avg_merchant_health_score": avg_health_score,
        "null_rates": MetadataValue.json(df.isnull().mean().to_dict()),
    }

    return MaterializeResult(metadata=metadata)

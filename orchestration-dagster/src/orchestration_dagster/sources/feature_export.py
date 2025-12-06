"""
Feature Export Assets for Feast Feature Store

This module exports DBT-computed features to parquet files in a shared volume
that Feast can use as data sources for materialization to Redis.

Flow:
    DBT Feature Tables (Iceberg) -> Trino Query -> Parquet Export -> Shared Volume
                                                                          |
                                                                          v
                                                                    Feast Server
                                                                          |
                                                                          v
                                                                    Redis (Online Store)
"""

from dagster import asset, AssetExecutionContext, Config
import pandas as pd
import os


class FeatureExportConfig(Config):
    """Configuration for feature export."""
    # Use shared volume path (mounted in both Dagster and Feast containers)
    feature_export_path: str = os.getenv("FEATURE_EXPORT_PATH", "/app/features")


@asset(
    key_prefix=["mlops", "features"],
    group_name="feature_export",
    description="Export customer features from DBT to parquet for Feast",
    compute_kind="python",
)
def customer_features_parquet(
    context: AssetExecutionContext,
    config: FeatureExportConfig,
) -> dict:
    """
    Export customer features from DBT intermediate tables to parquet.

    Queries the feat_customer_features table via Trino and writes to a shared
    volume as a parquet file that Feast can read.
    """
    from trino.dbapi import connect

    # Query features from Trino
    trino_host = os.getenv("TRINO_HOST", "trino")
    context.log.info(f"Connecting to Trino at {trino_host}:8080")

    with connect(
        host=trino_host,
        port=8080,
        catalog="iceberg",
        schema="data",
        user="dagster",
    ) as conn:
        # Check if table exists first
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW TABLES LIKE 'feat_customer_features'")
            tables = cursor.fetchall()
            if not tables:
                context.log.warning("feat_customer_features table not found. Run DBT first.")
                return {"status": "skipped", "reason": "table_not_found"}
        finally:
            cursor.close()

        # Query features
        query = """
        SELECT
            customer_id,
            feature_timestamp,
            total_payments_30d,
            total_payments_90d,
            total_amount_cents_30d,
            avg_amount_cents,
            failed_payments_30d,
            failure_rate_30d,
            consecutive_failures,
            recovered_payments_30d,
            recovery_rate_30d,
            days_since_first_payment,
            days_since_last_payment,
            days_since_last_failure,
            payment_method_count,
            has_backup_payment_method,
            fraud_score_avg,
            high_risk_payment_count,
            customer_tier,
            subscription_age_days,
            account_age_days
        FROM iceberg.data.feat_customer_features
        """
        context.log.info("Querying customer features from Trino...")
        df = pd.read_sql(query, conn)

    context.log.info(f"Retrieved {len(df)} customer feature rows")

    if df.empty:
        context.log.warning("No customer features found")
        return {"status": "empty", "rows": 0}

    # Ensure output directory exists
    os.makedirs(config.feature_export_path, exist_ok=True)

    output_path = os.path.join(config.feature_export_path, "customer_features.parquet")
    context.log.info(f"Writing to {output_path}")

    df.to_parquet(output_path, index=False)

    context.log.info(f"Exported {len(df)} customer features to {output_path}")

    return {
        "status": "success",
        "rows": len(df),
        "path": output_path,
    }


@asset(
    key_prefix=["mlops", "features"],
    group_name="feature_export",
    description="Export merchant features from DBT to parquet for Feast",
    compute_kind="python",
)
def merchant_features_parquet(
    context: AssetExecutionContext,
    config: FeatureExportConfig,
) -> dict:
    """
    Export merchant features from DBT intermediate tables to parquet.

    Queries the feat_merchant_features table via Trino and writes to a shared
    volume as a parquet file that Feast can read.
    """
    from trino.dbapi import connect

    # Query features from Trino
    trino_host = os.getenv("TRINO_HOST", "trino")
    context.log.info(f"Connecting to Trino at {trino_host}:8080")

    with connect(
        host=trino_host,
        port=8080,
        catalog="iceberg",
        schema="data",
        user="dagster",
    ) as conn:
        # Check if table exists first
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW TABLES LIKE 'feat_merchant_features'")
            tables = cursor.fetchall()
            if not tables:
                context.log.warning("feat_merchant_features table not found. Run DBT first.")
                return {"status": "skipped", "reason": "table_not_found"}
        finally:
            cursor.close()

        # Query features
        query = """
        SELECT
            merchant_id,
            feature_timestamp,
            total_transactions_30d,
            total_volume_cents_30d,
            unique_customers_30d,
            avg_transaction_amount,
            failure_rate_30d,
            dispute_rate_30d,
            refund_rate_30d,
            chargeback_rate_30d,
            fraud_rate_30d,
            high_risk_transaction_pct,
            merchant_health_score
        FROM iceberg.data.feat_merchant_features
        """
        context.log.info("Querying merchant features from Trino...")
        df = pd.read_sql(query, conn)

    context.log.info(f"Retrieved {len(df)} merchant feature rows")

    if df.empty:
        context.log.warning("No merchant features found")
        return {"status": "empty", "rows": 0}

    # Ensure output directory exists
    os.makedirs(config.feature_export_path, exist_ok=True)

    output_path = os.path.join(config.feature_export_path, "merchant_features.parquet")
    context.log.info(f"Writing to {output_path}")

    df.to_parquet(output_path, index=False)

    context.log.info(f"Exported {len(df)} merchant features to {output_path}")

    return {
        "status": "success",
        "rows": len(df),
        "path": output_path,
    }

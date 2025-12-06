"""Create sample parquet files for Feast schema validation."""

import os
import pandas as pd
from datetime import datetime, timezone

# Output path - configurable via environment variable
output_path = os.getenv("FEATURE_DATA_PATH", "/app/features")
os.makedirs(output_path, exist_ok=True)

# Create sample customer features
customer_data = {
    "customer_id": ["cust_001"],
    "feature_timestamp": [datetime.now(timezone.utc)],
    # Payment volume
    "total_payments_30d": [10],
    "total_payments_90d": [30],
    "total_amount_cents_30d": [50000],
    "avg_amount_cents": [5000.0],
    # Failure metrics
    "failed_payments_30d": [1],
    "failure_rate_30d": [0.1],
    "consecutive_failures": [0],
    # Recovery metrics
    "recovered_payments_30d": [1],
    "recovery_rate_30d": [1.0],
    # Engagement
    "days_since_first_payment": [365],
    "days_since_last_payment": [7],
    "days_since_last_failure": [30],
    # Payment methods
    "payment_method_count": [2],
    "has_backup_payment_method": [1],
    # Risk
    "fraud_score_avg": [0.05],
    "high_risk_payment_count": [0],
    # Profile
    "customer_tier": ["gold"],
    "subscription_age_days": [365],
    "account_age_days": [400],
}

customer_df = pd.DataFrame(customer_data)
customer_df.to_parquet(os.path.join(output_path, "customer_features.parquet"), index=False)
print(f"Created {output_path}/customer_features.parquet")

# Create sample merchant features
merchant_data = {
    "merchant_id": ["merch_001"],
    "feature_timestamp": [datetime.now(timezone.utc)],
    # Volume
    "total_transactions_30d": [1000],
    "total_volume_cents_30d": [5000000],
    "unique_customers_30d": [500],
    "avg_transaction_amount": [5000.0],
    # Quality
    "failure_rate_30d": [0.05],
    "dispute_rate_30d": [0.01],
    "refund_rate_30d": [0.02],
    "chargeback_rate_30d": [0.005],
    # Risk
    "fraud_rate_30d": [0.001],
    "high_risk_transaction_pct": [0.02],
    # Health
    "merchant_health_score": [0.95],
}

merchant_df = pd.DataFrame(merchant_data)
merchant_df.to_parquet(os.path.join(output_path, "merchant_features.parquet"), index=False)
print(f"Created {output_path}/merchant_features.parquet")

print("Sample data created successfully!")

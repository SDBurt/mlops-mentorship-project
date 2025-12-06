"""Merchant features for ML models.

These features capture merchant-level aggregations used for:
- Fraud detection (merchant risk profile)
- Transaction risk assessment
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float32, Int64, String

from ..entities import merchant

# Data source for merchant features
merchant_features_source = FileSource(
    name="merchant_features_source",
    path="/app/data/merchant_features.parquet",
    timestamp_field="feature_timestamp",
)

# Merchant payment metrics
merchant_payment_features = FeatureView(
    name="merchant_payment_features",
    entities=[merchant],
    ttl=timedelta(days=1),
    schema=[
        # Volume metrics
        Field(name="total_transactions_30d", dtype=Int64, description="Total transactions in last 30 days"),
        Field(name="total_volume_cents_30d", dtype=Int64, description="Total volume in cents (30d)"),
        Field(name="unique_customers_30d", dtype=Int64, description="Unique customers in last 30 days"),
        Field(name="avg_transaction_amount", dtype=Float32, description="Average transaction amount"),

        # Quality metrics
        Field(name="failure_rate_30d", dtype=Float32, description="Payment failure rate (30d)"),
        Field(name="dispute_rate_30d", dtype=Float32, description="Dispute rate (30d)"),
        Field(name="refund_rate_30d", dtype=Float32, description="Refund rate (30d)"),
        Field(name="chargeback_rate_30d", dtype=Float32, description="Chargeback rate (30d)"),

        # Risk metrics
        Field(name="fraud_rate_30d", dtype=Float32, description="Fraud rate (30d)"),
        Field(name="high_risk_transaction_pct", dtype=Float32, description="Percentage of high-risk transactions"),

        # Health score
        Field(name="merchant_health_score", dtype=Float32, description="Composite merchant health score (0-1)"),
    ],
    source=merchant_features_source,
    online=True,
    tags={"team": "mlops", "model": "fraud"},
)

# Merchant profile features
merchant_profile_features = FeatureView(
    name="merchant_profile_features",
    entities=[merchant],
    ttl=timedelta(days=7),
    schema=[
        Field(name="merchant_category", dtype=String, description="Merchant category code"),
        Field(name="merchant_country", dtype=String, description="Merchant country"),
        Field(name="days_since_onboarding", dtype=Int64, description="Days since merchant onboarding"),
        Field(name="is_high_risk_category", dtype=Int64, description="High-risk merchant category (0/1)"),
    ],
    source=merchant_features_source,
    online=True,
    tags={"team": "mlops", "model": "fraud"},
)

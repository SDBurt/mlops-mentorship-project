"""Feature definitions for payment ML models.

This file defines all entities, feature views, and feature services
for the payment feature store.
"""

from datetime import timedelta

from feast import Entity, FeatureService, FeatureView, Field, FileSource
from feast.types import Float32, Int64, String

# =============================================================================
# ENTITIES
# =============================================================================

customer = Entity(
    name="customer",
    join_keys=["customer_id"],
    description="Payment customer entity",
)

merchant = Entity(
    name="merchant",
    join_keys=["merchant_id"],
    description="Payment merchant entity",
)

# =============================================================================
# DATA SOURCES
# =============================================================================

customer_features_source = FileSource(
    name="customer_features_source",
    path="/app/data/customer_features.parquet",
    timestamp_field="feature_timestamp",
)

merchant_features_source = FileSource(
    name="merchant_features_source",
    path="/app/data/merchant_features.parquet",
    timestamp_field="feature_timestamp",
)

# =============================================================================
# FEATURE VIEWS
# =============================================================================

# Customer payment behavior features
customer_payment_features = FeatureView(
    name="customer_payment_features",
    entities=[customer],
    ttl=timedelta(days=1),
    schema=[
        # Payment volume metrics
        Field(name="total_payments_30d", dtype=Int64),
        Field(name="total_payments_90d", dtype=Int64),
        Field(name="total_amount_cents_30d", dtype=Int64),
        Field(name="avg_amount_cents", dtype=Float32),
        # Failure metrics
        Field(name="failed_payments_30d", dtype=Int64),
        Field(name="failure_rate_30d", dtype=Float32),
        Field(name="consecutive_failures", dtype=Int64),
        # Recovery metrics
        Field(name="recovered_payments_30d", dtype=Int64),
        Field(name="recovery_rate_30d", dtype=Float32),
        # Engagement signals
        Field(name="days_since_first_payment", dtype=Int64),
        Field(name="days_since_last_payment", dtype=Int64),
        Field(name="days_since_last_failure", dtype=Int64),
        # Payment method diversity
        Field(name="payment_method_count", dtype=Int64),
        Field(name="has_backup_payment_method", dtype=Int64),
        # Risk indicators
        Field(name="fraud_score_avg", dtype=Float32),
        Field(name="high_risk_payment_count", dtype=Int64),
    ],
    source=customer_features_source,
    online=True,
    tags={"team": "mlops", "model": "fraud,churn,retry"},
)

# Customer profile features
customer_profile_features = FeatureView(
    name="customer_profile_features",
    entities=[customer],
    ttl=timedelta(days=7),
    schema=[
        Field(name="customer_tier", dtype=String),
        Field(name="subscription_age_days", dtype=Int64),
        Field(name="account_age_days", dtype=Int64),
    ],
    source=customer_features_source,
    online=True,
    tags={"team": "mlops", "model": "churn"},
)

# Merchant payment metrics
merchant_payment_features = FeatureView(
    name="merchant_payment_features",
    entities=[merchant],
    ttl=timedelta(days=1),
    schema=[
        # Volume metrics
        Field(name="total_transactions_30d", dtype=Int64),
        Field(name="total_volume_cents_30d", dtype=Int64),
        Field(name="unique_customers_30d", dtype=Int64),
        Field(name="avg_transaction_amount", dtype=Float32),
        # Quality metrics
        Field(name="failure_rate_30d", dtype=Float32),
        Field(name="dispute_rate_30d", dtype=Float32),
        Field(name="refund_rate_30d", dtype=Float32),
        Field(name="chargeback_rate_30d", dtype=Float32),
        # Risk metrics
        Field(name="fraud_rate_30d", dtype=Float32),
        Field(name="high_risk_transaction_pct", dtype=Float32),
        # Health score
        Field(name="merchant_health_score", dtype=Float32),
    ],
    source=merchant_features_source,
    online=True,
    tags={"team": "mlops", "model": "fraud"},
)

# =============================================================================
# FEATURE SERVICES
# =============================================================================

# Feature service for fraud detection model
fraud_detection_service = FeatureService(
    name="fraud_detection",
    features=[
        customer_payment_features[[
            "total_payments_30d",
            "failure_rate_30d",
            "fraud_score_avg",
            "high_risk_payment_count",
            "days_since_first_payment",
        ]],
        merchant_payment_features[[
            "fraud_rate_30d",
            "high_risk_transaction_pct",
            "merchant_health_score",
        ]],
    ],
    description="Features for fraud detection model",
    tags={"model": "fraud", "version": "v1"},
)

# Feature service for churn prediction model
churn_prediction_service = FeatureService(
    name="churn_prediction",
    features=[
        customer_payment_features[[
            "total_payments_30d",
            "total_payments_90d",
            "failure_rate_30d",
            "consecutive_failures",
            "recovery_rate_30d",
            "days_since_first_payment",
            "days_since_last_payment",
            "days_since_last_failure",
            "payment_method_count",
            "has_backup_payment_method",
        ]],
        customer_profile_features[[
            "customer_tier",
            "subscription_age_days",
        ]],
    ],
    description="Features for churn prediction model",
    tags={"model": "churn", "version": "v1"},
)

# Feature service for retry optimization model
retry_optimization_service = FeatureService(
    name="retry_optimization",
    features=[
        customer_payment_features[[
            "failure_rate_30d",
            "consecutive_failures",
            "recovery_rate_30d",
        ]],
        merchant_payment_features[[
            "failure_rate_30d",
        ]],
    ],
    description="Features for retry optimization model",
    tags={"model": "retry", "version": "v1"},
)

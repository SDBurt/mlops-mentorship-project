"""Customer features for ML models.

These features are computed from payment history and used for:
- Fraud detection (customer risk profile)
- Churn prediction (customer engagement signals)
- Retry optimization (customer payment patterns)
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float32, Int64, String

from ..entities import customer

# Data source for customer features
# In production, this would be a data warehouse or feature computation pipeline
customer_features_source = FileSource(
    name="customer_features_source",
    path="/app/data/customer_features.parquet",
    timestamp_field="feature_timestamp",
)

# Customer payment behavior features
customer_payment_features = FeatureView(
    name="customer_payment_features",
    entities=[customer],
    ttl=timedelta(days=1),
    schema=[
        # Payment volume metrics
        Field(name="total_payments_30d", dtype=Int64, description="Total payments in last 30 days"),
        Field(name="total_payments_90d", dtype=Int64, description="Total payments in last 90 days"),
        Field(name="total_amount_cents_30d", dtype=Int64, description="Total amount in cents (30d)"),
        Field(name="avg_amount_cents", dtype=Float32, description="Average payment amount in cents"),

        # Failure metrics
        Field(name="failed_payments_30d", dtype=Int64, description="Failed payments in last 30 days"),
        Field(name="failure_rate_30d", dtype=Float32, description="Payment failure rate (30d)"),
        Field(name="consecutive_failures", dtype=Int64, description="Current consecutive failure count"),

        # Recovery metrics
        Field(name="recovered_payments_30d", dtype=Int64, description="Recovered payments in last 30 days"),
        Field(name="recovery_rate_30d", dtype=Float32, description="Recovery success rate (30d)"),

        # Engagement signals
        Field(name="days_since_first_payment", dtype=Int64, description="Customer tenure in days"),
        Field(name="days_since_last_payment", dtype=Int64, description="Days since last successful payment"),
        Field(name="days_since_last_failure", dtype=Int64, description="Days since last failed payment"),

        # Payment method diversity
        Field(name="payment_method_count", dtype=Int64, description="Number of payment methods used"),
        Field(name="has_backup_payment_method", dtype=Int64, description="Has backup payment method (0/1)"),

        # Risk indicators
        Field(name="fraud_score_avg", dtype=Float32, description="Average historical fraud score"),
        Field(name="high_risk_payment_count", dtype=Int64, description="Count of high-risk flagged payments"),
    ],
    source=customer_features_source,
    online=True,
    tags={"team": "mlops", "model": "fraud,churn,retry"},
)

# Customer demographic features (if available)
customer_profile_features = FeatureView(
    name="customer_profile_features",
    entities=[customer],
    ttl=timedelta(days=7),
    schema=[
        Field(name="customer_tier", dtype=String, description="Customer tier: platinum/gold/silver/bronze"),
        Field(name="subscription_age_days", dtype=Int64, description="Days since subscription start"),
        Field(name="account_age_days", dtype=Int64, description="Days since account creation"),
    ],
    source=customer_features_source,
    online=True,
    tags={"team": "mlops", "model": "churn"},
)

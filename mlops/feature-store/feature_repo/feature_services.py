"""Feature services bundle features for specific ML models.

Each feature service defines the set of features needed for a particular
model's inference. This ensures consistent feature retrieval.
"""

from feast import FeatureService

from .features.customer_features import customer_payment_features, customer_profile_features
from .features.merchant_features import merchant_payment_features, merchant_profile_features
from .features.transaction_features import transaction_derived_features

# Feature service for fraud detection model
fraud_detection_service = FeatureService(
    name="fraud_detection",
    features=[
        customer_payment_features[
            [
                "total_payments_30d",
                "failure_rate_30d",
                "fraud_score_avg",
                "high_risk_payment_count",
                "days_since_first_payment",
            ]
        ],
        merchant_payment_features[
            [
                "fraud_rate_30d",
                "high_risk_transaction_pct",
                "merchant_health_score",
            ]
        ],
        transaction_derived_features,
    ],
    description="Features for fraud detection model",
    tags={"model": "fraud", "version": "v1"},
)

# Feature service for churn prediction model
churn_prediction_service = FeatureService(
    name="churn_prediction",
    features=[
        customer_payment_features[
            [
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
            ]
        ],
        customer_profile_features[
            [
                "customer_tier",
                "subscription_age_days",
            ]
        ],
    ],
    description="Features for churn prediction model",
    tags={"model": "churn", "version": "v1"},
)

# Feature service for retry optimization model
retry_optimization_service = FeatureService(
    name="retry_optimization",
    features=[
        customer_payment_features[
            [
                "failure_rate_30d",
                "consecutive_failures",
                "recovery_rate_30d",
            ]
        ],
        merchant_payment_features[
            [
                "failure_rate_30d",
            ]
        ],
        transaction_derived_features,
    ],
    description="Features for retry optimization model",
    tags={"model": "retry", "version": "v1"},
)

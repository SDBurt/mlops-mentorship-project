"""Transaction features for ML models.

Real-time transaction features used at inference time for:
- Fraud detection (transaction risk signals)
- Retry optimization (failure context)
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource, RequestSource
from feast.on_demand_feature_view import on_demand_feature_view
from feast.types import Float32, Int64, String
import pandas as pd

from ..entities import transaction

# Request-time transaction data (passed at inference)
transaction_request_source = RequestSource(
    name="transaction_request",
    schema=[
        Field(name="amount_cents", dtype=Int64),
        Field(name="currency", dtype=String),
        Field(name="payment_method_type", dtype=String),
        Field(name="card_brand", dtype=String),
        Field(name="is_guest_checkout", dtype=Int64),
        Field(name="failure_code", dtype=String),
    ],
)


@on_demand_feature_view(
    sources=[transaction_request_source],
    schema=[
        Field(name="amount_bucket", dtype=String, description="Amount range bucket"),
        Field(name="is_high_amount", dtype=Int64, description="Transaction > $500"),
        Field(name="is_very_high_amount", dtype=Int64, description="Transaction > $1000"),
        Field(name="is_card_payment", dtype=Int64, description="Payment method is card"),
        Field(name="is_known_card_brand", dtype=Int64, description="Card brand is known"),
        Field(name="is_retryable_failure", dtype=Int64, description="Failure code is retryable"),
    ],
    mode="pandas",
)
def transaction_derived_features(inputs: pd.DataFrame) -> pd.DataFrame:
    """Compute derived features from transaction request data."""
    df = pd.DataFrame()

    # Amount buckets
    amount = inputs["amount_cents"]
    df["amount_bucket"] = pd.cut(
        amount,
        bins=[0, 1000, 5000, 10000, 50000, 100000, float("inf")],
        labels=["micro", "small", "medium", "large", "very_large", "huge"],
    ).astype(str)
    df["is_high_amount"] = (amount > 50000).astype(int)
    df["is_very_high_amount"] = (amount > 100000).astype(int)

    # Payment method features
    df["is_card_payment"] = inputs["payment_method_type"].isin(
        ["card", "credit_card", "debit_card"]
    ).astype(int)

    # Card brand features
    known_brands = {"visa", "mastercard", "amex", "discover", "diners", "jcb"}
    df["is_known_card_brand"] = inputs["card_brand"].str.lower().isin(known_brands).astype(int)

    # Retryable failure codes
    retryable_codes = {
        "processing_error",
        "issuer_not_available",
        "try_again_later",
        "network_error",
        "timeout",
    }
    df["is_retryable_failure"] = inputs["failure_code"].str.lower().isin(retryable_codes).astype(int)

    return df

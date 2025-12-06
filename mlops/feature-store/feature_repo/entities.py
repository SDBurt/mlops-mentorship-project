"""Entity definitions for the payment feature store."""

from feast import Entity

# Customer entity - primary key for customer-level features
customer = Entity(
    name="customer",
    join_keys=["customer_id"],
    description="Payment customer entity",
)

# Merchant entity - primary key for merchant-level features
merchant = Entity(
    name="merchant",
    join_keys=["merchant_id"],
    description="Payment merchant entity",
)

# Transaction entity - for transaction-level features
transaction = Entity(
    name="transaction",
    join_keys=["event_id"],
    description="Individual payment transaction",
)

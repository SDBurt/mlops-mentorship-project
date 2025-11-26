# temporal/activities/charge_payment.py
from temporalio import activity
from dataclasses import dataclass
import random

class PaymentDeclinedError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Payment declined: {code}")

@dataclass
class ChargeResult:
    status: str
    charge_id: str
    amount_charged: int

@activity.defn
async def charge_payment(payment_data: dict) -> ChargeResult:
    """
    Simulates payment processing with realistic failure rates.

    Works with normalized payment schema (amount_cents, provider_payment_id)
    and falls back to legacy fields (amount, transaction_id) for compatibility.
    """
    # Get payment identifier (works with normalized and legacy schemas)
    payment_id = payment_data.get(
        'provider_payment_id',
        payment_data.get('id', payment_data.get('transaction_id', 'unknown'))
    )
    provider = payment_data.get('provider', 'unknown')
    activity.logger.info(f"Processing charge for {payment_id} [{provider}]")

    # Simulate 15% decline rate (realistic for subscription renewals)
    if random.random() < 0.15:
        failure_codes = [
            "card_declined",
            "insufficient_funds",
            "expired_card",
            "incorrect_cvc",
            "processing_error"
        ]
        raise PaymentDeclinedError(random.choice(failure_codes))

    # Support both normalized (amount_cents) and legacy (amount) fields
    amount = payment_data.get("amount_cents", payment_data.get("amount", 0))

    return ChargeResult(
        status="succeeded",
        charge_id=f"ch_{random.randint(1000000, 9999999)}",
        amount_charged=amount
    )

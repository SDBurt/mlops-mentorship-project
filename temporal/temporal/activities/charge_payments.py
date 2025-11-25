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
    """
    activity.logger.info(f"Processing charge for {payment_data.get('transaction_id')}")

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

    return ChargeResult(
        status="succeeded",
        charge_id=f"ch_{random.randint(1000000, 9999999)}",
        amount_charged=payment_data["amount"]
    )

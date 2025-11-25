# temporal/payment_generator.py
import asyncio
import random
from datetime import datetime
from temporalio.client import Client

from temporal.workflows.payment_processing import PaymentProcessingWorkflow

async def generate_payments(rate_per_second: float = 2.0):
    """
    Generates payment workflow instances.
    This replaces JR for payment initiation - events flow through
    Temporal before reaching Kafka.
    """
    client = await Client.connect("localhost:7233")

    payment_id = 0

    while True:
        payment_id += 1

        payment_request = {
            "transaction_id": f"TXN_{payment_id:08d}",
            "user_id": f"USER_{random.randint(1, 3000)}",
            "customer_id": f"cus_{random.randint(1, 10000)}",
            "amount": random.randint(100, 50000),  # cents
            "currency": random.choice(["usd", "cad", "gbp", "eur", "jpy"]),
            "payment_method": "card",
            "merchant": random.choice([
                "Netflix", "Spotify", "Adobe", "Microsoft", "Dropbox"
            ]),
            "transaction_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "metadata": {
                "subscription_id": f"sub_{random.randint(1, 50000)}",
                "provider": random.choice(["stripe", "braintree", "adyen"])
            }
        }

        # Start workflow (non-blocking, durable)
        await client.start_workflow(
            PaymentProcessingWorkflow.run,
            payment_request,
            id=f"payment-{payment_request['transaction_id']}",
            task_queue="payment-processing",
        )

        print(f"Started workflow: payment-{payment_request['transaction_id']}")
        await asyncio.sleep(1 / rate_per_second)

if __name__ == "__main__":
    asyncio.run(generate_payments())

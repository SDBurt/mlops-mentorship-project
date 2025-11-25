# temporal/worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from temporal.workflows.payment_processing import PaymentProcessingWorkflow
from temporal.activities import (
    check_fraud, charge_payment, get_retry_strategy, emit_to_kafka
)

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="payment-processing",
        workflows=[PaymentProcessingWorkflow],
        activities=[
            check_fraud,
            charge_payment,
            get_retry_strategy,
            emit_to_kafka
        ],
    )

    print("Worker started, listening on task queue: payment-processing")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())

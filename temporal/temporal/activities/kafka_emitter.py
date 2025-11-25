# temporal/activities/kafka_emitter.py
from temporalio import activity
from aiokafka import AIOKafkaProducer
import json

@activity.defn
async def emit_to_kafka(topic: str, event: dict) -> None:
    """
    Emits completed payment event to Kafka for downstream processing.
    """
    activity.logger.info(f"Emitting to {topic}: {event.get('type')}")

    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",  # Use service DNS in k8s
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    await producer.start()
    try:
        await producer.send_and_wait(topic, event)
    finally:
        await producer.stop()

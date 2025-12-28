"""Braintree webhook router for FastAPI."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Form, Request

from payment_gateway.config import settings
from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.braintree.validator import parse_braintree_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


async def publish_to_kafka(
    kafka: KafkaProducerManager,
    topic: str,
    payload: bytes,
    event_id: str,
) -> None:
    """Background task to publish webhook to Kafka."""
    try:
        result = await kafka.send(
            topic=topic,
            value=payload,
            key=event_id.encode("utf-8"),
        )
        logger.info(
            "Published Braintree event %s to %s (partition=%d, offset=%d)",
            event_id,
            topic,
            result["partition"],
            result["offset"],
        )
    except Exception as e:
        logger.error("Failed to publish Braintree event %s to Kafka: %s", event_id, str(e))


async def send_to_dlq(
    kafka: KafkaProducerManager,
    bt_signature: str,
    bt_payload: str,
    error_type: str,
    error_message: str,
) -> None:
    """Background task to send invalid webhooks to DLQ."""
    try:
        await kafka.send_to_dlq(
            provider="braintree",
            raw_payload=f"bt_signature={bt_signature}&bt_payload={bt_payload}".encode("utf-8"),
            headers={},
            error_type=error_type,
            error_message=error_message,
        )
        logger.info("Sent invalid Braintree webhook to DLQ: %s - %s", error_type, error_message)
    except Exception as e:
        logger.error("Failed to send Braintree event to DLQ: %s", str(e))


@router.post("/")
async def receive_braintree_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    bt_signature: str = Form(...),
    bt_payload: str = Form(...),
) -> dict:
    """
    Receive and process Braintree webhook notifications.

    Braintree sends webhooks as form data with two fields:
    - bt_signature: Signature for verification
    - bt_payload: Base64-encoded notification payload

    This endpoint:
    1. Verifies the signature using Braintree SDK
    2. Parses the notification to extract event data
    3. Publishes valid events to Kafka
    4. Routes invalid payloads to the DLQ
    """
    # Get Kafka producer from app state
    kafka: KafkaProducerManager = request.app.state.kafka

    # Parse and verify the webhook
    try:
        notification_data = parse_braintree_webhook(
            bt_signature=bt_signature,
            bt_payload=bt_payload,
            merchant_id=settings.braintree_merchant_id,
            public_key=settings.braintree_public_key,
            private_key=settings.braintree_private_key,
        )
    except SignatureVerificationError as e:
        logger.warning("Braintree signature verification failed: %s", str(e))
        background_tasks.add_task(
            send_to_dlq, kafka, bt_signature, bt_payload, "invalid_signature", str(e)
        )
        return {
            "status": "rejected",
            "message": "Invalid signature",
        }

    # Extract event details
    kind = notification_data.get("kind", "unknown")
    timestamp = notification_data.get("timestamp")

    # Build event ID
    transaction = notification_data.get("transaction", {})
    transaction_id = transaction.get("id") if transaction else None
    event_id = f"{kind}_{transaction_id}" if transaction_id else f"{kind}_{timestamp}"

    # Add bt_payload for downstream processing reference
    notification_data["bt_payload"] = bt_payload

    # Serialize for Kafka
    kafka_payload = json.dumps(notification_data).encode("utf-8")

    # Publish to Kafka
    background_tasks.add_task(
        publish_to_kafka, kafka, settings.braintree_topic_notification, kafka_payload, event_id
    )

    logger.info("Accepted Braintree webhook: kind=%s, event_id=%s", kind, event_id)

    return {
        "status": "accepted",
        "event_id": event_id,
        "kind": kind,
        "kafka_topic": settings.braintree_topic_notification,
    }

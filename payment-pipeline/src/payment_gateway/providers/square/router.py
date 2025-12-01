"""Square webhook router for FastAPI."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Header, Request
from pydantic import ValidationError

from payment_gateway.config import settings
from payment_gateway.core.base_models import WebhookResult, WebhookStatus
from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.square.models import SquareWebhookEvent
from payment_gateway.providers.square.validator import verify_square_signature

logger = logging.getLogger(__name__)

router = APIRouter()


def get_topic_for_event(event_category: str) -> str:
    """Get the Kafka topic for a given event category."""
    topic_map = {
        "payment": settings.square_topic_payment,
        "refund": settings.square_topic_refund,
    }
    return topic_map.get(event_category, f"{settings.kafka_topic_prefix}.square.{event_category}")


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
            "Published Square event %s to %s (partition=%d, offset=%d)",
            event_id,
            topic,
            result["partition"],
            result["offset"],
        )
    except Exception as e:
        logger.error("Failed to publish Square event %s to Kafka: %s", event_id, str(e))


async def send_to_dlq(
    kafka: KafkaProducerManager,
    raw_payload: bytes,
    headers: dict[str, str],
    error_type: str,
    error_message: str,
) -> None:
    """Background task to send invalid webhooks to DLQ."""
    try:
        await kafka.send_to_dlq(
            provider="square",
            raw_payload=raw_payload,
            headers=headers,
            error_type=error_type,
            error_message=error_message,
        )
        logger.info("Sent invalid Square webhook to DLQ: %s - %s", error_type, error_message)
    except Exception as e:
        logger.error("Failed to send Square event to DLQ: %s", str(e))


@router.post("/", response_model=WebhookResult)
async def receive_square_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    square_signature: str = Header(..., alias="x-square-hmacsha256-signature"),
) -> WebhookResult:
    """
    Receive and process Square webhook events.

    This endpoint:
    1. Verifies the webhook signature (HMAC-SHA256)
    2. Validates the payload structure using Pydantic
    3. Publishes valid events to the appropriate Kafka topic
    4. Routes invalid payloads to the DLQ

    Returns 200 quickly to acknowledge receipt (Square requirement).
    Actual Kafka publishing happens in a background task.
    """
    # Read raw body (needed for signature verification)
    raw_body = await request.body()

    # Extract headers for DLQ logging
    headers = {k.decode(): v.decode() for k, v in request.headers.raw}

    # Get Kafka producer from app state
    kafka: KafkaProducerManager = request.app.state.kafka

    # Step 1: Verify signature
    try:
        verify_square_signature(
            payload=raw_body,
            signature_header=square_signature,
            signature_key=settings.square_webhook_signature_key,
            notification_url=settings.square_notification_url,
        )
    except SignatureVerificationError as e:
        logger.warning("Square signature verification failed: %s", str(e))
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "invalid_signature", str(e)
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_SIGNATURE,
            message=str(e),
        )

    # Step 2: Parse and validate payload structure
    try:
        payload = json.loads(raw_body)
        event = SquareWebhookEvent.model_validate(payload)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON payload from Square: %s", str(e))
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "invalid_json", str(e)
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=f"Invalid JSON: {e}",
        )
    except ValidationError as e:
        error_details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        logger.warning("Square payload validation failed: %s", error_details)
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "validation_error", error_details
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=f"Validation error: {error_details}",
        )
    except Exception as e:
        logger.error("Unexpected error during Square validation: %s", str(e), exc_info=True)
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "validation_error", str(e)
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=str(e),
        )

    # Step 3: Queue Kafka publish (background task for fast response)
    topic = get_topic_for_event(event.event_category)
    background_tasks.add_task(publish_to_kafka, kafka, topic, raw_body, event.event_id)

    logger.info("Accepted Square webhook event %s (type=%s)", event.event_id, event.type)

    return WebhookResult(
        status=WebhookStatus.ACCEPTED,
        event_id=event.event_id,
        event_type=event.type,
        kafka_topic=topic,
    )

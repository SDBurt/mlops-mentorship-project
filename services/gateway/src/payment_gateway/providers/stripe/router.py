"""Stripe webhook router for FastAPI."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Header, Request
from pydantic import ValidationError

from payment_gateway.config import settings
from payment_gateway.core.base_models import WebhookResult, WebhookStatus
from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.stripe.models import StripeWebhookEventAdapter
from payment_gateway.providers.stripe.validator import verify_stripe_signature

logger = logging.getLogger(__name__)

router = APIRouter()


def get_topic_for_event(event_category: str) -> str:
    """Get the Kafka topic for a given event category."""
    topic_map = {
        "payment_intent": settings.stripe_topic_payment_intent,
        "charge": settings.stripe_topic_charge,
        "refund": settings.stripe_topic_refund,
    }
    return topic_map.get(event_category, f"{settings.kafka_topic_prefix}.stripe.{event_category}")


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
            "Published event %s to %s (partition=%d, offset=%d)",
            event_id,
            topic,
            result["partition"],
            result["offset"],
        )
    except Exception as e:
        logger.error("Failed to publish event %s to Kafka: %s", event_id, str(e))
        # In production, you might want to retry or send to a local buffer


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
            provider="stripe",
            raw_payload=raw_payload,
            headers=headers,
            error_type=error_type,
            error_message=error_message,
        )
        logger.info("Sent invalid webhook to DLQ: %s - %s", error_type, error_message)
    except Exception as e:
        logger.error("Failed to send to DLQ: %s", str(e))


@router.post("/", response_model=WebhookResult)
async def receive_stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> WebhookResult:
    """
    Receive and process Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature (HMAC-SHA256)
    2. Validates the payload structure using Pydantic
    3. Publishes valid events to the appropriate Kafka topic
    4. Routes invalid payloads to the DLQ

    Returns 200 quickly to acknowledge receipt (Stripe requirement).
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
        verify_stripe_signature(
            payload=raw_body,
            signature_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
            tolerance=settings.stripe_signature_tolerance,
        )
    except SignatureVerificationError as e:
        logger.warning("Signature verification failed: %s", str(e))
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
        event = StripeWebhookEventAdapter.validate_python(payload)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON payload: %s", str(e))
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "invalid_json", str(e)
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=f"Invalid JSON: {e}",
        )
    except ValidationError as e:
        # Log detailed Pydantic validation errors
        error_details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        logger.warning("Payload validation failed: %s", error_details)
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "validation_error", error_details
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=f"Validation error: {error_details}",
        )
    except Exception as e:
        logger.error("Unexpected error during validation: %s", str(e), exc_info=True)
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "validation_error", str(e)
        )
        return WebhookResult(
            status=WebhookStatus.INVALID_PAYLOAD,
            message=str(e),
        )

    # Step 3: Queue Kafka publish (background task for fast response)
    topic = get_topic_for_event(event.event_category)
    background_tasks.add_task(publish_to_kafka, kafka, topic, raw_body, event.id)

    logger.info("Accepted webhook event %s (type=%s)", event.id, event.type)

    return WebhookResult(
        status=WebhookStatus.ACCEPTED,
        event_id=event.id,
        event_type=event.type,
        kafka_topic=topic,
    )

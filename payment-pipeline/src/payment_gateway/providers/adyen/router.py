"""Adyen webhook router for FastAPI."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from pydantic import ValidationError

from payment_gateway.config import settings
from payment_gateway.core.exceptions import SignatureVerificationError
from payment_gateway.core.kafka_producer import KafkaProducerManager
from payment_gateway.providers.adyen.models import AdyenNotificationRequest
from payment_gateway.providers.adyen.validator import verify_adyen_hmac

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
            "Published Adyen event %s to %s (partition=%d, offset=%d)",
            event_id,
            topic,
            result["partition"],
            result["offset"],
        )
    except Exception as e:
        logger.error("Failed to publish Adyen event %s to Kafka: %s", event_id, str(e))


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
            provider="adyen",
            raw_payload=raw_payload,
            headers=headers,
            error_type=error_type,
            error_message=error_message,
        )
        logger.info("Sent invalid Adyen webhook to DLQ: %s - %s", error_type, error_message)
    except Exception as e:
        logger.error("Failed to send Adyen event to DLQ: %s", str(e))


@router.post("/")
async def receive_adyen_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Receive and process Adyen webhook notifications.

    This endpoint:
    1. Parses the notification request (may contain multiple items)
    2. Verifies HMAC signature for each notification item
    3. Publishes valid events to Kafka
    4. Routes invalid payloads to the DLQ

    IMPORTANT: Adyen expects "[accepted]" response to acknowledge receipt.
    Any other response will cause Adyen to retry the notification.
    """
    # Read raw body
    raw_body = await request.body()

    # Extract headers for DLQ logging
    headers = {k.decode(): v.decode() for k, v in request.headers.raw}

    # Get Kafka producer from app state
    kafka: KafkaProducerManager = request.app.state.kafka

    # Step 1: Parse and validate payload structure
    try:
        payload = json.loads(raw_body)
        notification_request = AdyenNotificationRequest.model_validate(payload)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON payload from Adyen: %s", str(e))
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "invalid_json", str(e)
        )
        # Still return [accepted] to prevent Adyen retries
        return Response(content="[accepted]", media_type="text/plain")
    except ValidationError as e:
        error_details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        logger.warning("Adyen payload validation failed: %s", error_details)
        background_tasks.add_task(
            send_to_dlq, kafka, raw_body, headers, "validation_error", error_details
        )
        return Response(content="[accepted]", media_type="text/plain")

    # Step 2: Process each notification item
    processed_count = 0
    failed_count = 0

    for item in notification_request.items:
        # Create a unique event ID from pspReference and eventCode
        event_id = f"{item.pspReference}_{item.eventCode}"

        # Verify HMAC signature for this item
        try:
            # Convert item to dict for signature verification
            item_dict = item.model_dump()
            verify_adyen_hmac(
                notification_item=item_dict,
                hmac_key=settings.adyen_hmac_key,
            )
        except SignatureVerificationError as e:
            logger.warning("Adyen HMAC verification failed for %s: %s", event_id, str(e))
            # Send individual item to DLQ
            item_payload = json.dumps({"item": item_dict, "live": notification_request.live}).encode()
            background_tasks.add_task(
                send_to_dlq, kafka, item_payload, headers, "invalid_signature", str(e)
            )
            failed_count += 1
            continue

        # Publish to Kafka
        # Create a payload with the individual item and live flag
        kafka_payload = json.dumps({
            "pspReference": item.pspReference,
            "eventCode": item.eventCode,
            "merchantAccountCode": item.merchantAccountCode,
            "merchantReference": item.merchantReference,
            "originalReference": item.originalReference,
            "amount": item.amount.model_dump() if item.amount else None,
            "success": item.success,
            "eventDate": item.eventDate,
            "paymentMethod": item.paymentMethod,
            "reason": item.reason,
            "operations": item.operations,
            "additionalData": item.additionalData,
            "live": notification_request.live,
        }).encode("utf-8")

        background_tasks.add_task(
            publish_to_kafka, kafka, settings.adyen_topic_notification, kafka_payload, event_id
        )
        processed_count += 1

    logger.info(
        "Processed Adyen notification: %d items published, %d failed",
        processed_count,
        failed_count,
    )

    # Adyen requires "[accepted]" response
    return Response(content="[accepted]", media_type="text/plain")

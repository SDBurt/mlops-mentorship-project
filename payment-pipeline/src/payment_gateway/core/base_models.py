"""Base models shared across all payment providers."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class WebhookStatus(str, Enum):
    """Status of webhook processing."""

    ACCEPTED = "accepted"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_PAYLOAD = "invalid_payload"
    PROCESSING_ERROR = "processing_error"


class WebhookResult(BaseModel):
    """Result returned from webhook endpoint."""

    status: WebhookStatus
    event_id: str | None = None
    event_type: str | None = None
    message: str | None = None
    kafka_topic: str | None = None


class DLQPayload(BaseModel):
    """Payload structure for dead letter queue entries."""

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    provider: str = Field(..., description="Payment provider name (stripe, square, etc.)")
    raw_payload: str = Field(..., description="Original raw payload as JSON string")
    raw_headers: dict[str, str] = Field(
        default_factory=dict, description="Original request headers"
    )
    error_type: str = Field(..., description="Type of error (invalid_signature, invalid_payload)")
    error_message: str = Field(..., description="Detailed error message")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when webhook was received",
    )
    retry_count: int = Field(default=0, description="Number of processing retry attempts")

    @field_serializer("received_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

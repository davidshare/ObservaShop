# src/interfaces/http/schemas.py
"""
Pydantic schemas for the notification service API.
Defines request/response models and validation rules.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class NotificationBase(BaseModel):
    """
    Base model for notification data.
    Shared attributes across all notification models.
    """

    user_id: UUID = Field(..., description="ID of the user who owns this notification")
    recipient: str = Field(..., description="Email or phone number of recipient")
    notification_type: str = Field(
        ..., description="Type of notification (email, sms)", pattern="^(email|sms)$"
    )
    subject: str = Field(
        ..., min_length=1, max_length=200, description="Notification subject"
    )
    content: str = Field(
        ..., min_length=1, max_length=5000, description="Notification content"
    )
    event_type: str = Field(
        ..., description="Type of event that triggered this notification"
    )

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "recipient": "user@example.com",
                "notification_type": "email",
                "subject": "Welcome to ObservaShop!",
                "content": "Thank you for registering with us.",
                "event_type": "user.created",
            }
        }


class NotificationCreate(BaseModel):
    """
    Schema for creating a new notification.
    Used in POST requests to create notifications manually.
    """

    user_id: UUID = Field(..., description="ID of the user who owns this notification")
    recipient: str = Field(..., description="Email or phone number of recipient")
    notification_type: str = Field(
        ..., description="Type of notification (email, sms)", pattern="^(email|sms)$"
    )
    subject: str = Field(
        ..., min_length=1, max_length=200, description="Notification subject"
    )
    content: str = Field(
        ..., min_length=1, max_length=5000, description="Notification content"
    )
    event_type: str = Field(
        ..., description="Type of event that triggered this notification"
    )

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, v: str, info) -> str:
        """Validate recipient based on notification type."""
        if "notification_type" in info.data:
            if info.data["notification_type"] == "email":
                if "@" not in v:
                    raise ValueError("Invalid email address")
            elif info.data["notification_type"] == "sms":
                if not v.startswith("+") or not v[1:].isdigit():
                    raise ValueError("Phone number must be in E.164 format")
        return v

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "recipient": "user@example.com",
                "notification_type": "email",
                "subject": "Welcome to ObservaShop!",
                "content": "Thank you for registering with us.",
                "event_type": "user.created",
            }
        }


class NotificationUpdate(BaseModel):
    """
    Schema for updating a notification.
    All fields are optional - only provided fields will be updated.
    """

    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    status: Optional[str] = Field(
        None, description="New status (pending, sent, failed, read)"
    )

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "NotificationUpdate":
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self

    class Config:
        extra = "forbid"


class NotificationResponse(BaseModel):
    """
    Schema for notification response.
    Includes all fields from NotificationBase plus metadata.
    """

    id: UUID = Field(..., description="Unique identifier for the notification")
    user_id: UUID = Field(..., description="ID of the user who owns this notification")
    recipient: str = Field(..., description="Email or phone number of recipient")
    notification_type: str = Field(..., description="Type of notification (email, sms)")
    subject: str = Field(..., description="Notification subject")
    content: str = Field(..., description="Notification content")
    status: str = Field(
        ...,
        description="Current status (pending, sent, failed, read)",
        pattern="^(pending|sent|failed|read)$",
    )
    event_type: str = Field(
        ..., description="Type of event that triggered this notification"
    )
    created_at: datetime = Field(..., description="When the notification was created")
    updated_at: Optional[datetime] = Field(
        None, description="When the notification was last updated"
    )
    sent_at: Optional[datetime] = Field(
        None, description="When the notification was sent"
    )

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "recipient": "user@example.com",
                "notification_type": "email",
                "subject": "Welcome to ObservaShop!",
                "content": "Thank you for registering with us.",
                "status": "sent",
                "event_type": "user.created",
                "created_at": "2025-08-19T10:00:00Z",
                "updated_at": "2025-08-19T10:01:00Z",
                "sent_at": "2025-08-19T10:01:00Z",
            }
        }


class Meta(BaseModel):
    """
    Metadata for paginated responses.
    """

    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Number of items skipped")
    pages: int = Field(..., description="Total number of pages")

    class Config:
        extra = "forbid"


class NotificationListResponse(BaseModel):
    """
    Schema for paginated list of notifications.
    """

    notifications: List[NotificationResponse] = Field(
        ..., description="List of notifications"
    )
    meta: Meta = Field(..., description="Pagination metadata")

    class Config:
        extra = "forbid"


class HealthResponse(BaseModel):
    """
    Schema for health check response.
    """

    status: str = Field(..., description="Service status (healthy, unhealthy)")
    service: str = Field(..., description="Service name")
    database: Optional[str] = Field(None, description="Database connection status")
    redis: Optional[str] = Field(None, description="Redis connection status")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of check")

    class Config:
        extra = "forbid"


class ErrorResponse(BaseModel):
    """
    Schema for error responses.
    Standardized error format across the API.
    """

    detail: str = Field(..., description="Error message")

    class Config:
        extra = "forbid"
        json_schema_extra = {"example": {"detail": "Notification not found"}}

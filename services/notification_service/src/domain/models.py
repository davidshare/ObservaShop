from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column
from sqlmodel import Column as SQLColumn
from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    """Notification database model class"""

    __tablename__ = "notifications"
    __table_args__ = {"schema": "notification"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        description="Unique identifier for the notification",
    )

    user_id: UUID = Field(
        index=True,
        nullable=False,
        description="Logical reference to auth.users.id (no real FK in multi-service setup)",
    )

    recipient: str = Field(
        max_length=255,
        nullable=False,
        description="Email address or phone number of the recipient",
    )

    notification_type: str = Field(
        max_length=20,
        nullable=False,
        description="Type of notification: email, push, etc.",
    )

    subject: Optional[str] = Field(
        max_length=255,
        nullable=True,
        description="Subject line for email notifications",
    )

    content: str = Field(
        max_length=1000,
        nullable=False,
        description="The message content",
    )

    status: str = Field(
        max_length=20,
        nullable=False,
        description="Status: pending, sent, failed, delivered, read",
    )

    event_type: str = Field(
        max_length=50,
        nullable=False,
        description="The event that triggered this notification, e.g., order.created, user.registered",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="When the notification was created",
    )

    sent_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="When the notification was successfully sent",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="When the notification was last updated",
    )

    is_read: bool = Field(
        default=False,
        nullable=False,
        description="Whether the user has read the notification",
    )

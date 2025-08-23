"""
Event schemas for ObservaShop notification service.
Defines Pydantic models for validating Kafka event structures.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """
    Base schema for Kafka events with common fields.
    All events inherit these fields for consistency.
    """

    event_id: str = Field(..., description="Unique event identifier")
    correlation_id: Optional[str] = Field(
        None, description="For tracing across services"
    )
    event_type: str = Field(..., description="Event type (e.g., user.created)")
    source: str = Field(..., description="Service that emitted the event")
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    version: str = Field("1.0", description="Schema version")

    class Config:
        extra = "allow"  # Allow additional fields from producers


class UserCreatedData(BaseModel):
    """Data schema for user.created event."""

    user_id: UUID
    email: str
    username: Optional[str] = None


class OrderCreatedData(BaseModel):
    """Data schema for order.created event."""

    user_id: UUID
    email: str
    order_id: str
    total: float


class PaymentFailedData(BaseModel):
    """Data schema for payment.failed event."""

    user_id: UUID
    email: str
    order_id: str
    reason: Optional[str] = "Unknown"


class ProductBackInStockData(BaseModel):
    """Data schema for product.back_in_stock event."""

    user_id: UUID
    email: str
    product_id: str
    product_name: str


class UserCreated(BaseEvent):
    """Schema for user.created event."""

    event_type: str = "user.created"
    data: UserCreatedData = Field(..., description="User creation data")


class OrderCreated(BaseEvent):
    """Schema for order.created event."""

    event_type: str = "order.created"
    data: OrderCreatedData = Field(..., description="Order creation data")


class PaymentFailed(BaseEvent):
    """Schema for payment.failed event."""

    event_type: str = "payment.failed"
    data: PaymentFailedData = Field(..., description="Payment failure data")


class ProductBackInStock(BaseEvent):
    """Schema for product.back_in_stock event."""

    event_type: str = "product.back_in_stock"
    data: ProductBackInStockData = Field(..., description="Product restock data")

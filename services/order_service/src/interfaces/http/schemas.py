from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    """
    Schema for creating an order item.
    Represents a product and quantity in an order.
    """

    product_id: UUID = Field(..., description="The UUID of the product")
    quantity: int = Field(
        ..., gt=0, description="Quantity of the product (must be > 0)"
    )


class OrderCreate(BaseModel):
    """
    Schema for creating a new order.
    Contains a list of items to be ordered.
    """

    items: List[OrderItemCreate] = Field(
        ..., min_items=1, description="List of items in the order"
    )


class OrderItemResponse(BaseModel):
    """
    Schema for returning order item data in API responses.
    Includes product details and pricing at time of order.
    """

    id: UUID
    product_id: UUID
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """
    Schema for returning order data in API responses.
    Includes metadata and list of items.
    """

    id: UUID
    user_id: UUID
    status: str
    total_amount: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True


class OrderUpdate(BaseModel):
    """
    Schema for updating an existing order.
    Currently only supports status updates.
    """

    status: str = Field(..., pattern="^(confirmed|shipped|delivered|cancelled)$")


class OrderListResponse(BaseModel):
    """
    Response model for returning a paginated list of orders.
    Includes the list of orders and metadata for pagination.
    """

    orders: List[OrderResponse]
    meta: dict

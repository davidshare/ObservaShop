# src/interfaces/http/schemas.py

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    """
    Schema for creating a new payment.
    """

    order_id: UUID = Field(..., description="The UUID of the order to pay for")
    amount: float = Field(..., gt=0, description="Payment amount (must be > 0)")
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Currency code (e.g., USD, EUR)",
    )
    payment_method: str = Field(
        ..., min_length=1, description="Payment method (e.g., stripe, paypal, mock)"
    )


class PaymentUpdate(BaseModel):
    """
    Schema for updating a payment.
    Currently only supports status updates.
    """

    status: str = Field(
        ...,
        pattern="^(pending|succeeded|failed|refunded)$",
        description="New payment status",
    )


class PaymentItemResponse(BaseModel):
    """
    Response model for a single payment item (if needed for future expansion).
    """

    id: UUID
    product_id: UUID
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    """
    Response model for returning a single payment.
    """

    id: UUID
    order_id: UUID
    amount: float
    currency: str
    status: str
    payment_method: str
    transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """
    Response model for returning a paginated list of payments.
    """

    payments: List[PaymentResponse]
    meta: Dict[str, Any]

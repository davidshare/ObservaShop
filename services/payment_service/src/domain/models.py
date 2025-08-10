from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class Payment(SQLModel, table=True):
    """
    Represents a payment record in the system.

    This model stores payment details for an order, including amount, status,
    payment method, and transaction ID from the external gateway.

    The `order_id` is a logical reference to the `order-service` Order ID.
    There is no foreign key constraint because it's a cross-service reference.

    Attributes:
        id: Unique identifier for the payment (UUID, primary key).
        order_id: Reference to the order this payment is for (UUID).
        amount: The monetary amount of the payment (NUMERIC(10,2)).
        currency: The currency code (e.g., USD, EUR). Defaults to "USD".
        status: The current status of the payment (e.g., pending, succeeded, failed, refunded).
        payment_method: The payment gateway used (e.g., stripe, paypal, mock).
        transaction_id: The transaction ID from the external payment gateway (optional).
        created_at: Timestamp when the payment was created (auto-set).
        updated_at: Timestamp when the payment was last updated (auto-updated).
        is_active: Whether the payment record is active (soft-delete flag).
    """

    __tablename__ = "payments"
    __table_args__ = {"schema": "payment"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        description="Unique identifier for the payment",
    )

    order_id: UUID = Field(
        index=True,
        nullable=False,
        description="Logical reference to order-service Order ID (no real DB FK)",
    )

    amount: Decimal = Field(
        sa_column=Column(
            pg.NUMERIC(10, 2),
            nullable=False,
        ),
        description="Payment amount",
    )

    currency: str = Field(
        default="USD",
        max_length=3,
        nullable=False,
        description="Currency code (e.g., USD, EUR)",
    )

    status: str = Field(
        default="pending",
        max_length=20,
        nullable=False,
        description="e.g., pending, succeeded, failed, refunded",
    )

    payment_method: str = Field(
        max_length=20,
        nullable=False,
        description="e.g., stripe, paypal, mock",
    )

    transaction_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Transaction ID from payment gateway",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            default=datetime.utcnow,
        ),
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
    )

    is_active: bool = Field(
        default=True,
        nullable=False,
        description="Whether the payment record is active",
    )

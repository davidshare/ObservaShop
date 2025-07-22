from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column


class Payment(SQLModel, table=True):
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

    status: str = Field(
        max_length=20,
        nullable=False,
        description="e.g., pending, succeeded, failed, refunded",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            default=datetime.utcnow,
        ),
    )

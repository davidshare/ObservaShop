from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column
from sqlmodel import Column as SQLColumn
from sqlmodel import Field, Relationship, SQLModel


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"
    __table_args__ = {"schema": "orders"}

    id: UUID = Field(
        sa_column=SQLColumn(
            pg.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            index=True,
            nullable=False,
        )
    )

    order_id: UUID = Field(
        foreign_key="orders.orders.id",
        index=True,
        nullable=False,
    )

    product_id: UUID = Field(
        index=True,
        nullable=False,
        description="Logical reference to product-service Product ID",
    )

    quantity: int = Field(ge=1, nullable=False)

    price: Decimal = Field(
        sa_column=Column(pg.NUMERIC(10, 2), nullable=False),
        description="Price at time of purchase",
    )

    order: Optional["Order"] = Relationship(back_populates="items")


class Order(SQLModel, table=True):
    __tablename__ = "orders"
    __table_args__ = {"schema": "orders"}

    id: UUID = Field(
        sa_column=SQLColumn(
            pg.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            index=True,
            nullable=False,
        )
    )

    user_id: UUID = Field(
        index=True, nullable=False, description="Logical reference to auth.users.id"
    )

    total_amount: Decimal = Field(
        sa_column=Column(pg.NUMERIC(10, 2), nullable=False),
        description="Total amount of the order",
    )

    status: str = Field(
        max_length=20,
        nullable=False,
        description="e.g., pending, confirmed, shipped, cancelled",
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

    items: List["OrderItem"] = Relationship(back_populates="order")


# Fix forward reference
OrderItem.order: Order = Relationship(back_populates="items")

from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = {"schema": "product"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        description="Unique identifier for the product",
    )

    name: str = Field(max_length=100, nullable=False, description="Product name")

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(pg.TEXT, nullable=True),
        description="Detailed description of the product",
    )

    price: Decimal = Field(
        sa_column=Column(
            pg.NUMERIC(10, 2),
            nullable=False,
        ),
        description="Unit price in USD or local currency",
    )

    stock: int = Field(nullable=False, description="Available quantity in inventory")

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
            onupdate=datetime.utcnow,  # Auto-update when row changes
        ),
    )

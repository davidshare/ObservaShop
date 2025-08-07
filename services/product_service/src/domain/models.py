from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel


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

    category_id: UUID = Field(
        foreign_key="product.categories.id",
        nullable=False,
        description="ID of the category this product belongs to.",
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
            onupdate=datetime.utcnow,  # Auto-update when row changes
        ),
    )

    category: "Category" = Relationship(
        back_populates="products",
        sa_relationship_kwargs={
            "primaryjoin": "Product.category_id == foreign(Category.id)"
        },
    )


class Category(SQLModel, table=True):
    """
    Represents a product category in a hierarchical structure.

    Categories are used to organize products (e.g., Electronics → Phones → Smartphones).
    Supports soft-delete via `is_active` flag.

    Schema: product.categories
    """

    __tablename__ = "categories"
    __table_args__ = {"schema": "product"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the category (UUID).",
    )
    name: str = Field(
        max_length=100,
        unique=True,
        nullable=False,
        description="Category name (e.g., 'Electronics'). Must be unique.",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        nullable=True,
        description="Optional description of the category.",
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        foreign_key="product.categories.id",
        nullable=True,
        description="ID of the parent category for hierarchical structure.",
    )
    is_active: bool = Field(
        default=True, description="Whether the category is active and visible."
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the category was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the category was last updated.",
    )

    # Relationships
    children: List["Category"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "remote_side": "Category.id",
            "cascade": "all, delete-orphan",
        },
    )
    parent: Optional["Category"] = Relationship(back_populates="children")
    products: List["Product"] = Relationship(
        back_populates="category",
        sa_relationship_kwargs={
            "primaryjoin": "Category.id == foreign(Product.category_id)"
        },
    )

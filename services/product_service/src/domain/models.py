from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


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
        default=True,
        description="Whether the category is active and visible.",
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
    children: List["Category"] = Relationship(back_populates="parent")
    parent: Optional["Category"] = Relationship(
        back_populates="children", sa_relationship_kwargs={"remote_side": "Category.id"}
    )
    products: List["Product"] = Relationship(
        back_populates="category",
    )


class Product(SQLModel, table=True):
    """
    Represents a product in the catalog.
    Linked to a Category for organization.
    """

    __tablename__ = "products"
    __table_args__ = {"schema": "product"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the product",
    )
    name: str = Field(
        max_length=100,
        nullable=False,
        description="Product name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        nullable=True,
        description="Detailed description of the product",
    )
    price: Decimal = Field(
        max_digits=10,
        decimal_places=2,
        nullable=False,
        description="Unit price in USD or local currency",
    )
    stock: int = Field(
        ge=0,
        nullable=False,
        description="Available quantity in inventory",
    )
    category_id: UUID = Field(
        foreign_key="product.categories.id",
        nullable=False,
        description="ID of the category this product belongs to.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the product was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the product was last updated.",
    )

    # Relationships
    category: "Category" = Relationship(
        back_populates="products",
    )

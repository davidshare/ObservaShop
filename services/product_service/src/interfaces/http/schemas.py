from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class CategoryBase(BaseModel):
    """
    Base schema for Category with common fields.
    Used as a parent for Create and Update schemas.
    """

    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None


class CategoryCreate(CategoryBase):
    """
    Schema for creating a new category.
    All fields are required unless specified as optional.
    """

    pass


class CategoryUpdate(BaseModel):
    """
    Schema for updating an existing category.
    All fields are optional — only provided fields are updated.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """
    Schema for returning category data in API responses.
    Includes metadata and nested relationships.
    """

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    parent: Optional["CategoryResponse"] = None
    children: List["CategoryResponse"] = []
    product_count: int = 0

    class Config:
        from_attributes = True


# Fix forward references
CategoryResponse.model_rebuild()

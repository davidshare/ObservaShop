from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    # parent: Optional["CategoryResponse"] = None
    children: List["CategoryResponse"] = []
    product_count: int = 0

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """
    Response model for returning a paginated list of categories.
    Includes the list of categories and metadata for pagination.
    """

    categories: List[CategoryResponse]
    meta: Dict[str, Any]


# Fix forward references
CategoryResponse.model_rebuild()


###### Product schemas ############
class ProductBase(BaseModel):
    """
    Base schema for Product with common fields.
    Used as a parent for Create and Update schemas.
    """

    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category_id: UUID


class ProductCreate(ProductBase):
    """
    Schema for creating a new product.
    All fields are required unless specified as optional.
    Performs validation:
    - name: stripped and min_length=1
    - price: > 0
    - stock: >= 0
    """

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: float = Field(..., gt=0, description="Must be greater than zero")
    stock: int = Field(..., ge=0, description="Must be zero or positive")
    category_id: UUID

    @classmethod
    @field_validator("name", "description", mode="before")
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class ProductUpdate(BaseModel):
    """
    Schema for updating an existing product.
    All fields are optional — only provided fields are updated.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: Optional[float] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    category_id: Optional[UUID] = None

    @classmethod
    @field_validator("name", "description", mode="before")
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class ProductResponse(ProductBase):
    """
    Schema for returning product data in API responses.
    Includes metadata and relationships.
    """

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """
    Response model for returning a paginated list of products.
    Includes the list of products and metadata for pagination.
    """

    products: List[ProductResponse]
    meta: dict

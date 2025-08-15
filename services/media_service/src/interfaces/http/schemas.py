from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

# === Enums and Types ===

# Allowed owner types for media
OwnerType = Literal["product", "user", "post", "category"]


# === Request Models ===


class MediaCreate(BaseModel):
    """
    Request model for uploading media.
    No fields — file is uploaded via multipart/form-data.
    All metadata is extracted from the file and context.
    """

    # Note: This is a placeholder. The file is passed separately in FastAPI.
    pass


class MediaUpdate(BaseModel):
    """
    Request model for updating media metadata.
    Currently, only soft-delete is supported via PATCH.
    """

    is_active: bool = Field(..., description="Set to false to delete media")


# === Response Models ===


class MediaResponse(BaseModel):
    """
    Response model for a single media item.
    Includes a presigned URL for secure access.
    """

    id: UUID = Field(..., description="Unique identifier for the media")
    owner_id: UUID = Field(
        ..., description="ID of the owning entity (e.g., product ID)"
    )
    owner_type: OwnerType = Field(..., description="Type of the owning entity")
    filename: str = Field(..., max_length=255, description="Original filename")
    media_type: str = Field(
        ..., max_length=20, description="Media category (e.g., image, video)"
    )
    file_type: str = Field(
        ..., max_length=100, description="MIME type (e.g., image/jpeg)"
    )
    file_size: int = Field(..., description="File size in bytes")
    url: str = Field(..., description="Presigned URL for accessing the media")
    created_at: datetime = Field(..., description="When the media was uploaded")

    class Config:
        from_attributes = True


class MediaListResponse(BaseModel):
    """
    Response model for listing media items with pagination.
    """

    media: List[MediaResponse] = Field(..., description="List of media items")
    meta: dict = Field(
        ...,
        description="Pagination and filtering metadata",
        example={"total": 100, "limit": 10, "offset": 0, "pages": 10},
    )


class MediaUploadResponse(BaseModel):
    """
    Response model for successful upload.
    Returns the created media with presigned URL.
    """

    media: MediaResponse = Field(..., description="The uploaded media")
    message: str = Field("Media uploaded successfully", description="Success message")

    class Config:
        from_attributes = True


# === Query Parameters Model ===


class MediaListQuery(BaseModel):
    """
    Model for query parameters in GET /media.
    Used for filtering, pagination, and sorting.
    """

    limit: int = Field(10, ge=1, le=100, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Number of items to skip")
    owner_type: Optional[OwnerType] = Field(None, description="Filter by owner type")
    owner_id: Optional[UUID] = Field(None, description="Filter by owner ID")
    sort: str = Field(
        "created_at:desc", description="Sort by field:direction (e.g., created_at:asc)"
    )

    @validator("sort")
    @classmethod
    def validate_sort(cls, v):
        allowed_fields = ["created_at", "filename", "file_size"]
        allowed_directions = ["asc", "desc"]
        try:
            field, direction = v.split(":")
            if field not in allowed_fields:
                raise ValueError(f"Invalid sort field: {field}")
            if direction not in allowed_directions:
                raise ValueError(f"Invalid sort direction: {direction}")
        except ValueError as e:
            raise ValueError("Sort must be in format 'field:direction'") from e
        return v

from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column


class Media(SQLModel, table=True):
    """
    Represents a media asset (image, video) stored in MinIO.
    Metadata is stored in the PostgreSQL `media` schema.
    The actual file is stored in MinIO with a generated storage key.
    """

    __tablename__ = "media"
    __table_args__ = {"schema": "media"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        description="Unique identifier for the media asset",
    )

    owner_id: UUID = Field(
        index=True,
        nullable=False,
        description="ID of the owning entity (e.g., product ID)",
    )

    owner_type: str = Field(
        max_length=20,
        nullable=False,
        description="Type of the owning entity (e.g., product, user)",
    )

    filename: str = Field(
        max_length=255,
        nullable=False,
        description="Original filename (e.g., product.jpg)",
    )

    media_type: str = Field(
        max_length=20, nullable=False, description="Media category (e.g., image, video)"
    )

    file_type: str = Field(
        max_length=100,
        nullable=False,
        description="MIME type (e.g., image/jpeg, video/mp4)",
    )

    file_size: int = Field(nullable=False, description="File size in bytes")

    storage_key: str = Field(
        max_length=500,
        nullable=False,
        description="Path in MinIO (e.g., media/uuid.jpg)",
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
        description="Whether the media is active (soft-delete flag)",
    )

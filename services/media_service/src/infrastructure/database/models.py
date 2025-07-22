from sqlmodel import SQLModel, Field, Column as SQLColumn
from typing import Optional, Literal
from uuid import UUID, uuid4
from datetime import datetime

import sqlalchemy.dialects.postgresql as pg

# Define allowed owner types
OwnerType = Literal["product", "post", "user", "category"]


class Media(SQLModel, table=True):
    __tablename__ = "media"
    __table_args__ = {"schema": "media"}

    id: UUID = Field(
        sa_column=SQLColumn(
            pg.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            index=True,
            nullable=False,
        )
    )

    owner_id: UUID = Field(
        index=True,
        nullable=False,
        description="The ID of the owning entity (e.g., product ID)",
    )

    owner_type: OwnerType = Field(
        sa_column=SQLColumn(
            pg.VARCHAR(20),
            nullable=False,
        ),
        description="Type of the owning entity",
    )

    url: str = Field(max_length=255, nullable=False)

    type: str = Field(max_length=20, nullable=False)  # e.g., 'image', 'video'

    created_at: Optional[datetime] = Field(
        sa_column=SQLColumn(
            pg.TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
        )
    )

from sqlmodel import SQLModel, Field, Column as SQLColumn
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "notification"}

    id: UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            index=True,
            nullable=False,
        )
    )

    user_id: UUID = Field(
        index=True,
        nullable=False,
        description="Logical reference to auth.users.id (no real FK in multi-service setup)",
    )

    type: str = Field(
        max_length=20,
        nullable=False,
        description="Type of notification: email, sms, push, etc.",
    )

    content: str = Field(
        sa_column=Column(
            pg.TEXT,
            nullable=False,
        ),
        description="The message content",
    )

    status: str = Field(
        max_length=20,
        nullable=False,
        description="e.g., pending, sent, failed, delivered",
    )

    created_at: Optional[datetime] = Field(
        sa_column=SQLColumn(
            pg.TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
        )
    )

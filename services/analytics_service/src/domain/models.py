from sqlmodel import SQLModel, Field, Column as SQLColumn
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

import sqlalchemy.dialects.postgresql as pg


# Use native PostgreSQL JSONB and UUID types via sqlalchemy.dialects.postgresql
class Metrics(SQLModel, table=True):
    __tablename__ = "metrics"
    __table_args__ = {"schema": "analytics"}

    id: UUID = Field(
        sa_column=SQLColumn(
            pg.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            index=True,
            nullable=False,
        )
    )

    type: str = Field(max_length=50, nullable=False)

    value: Dict[str, Any] = Field(
        sa_column=SQLColumn(
            pg.JSONB,  # Use PostgreSQL-specific JSONB
            nullable=False,
        )
    )

    created_at: Optional[datetime] = Field(
        sa_column=SQLColumn(
            pg.TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
        )
    )

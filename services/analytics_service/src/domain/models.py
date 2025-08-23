from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column as SQLColumn
from sqlmodel import Field, SQLModel


class Metrics(SQLModel, table=True):
    """
    Generic metrics table for analytics service.
    Uses PostgreSQL JSONB for flexible schema.
    """

    # Remove schema unless you have multiple schemas
    __table_args__ = {"schema": "analytics", "extend_existing": True}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        description="Unique identifier for the metric",
    )

    metric_type: str = Field(
        max_length=50,
        index=True,
        description="Type of metric (user_activity, sales, system, etc.)",
    )

    value: Dict[str, Any] = Field(
        default={},
        sa_column=SQLColumn(pg.JSONB, nullable=False),
        description="Metric data in structured JSON format",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SQLColumn(pg.TIMESTAMP(timezone=True), nullable=False, index=True),
        description="When the metric was recorded (UTC)",
    )

# src/interfaces/http/schemas.py
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class MetricCreate(BaseModel):
    """
    Schema for creating a new metric.
    Used in POST requests to /metrics.
    """

    metric_type: str = Field(
        ..., max_length=50, description="Type of metric (user_activity, sales, system)"
    )
    value: Dict[str, Any] = Field(..., description="Metric data in key-value format")

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "metric_type": "user.login",
                "value": {
                    "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "ip_address": "192.168.1.1",
                },
            }
        }


class MetricResponse(BaseModel):
    """
    Schema for metric response.
    Includes all fields from Metrics model.
    """

    id: UUID = Field(..., description="Unique identifier for the metric")
    metric_type: str = Field(..., description="Type of metric")
    value: Dict[str, Any] = Field(..., description="Metric data")
    created_at: datetime = Field(..., description="When the metric was recorded")

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "metric_type": "user.login",
                "value": {
                    "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "ip_address": "192.168.1.1",
                },
                "created_at": "2025-08-22T12:00:00Z",
            }
        }


class MetricsListResponse(BaseModel):
    """
    Schema for paginated list of metrics.
    """

    metrics: list[MetricResponse] = Field(..., description="List of metrics")
    meta: dict = Field(..., description="Pagination metadata")

    class Config:
        extra = "forbid"


class HealthResponse(BaseModel):
    """
    Schema for health check response.
    """

    status: str = Field(..., description="Service status (healthy, unhealthy)")
    service: str = Field(..., description="Service name")
    database: str = Field(..., description="Database connection status")
    redis: str = Field(..., description="Redis connection status")

    class Config:
        extra = "forbid"

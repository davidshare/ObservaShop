"""
Pydantic schemas for the analytics service API.
These schemas exactly match the return types of AnalyticsService methods.
No dummy data — only real field definitions.
"""

from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class EventCreate(BaseModel):
    """
    Schema for creating a new analytics event.
    Matches the input parameters of AnalyticsService.track_event().
    """

    event_type: str = Field(
        ..., description="Type of event (e.g., user.login, order.created)"
    )
    data: Dict[str, Any] = Field(..., description="Event payload data")

    model_config = ConfigDict(extra="forbid")


class UserActivitySummaryResponse(BaseModel):
    """
    Schema for user activity summary.
    Matches the return type of AnalyticsService.get_user_activity_summary().
    """

    period_days: int = Field(..., description="Number of days in the analysis period")
    total_events: int = Field(..., description="Total number of events in the period")
    events_by_type: Dict[str, int] = Field(
        ..., description="Count of events grouped by event type"
    )
    generated_at: datetime = Field(..., description="When the summary was generated")

    model_config = ConfigDict(extra="forbid")


class SalesSummaryResponse(BaseModel):
    """
    Schema for sales performance summary.
    Matches the return type of AnalyticsService.get_sales_summary().
    """

    period_days: int = Field(..., description="Number of days in the analysis period")
    total_revenue: float = Field(..., description="Total revenue generated")
    orders_count: int = Field(..., description="Total number of orders")
    average_order_value: float = Field(..., description="Average value per order")
    generated_at: datetime = Field(..., description="When the summary was generated")

    model_config = ConfigDict(extra="forbid")


class SystemHealthResponse(BaseModel):
    """
    Schema for system health metrics.
    Matches the return type of AnalyticsService.get_system_health().
    """

    period: str = Field(..., description="Time period for the metrics")
    metrics: Dict[str, Dict[str, float]] = Field(
        ..., description="Health metrics with avg/max/min values"
    )
    generated_at: datetime = Field(..., description="When the metrics were generated")

    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    """
    Schema for error responses.
    Standardized format for all API errors.
    """

    detail: str = Field(..., description="Error message")

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    """
    Schema for health check response.
    """

    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database connection status")
    redis: str = Field(..., description="Redis connection status")

    model_config = ConfigDict(extra="forbid")

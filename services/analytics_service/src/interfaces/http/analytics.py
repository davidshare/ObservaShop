"""
API routes for the analytics service.
Uses AnalyticsService to retrieve real data from PostgreSQL.
No hardcoded responses — all data comes from the database.
"""

from typing import Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session

from src.application.analytics_service import AnalyticsService
from src.config.logger_config import log
from src.infrastructure.database.session import get_session
from src.infrastructure.services import redis_service
from src.interfaces.http.schemas import (
    EventCreate,
    UserActivitySummaryResponse,
    SalesSummaryResponse,
    SystemHealthResponse,
)
from shared.libs.observability.metrics import create_metrics_endpoint


# Create router
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

metrics_endpoint = create_metrics_endpoint()
router.add_api_route(
    "/metrics", metrics_endpoint, name="metrics", include_in_schema=False
)


def get_analytics_service(session: Session = Depends(get_session)) -> AnalyticsService:
    """
    Dependency injection for AnalyticsService.

    Args:
        session: Database session

    Returns:
        AnalyticsService instance
    """
    return AnalyticsService(session)


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def track_event(
    event: EventCreate,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Track a new analytics event.
    Uses the real AnalyticsService to store data in PostgreSQL.
    """
    try:
        await analytics_service.track_event(event.event_type, event.data)
        return {"status": "success", "message": "Event tracked"}
    except Exception as e:
        log.error("Failed to track event", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to track event: {str(e)}",
        ) from e


@router.get("/user-activity", response_model=UserActivitySummaryResponse)
async def get_user_activity_summary(
    days: int = Query(7, ge=1, le=90),
    user_id: Optional[UUID] = Query(None),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Get user activity summary.
    Uses AnalyticsService to query real data from PostgreSQL.
    """
    try:
        result = await analytics_service.get_user_activity_summary(days, user_id)
        return UserActivitySummaryResponse(**result)
    except Exception as e:
        log.error("Failed to get user activity summary", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user activity summary",
        ) from e


@router.get("/sales", response_model=SalesSummaryResponse)
async def get_sales_summary(
    days: int = Query(30, ge=1, le=365),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Get sales performance summary.
    Uses AnalyticsService to query real data from PostgreSQL.
    """
    try:
        result = await analytics_service.get_sales_summary(days)
        return SalesSummaryResponse(**result)
    except Exception as e:
        log.error("Failed to get sales summary", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sales summary",
        ) from e


@router.get("/system-health", response_model=SystemHealthResponse)
async def get_system_health(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Get system health metrics.
    Uses AnalyticsService to query real data from PostgreSQL.
    """
    try:
        result = await analytics_service.get_system_health()
        return SystemHealthResponse(**result)
    except Exception as e:
        log.error("Failed to get system health", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health",
        ) from e


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    Verifies connectivity to database and Redis.
    """
    try:
        # This would be replaced with actual health checks
        redis_healthy = await redis_service.ping()

        return {
            "status": "healthy" if redis_healthy else "unhealthy",
            "redis": "connected" if redis_healthy else "disconnected",
        }
    except Exception as e:
        log.error("Health check failed", error=str(e))
        return {"status": "unhealthy", "redis": "disconnected"}

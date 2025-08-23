"""
REST API routes for the notification service.
Follows senior engineering standards with proper dependency injection and error handling.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from src.application.notification_service import NotificationService
from src.config.logger_config import log
from src.core.exceptions import (
    DatabaseError,
    NotificationCreationError,
    NotificationNotFoundError,
    SchemaValidationError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.email.client import EmailClient
from src.infrastructure.services import jwt_service, redis_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
email_client = EmailClient()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    notification_status: Optional[str] = Query(
        None, description="Filter by status (pending, sent, failed, read)"
    ),
    notification_type: Optional[str] = Query(
        None, description="Filter by type (email, sms)"
    ),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("list", "notification")),
):
    """
    List notifications with pagination and filtering.
    - Requires: superadmin OR notification:list permission
    - Returns paginated list with metadata
    """
    requesting_user_id, _ = current_user_id_and_token

    try:
        log.info(
            "List notifications request",
            user_id=str(requesting_user_id),
            limit=limit,
            offset=offset,
            status=notification_status,
            notification_type=notification_type,
            filter_user_id=str(user_id) if user_id else None,
        )

        notification_service = NotificationService(
            session=session, email_client=email_client
        )
        notifications, total = notification_service.list_notifications(
            limit=limit,
            offset=offset,
            status=notification_status,
            notification_type=notification_type,
            user_id=user_id,
            requesting_user_id=requesting_user_id,
        )

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        return NotificationListResponse(notifications=notifications, meta=meta)

    except SchemaValidationError as e:
        log.warning("Invalid parameters in list notifications", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except DatabaseError as e:
        log.critical("Database error during list notifications", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications",
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during list notifications", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID = Path(
        ..., description="The UUID of the notification to retrieve"
    ),
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("read", "notification")),
):
    """
    Retrieve a specific notification by ID.
    - Requires: superadmin OR notification:read permission
    - Returns full notification details
    """
    requesting_user_id, _ = current_user_id_and_token

    try:
        log.info(
            "Get notification request",
            notification_id=str(notification_id),
            user_id=str(requesting_user_id),
        )

        notification_service = NotificationService(session=session)
        notification = notification_service.get_notification(
            notification_id=notification_id,
            user_id=requesting_user_id,
        )

        return NotificationResponse.model_validate(notification)

    except NotificationNotFoundError as e:
        log.warning("Notification not found", notification_id=str(notification_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except DatabaseError as e:
        log.critical("Database error during get notification", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification",
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during get notification", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: UUID = Path(
        ..., description="The UUID of the notification to mark as read"
    ),
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("update", "notification")),
):
    """
    Mark a notification as read.
    - Requires: superadmin OR notification:update permission
    - Returns updated notification
    """
    requesting_user_id, _ = current_user_id_and_token

    try:
        log.info(
            "Mark notification as read request",
            notification_id=str(notification_id),
            user_id=str(requesting_user_id),
        )

        notification_service = NotificationService(session=session)
        notification = notification_service.mark_as_read(
            notification_id=notification_id,
            user_id=requesting_user_id,
        )

        return NotificationResponse.model_validate(notification)

    except NotificationNotFoundError as e:
        log.warning("Notification not found", notification_id=str(notification_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except DatabaseError as e:
        log.critical("Database error during mark as read", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification status",
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during mark as read", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post("/{notification_id}/resend")
async def resend_notification(
    notification_id: UUID = Path(
        ..., description="The UUID of the notification to resend"
    ),
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("resend", "notification")),
):
    """
    Re-send a failed or pending notification.
    - Requires: superadmin OR notification:resend permission
    - Returns success status
    """
    requesting_user_id, _ = current_user_id_and_token

    try:
        log.info(
            "Resend notification request",
            notification_id=str(notification_id),
            user_id=str(requesting_user_id),
        )

        notification_service = NotificationService(session=session)
        success = notification_service.resend_notification(
            notification_id=notification_id,
            user_id=requesting_user_id,
        )

        if success:
            return {"message": "Notification resent successfully", "success": True}
        else:
            return {"message": "Failed to resend notification", "success": False}

    except NotificationNotFoundError as e:
        log.warning("Notification not found", notification_id=str(notification_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except NotificationCreationError as e:
        log.warning("Notification creation error during resend", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except DatabaseError as e:
        log.critical("Database error during resend", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification status",
        ) from e

    except Exception as e:
        log.critical("Unexpected error during resend", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring systems.
    Returns basic service status.
    """
    try:
        # Check database
        db_healthy = await redis_service.ping()

        return {
            "status": "healthy",
            "service": "notification-service",
            "database": "connected" if db_healthy else "disconnected",
            "redis": "connected" if db_healthy else "disconnected",
        }
    except Exception as e:
        log.error("Health check failed", error=str(e))
        return {"status": "unhealthy", "service": "notification-service"}

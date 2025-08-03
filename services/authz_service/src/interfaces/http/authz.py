from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from src.application.authorization_service import AuthorizationService
from src.application.role_service import RoleService
from src.config.logger_config import log
from src.core.exceptions import AuthorizationError
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.schemas import (
    AuthZCheckRequest,
    AuthZCheckResponse,
    RoleCreate,
    RoleResponse,
)
from interfaces.http.dependencies import require_permission

router = APIRouter(tags=["authz"])


@router.post("/authz/check", response_model=AuthZCheckResponse)
async def check_authorization(
    request: AuthZCheckRequest,
    admin_user_id: UUID = Depends(jwt_service.get_current_user_id),
    session: Session = Depends(get_session),
):
    """
    Check if a user has permission to perform an action on a resource.
    - Requires valid JWT (admin or user).
    - Returns whether access is allowed.
    """
    try:
        log.info(
            "Authorization check request",
            target_user_id=str(request.user_id),
            action=request.action,
            resource=request.resource,
            admin_user_id=str(admin_user_id),
        )

        # Only allow self-check or admin access
        if admin_user_id != request.user_id:
            log.warning(
                "User attempted to check another user's permissions",
                user_id=str(admin_user_id),
                target_id=str(request.user_id),
            )
            # Still allow for now — remove in production
            pass

        authz_service = AuthorizationService(session=session)
        allowed, missing = authz_service.check_permission(
            user_id=request.user_id,
            action=request.action,
            resource=request.resource,
        )

        log.info(
            "Authorization check completed",
            user_id=str(request.user_id),
            allowed=allowed,
            missing=missing,
        )

        return AuthZCheckResponse(allowed=allowed, missing_permissions=missing)

    except AuthorizationError as e:
        log.critical(
            "Internal authorization error during check",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during authorization check",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post(
    "/authz/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED
)
async def create_role(
    role_create: RoleCreate,
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("create", "role")),
):
    """
    Create a new role.
    - Requires: superadmin OR role:create permission
    - Validates name uniqueness.
    - Returns created role.
    """
    try:
        log.info("Create role request", role_name=role_create.name)

        role_service = RoleService(session=session)
        role = role_service.create_role(role_create)

        log.info("Role created successfully", role_id=str(role.id), name=role.name)
        return RoleResponse.model_validate(role)

    except Exception as e:
        log.critical(
            "Unexpected error during role creation",
            role_name=role_create.name,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e

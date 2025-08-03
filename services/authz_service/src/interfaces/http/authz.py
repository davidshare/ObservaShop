from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session

from src.application.authorization_service import AuthorizationService
from src.application.role_service import RoleService
from src.config.logger_config import log
from src.core.exceptions import (
    AuthorizationError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    AuthZCheckRequest,
    AuthZCheckResponse,
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)

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


@router.get("/authz/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID = Path(..., description="The UUID of the role to retrieve"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("read", "role")),
):
    """
    Retrieve a role by ID.
    - Requires: superadmin OR role:read permission.
    """
    try:
        log.info("Get role request", role_id=str(role_id))

        role_service = RoleService(session=session)
        role = role_service.get_role_by_id(role_id)

        log.info("Role retrieved successfully", role_id=str(role.id), name=role.name)
        return RoleResponse.model_validate(role)

    except RoleNotFoundError as e:
        log.warning("Role not found", role_id=str(role_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during get role",
            role_id=str(role_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/authz/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_update: RoleUpdate,
    role_id: UUID = Path(..., description="The UUID of the role to update"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("update", "role")),
):
    """
    Update a role's fields.
    - Requires: superadmin OR role:update permission.
    """
    try:
        log.info(
            "Update role request",
            role_id=str(role_id),
            update_data=role_update.model_dump(exclude_unset=True),
        )

        role_service = RoleService(session=session)
        role = role_service.update_role(role_id, role_update)

        log.info("Role updated successfully", role_id=str(role.id), name=role.name)
        return RoleResponse.model_validate(role)

    except RoleNotFoundError as e:
        log.warning("Role not found for update", role_id=str(role_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        ) from e

    except RoleAlreadyExistsError as e:
        log.warning("Role update failed: name already exists", role_id=str(role_id))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during role update",
            role_id=str(role_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/authz/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID = Path(..., description="The UUID of the role to delete"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("delete", "role")),
):
    """
    Delete a role by ID.
    - Requires: superadmin OR role:delete permission.
    - Returns 204 No Content.
    """
    try:
        log.info("Delete role request", role_id=str(role_id))

        role_service = RoleService(session=session)
        role_service.delete_role(role_id)

        log.info("Role deleted successfully", role_id=str(role_id))
        return  # 204 No Content

    except RoleNotFoundError as e:
        log.warning("Role not found for deletion", role_id=str(role_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during role deletion",
            role_id=str(role_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/authz/roles", response_model=RoleListResponse)
async def list_roles(
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    sort: str = "created_at:desc",
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("list", "role")),
):
    """
    List roles with pagination, filtering, and sorting.
    - Requires: superadmin OR role:list permission.
    - Supports filtering by name (partial), sorting (name, created_at), pagination.
    - Returns paginated list with meta.
    """
    try:
        log.info("List roles request", limit=limit, offset=offset, name=name, sort=sort)

        # Validate inputs
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        allowed_sort_fields = ["name", "created_at", "updated_at"]
        sort_field, direction = sort.split(":") if ":" in sort else (sort, "asc")
        if sort_field not in allowed_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field: {sort_field}",
            )
        if direction not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort direction: {direction}",
            )

        role_service = RoleService(session=session)
        roles, total = role_service.list_roles(
            limit=limit, offset=offset, name=name, sort=sort
        )

        role_responses = [RoleResponse.model_validate(role) for role in roles]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Roles listed successfully", count=len(roles), total=total)
        return RoleListResponse(roles=role_responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.critical("Unexpected error during list roles", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e

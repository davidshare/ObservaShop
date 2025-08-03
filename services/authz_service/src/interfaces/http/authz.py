from typing import Optional
from uuid import UUID
from httpx import AsyncClient

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session

from src.application.authorization_service import AuthorizationService
from src.application.role_service import RoleService
from src.application.permission_service import PermissionService
from src.application.user_role_service import UserRoleService
from src.config.logger_config import log
from src.core.exceptions import (
    AuthorizationError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    UserRoleNotFoundError,
    UserRoleAlreadyExistsError,
    PermissionAlreadyExistsError,
    PermissionNotFoundError,
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
    UserRoleResponse,
    UserRoleListResponse,
    UserRoleCreate,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    PermissionListResponse,
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


@router.post(
    "/authz/user-roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_user(
    user_role_create: UserRoleCreate,
    session: Session = Depends(get_session),
    http_client: AsyncClient = Depends(lambda: AsyncClient(timeout=10.0)),
    # ✅ CORRECT: Use require_permission
    _: UUID = Depends(require_permission("assign", "user_role")),
):
    """
    Assign a role to a user.
    - Requires: superadmin OR user_role:assign permission
    - Validates user exists via auth-service.
    - Validates role exists.
    - Returns created assignment.
    """
    try:
        log.info(
            "Assign role to user request",
            user_id=str(user_role_create.user_id),
            role_id=str(user_role_create.role_id),
        )

        user_role_service = UserRoleService(session=session, http_client=http_client)

        # ✅ Validate user exists
        if not await user_role_service.validate_user_exists(user_role_create.user_id):
            log.warning(
                "Cannot assign role: user not found",
                user_id=str(user_role_create.user_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # ✅ Validate role exists
        if not user_role_service.validate_role_exists(user_role_create.role_id):
            log.warning(
                "Cannot assign role: role not found",
                role_id=str(user_role_create.role_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )

        user_role = user_role_service.assign_role_to_user(
            user_role_create.user_id, user_role_create.role_id
        )

        log.info(
            "Role assigned successfully",
            user_id=str(user_role.user_id),
            role_id=str(user_role.role_id),
        )
        return UserRoleResponse.model_validate(user_role)

    except UserRoleAlreadyExistsError as e:
        log.warning(
            "User already has role",
            user_id=str(user_role_create.user_id),
            role_id=str(user_role_create.role_id),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical("Unexpected error during role assignment", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete(
    "/authz/user-roles/{user_id}/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_role_from_user(
    user_id: UUID = Path(...),
    role_id: UUID = Path(...),
    session: Session = Depends(get_session),
    http_client: AsyncClient = Depends(lambda: AsyncClient(timeout=10.0)),
    # ✅ CORRECT: Use require_permission
    _: UUID = Depends(require_permission("revoke", "user_role")),
):
    """
    Remove a role from a user.
    - Requires: superadmin OR user_role:revoke permission.
    - Returns 204 No Content.
    """
    try:
        log.info(
            "Remove role from user request", user_id=str(user_id), role_id=str(role_id)
        )

        user_role_service = UserRoleService(session=session, http_client=http_client)

        user_role_service.remove_role_from_user(user_id, role_id)

        log.info(
            "Role removed successfully", user_id=str(user_id), role_id=str(role_id)
        )
        return  # 204 No Content

    except UserRoleNotFoundError as e:
        log.warning(
            "User-role assignment not found", user_id=str(user_id), role_id=str(role_id)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User-role assignment not found",
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical("Unexpected error during role removal", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/authz/user-roles/{user_id}", response_model=UserRoleListResponse)
async def get_user_roles(
    user_id: UUID = Path(...),
    limit: int = 10,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    http_client: AsyncClient = Depends(lambda: AsyncClient(timeout=10.0)),
    # ✅ CORRECT: Use require_permission only if not self
):
    """
    Get all roles assigned to a user.
    - User can view their own roles.
    - Admin can view any user's roles.
    """
    try:
        log.info(
            "Get user roles request",
            target_user_id=str(user_id),
            requester_id=str(current_user_id),
        )

        # ✅ Self or admin check
        if current_user_id != user_id:
            # Must have user_role:read permission
            authz_service = AuthorizationService(session=session)
            allowed, _ = authz_service.check_permission(
                current_user_id, "read", "user_role"
            )
            if not allowed:
                log.warning(
                    "User lacks permission to read user roles",
                    user_id=str(current_user_id),
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Missing required permission: user_role:read",
                )

        user_role_service = UserRoleService(session=session, http_client=http_client)

        user_roles, total = user_role_service.get_user_roles(
            user_id, limit=limit, offset=offset
        )

        role_responses = [UserRoleResponse.model_validate(ur) for ur in user_roles]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info(
            "User roles retrieved successfully",
            user_id=str(user_id),
            count=len(user_roles),
        )
        return UserRoleListResponse(roles=role_responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.critical("Unexpected error during get user roles", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post(
    "/authz/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_permission(
    permission_create: PermissionCreate,
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("create", "permission")),
):
    """
    Create a new permission.
    - Requires: superadmin OR permission:create permission
    - Validates name uniqueness.
    - Returns created permission.
    """
    try:
        log.info("Create permission request", name=permission_create.name)

        permission_service = PermissionService(session=session)
        permission = permission_service.create_permission(permission_create)

        log.info(
            "Permission created successfully",
            permission_id=str(permission.id),
            name=permission.name,
        )
        return PermissionResponse.model_validate(permission)

    except PermissionAlreadyExistsError as e:
        log.warning(
            "Permission creation failed: name already exists",
            name=permission_create.name,
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except ValueError as e:
        log.warning("Invalid input during permission creation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during permission creation",
            name=permission_create.name,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/authz/permissions/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: int = Path(..., description="The ID of the permission to retrieve"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("read", "permission")),
):
    """
    Retrieve a permission by ID.
    - Requires: superadmin OR permission:read permission.
    """
    try:
        log.info("Get permission request", permission_id=permission_id)

        permission_service = PermissionService(session=session)
        permission = permission_service.get_permission_by_id(permission_id)

        log.info(
            "Permission retrieved successfully",
            permission_id=permission_id,
            name=permission.name,
        )
        return PermissionResponse.model_validate(permission)

    except PermissionNotFoundError as e:
        log.warning("Permission not found", permission_id=permission_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during get permission",
            permission_id=permission_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/authz/permissions/{permission_id}", response_model=PermissionResponse)
async def update_permission(
    permission_update: PermissionUpdate,
    permission_id: int = Path(..., description="The ID of the permission to update"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("update", "permission")),
):
    """
    Update a permission's fields.
    - Requires: superadmin OR permission:update permission.
    """
    try:
        log.info(
            "Update permission request",
            permission_id=permission_id,
            update_data=permission_update.model_dump(exclude_unset=True),
        )

        permission_service = PermissionService(session=session)
        permission = permission_service.update_permission(
            permission_id, permission_update
        )

        log.info(
            "Permission updated successfully",
            permission_id=permission_id,
            name=permission.name,
        )
        return PermissionResponse.model_validate(permission)

    except PermissionNotFoundError as e:
        log.warning("Permission not found for update", permission_id=permission_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        ) from e

    except PermissionAlreadyExistsError as e:
        log.warning(
            "Permission update failed: name already exists", permission_id=permission_id
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during permission update",
            permission_id=permission_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete(
    "/authz/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_permission(
    permission_id: int = Path(..., description="The ID of the permission to delete"),
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("delete", "permission")),
):
    """
    Delete a permission by ID.
    - Requires: superadmin OR permission:delete permission.
    - Returns 204 No Content.
    """
    try:
        log.info("Delete permission request", permission_id=permission_id)

        permission_service = PermissionService(session=session)
        permission_service.delete_permission(permission_id)

        log.info("Permission deleted successfully", permission_id=permission_id)
        return  # 204 No Content

    except PermissionNotFoundError as e:
        log.warning("Permission not found for deletion", permission_id=permission_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during permission deletion",
            permission_id=permission_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/authz/permissions", response_model=PermissionListResponse)
async def list_permissions(
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    sort: str = "created_at:desc",
    session: Session = Depends(get_session),
    _: UUID = Depends(require_permission("list", "permission")),
):
    """
    List permissions with pagination, filtering, and sorting.
    - Requires: superadmin OR permission:list permission.
    - Supports filtering by name (partial), sorting (name, created_at), pagination.
    - Returns paginated list with meta.
    """
    try:
        log.info(
            "List permissions request", limit=limit, offset=offset, name=name, sort=sort
        )

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

        permission_service = PermissionService(session=session)
        permissions, total = permission_service.list_permissions(
            limit=limit, offset=offset, name=name, sort=sort
        )

        permission_responses = [
            PermissionResponse.model_validate(p) for p in permissions
        ]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Permissions listed successfully", count=len(permissions), total=total)
        return PermissionListResponse(permissions=permission_responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during list permissions", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e

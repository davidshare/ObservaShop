# src/application/role_permission_service.py

from uuid import UUID
from sqlmodel import Session, select
from src.config.logger_config import log
from src.core.exceptions import (
    RoleNotFoundError,
    PermissionNotFoundError,
)
from src.domain.models import Role, Permission, RolePermission


class RolePermissionService:
    """
    Service class for handling role-permission assignment logic.
    Encapsulates CRUD operations for role_permissions.
    """

    def __init__(self, session: Session):
        self.session = session

    def assign_permission_to_role(
        self, role_id: UUID, permission_id: int
    ) -> RolePermission:
        """
        Assign a permission to a role.
        Args:
            role_id: UUID of the role.
            permission_id: ID of the permission.
        Returns:
            Created RolePermission object.
        Raises:
            RoleNotFoundError: If role does not exist.
            PermissionNotFoundError: If permission does not exist.
            ValueError: If assignment already exists.
        """
        log.debug(
            "Assigning permission to role",
            role_id=str(role_id),
            permission_id=permission_id,
        )

        # Validate role exists
        role = self.session.get(Role, role_id)
        if not role:
            log.warning(
                "Cannot assign permission: role not found", role_id=str(role_id)
            )
            raise RoleNotFoundError(f"Role with ID {role_id} not found")

        # Validate permission exists
        permission = self.session.get(Permission, permission_id)
        if not permission:
            log.warning(
                "Cannot assign permission: permission not found",
                permission_id=permission_id,
            )
            raise PermissionNotFoundError(
                f"Permission with ID {permission_id} not found"
            )

        # Check if already assigned
        existing = self.session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
        ).first()
        if existing:
            log.warning(
                "Permission already assigned to role",
                role_id=str(role_id),
                permission_id=permission_id,
            )
            raise ValueError("Permission already assigned to role")

        role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
        self.session.add(role_permission)
        try:
            self.session.commit()
            self.session.refresh(role_permission)
            log.info(
                "Permission assigned to role",
                role_id=str(role_id),
                permission_id=permission_id,
            )
            return role_permission
        except Exception as e:
            log.error("Failed to assign permission to role", error=str(e))
            self.session.rollback()
            raise

    def get_permissions_for_role(
        self,
        role_id: UUID,
        limit: int = 10,
        offset: int = 0,
        sort: str = "assigned_at:desc",
    ) -> tuple[list[RolePermission], int]:
        """
        Retrieve a paginated list of permissions assigned to a role.

        Args:
            role_id: UUID of the role
            limit: Number of permissions to return
            offset: Number of permissions to skip
            sort: Sort by field:direction (e.g., assigned_at:asc, permission_id:desc)

        Returns:
            Tuple of (list of RolePermission, total count)

        Raises:
            RoleNotFoundError: If the role does not exist
        """
        log.debug(
            "Getting permissions for role",
            role_id=str(role_id),
            limit=limit,
            offset=offset,
            sort=sort,
        )

        # Verify role exists
        role = self.session.get(Role, role_id)
        if not role:
            log.warning("Role not found", role_id=str(role_id))
            raise RoleNotFoundError(f"Role with ID {role_id} not found")

        # Build query
        query = select(RolePermission).where(RolePermission.role_id == role_id)

        # Parse sort
        sort_field, direction = (
            sort.split(":") if ":" in sort else ("assigned_at", "desc")
        )
        allowed_sort_fields = ["assigned_at", "permission_id"]
        if sort_field not in allowed_sort_fields:
            raise ValueError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise ValueError(f"Invalid sort direction: {direction}")

        # Apply sorting
        column = getattr(RolePermission, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        # Get total count
        count_query = query.with_only_columns(RolePermission.role_id).order_by()
        total = len(self.session.exec(count_query).all())

        # Apply pagination
        query = query.offset(offset).limit(limit)
        permissions = self.session.exec(query).all()

        log.info(
            "Permissions retrieved for role",
            role_id=str(role_id),
            count=len(permissions),
            total=total,
        )
        return permissions, total

    def remove_permission_from_role(self, role_id: UUID, permission_id: int) -> None:
        """
        Remove a permission from a role.
        Args:
            role_id: UUID of the role.
            permission_id: ID of the permission.
        Raises:
            ValueError: If assignment does not exist.
        """
        log.debug(
            "Removing permission from role",
            role_id=str(role_id),
            permission_id=permission_id,
        )

        role_permission = self.session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
        ).first()

        if not role_permission:
            log.warning(
                "Role-permission assignment not found",
                role_id=str(role_id),
                permission_id=permission_id,
            )
            raise ValueError("Permission not assigned to role")

        try:
            self.session.delete(role_permission)
            self.session.commit()
            log.info(
                "Permission removed from role",
                role_id=str(role_id),
                permission_id=permission_id,
            )
        except Exception as e:
            log.error("Failed to remove permission from role", error=str(e))
            self.session.rollback()
            raise

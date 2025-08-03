from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    AuthorizationError,
    PermissionAlreadyExistsError,
    PermissionNotFoundError,
)
from src.domain.models import Permission
from src.interfaces.http.schemas import PermissionCreate, PermissionUpdate


class PermissionService:
    """
    Service class for handling permission management logic.
    Encapsulates CRUD operations for permissions.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_permission(self, permission_create: PermissionCreate) -> Permission:
        """
        Create a new permission.
        Args:
            permission_create: PermissionCreate schema with new data.
        Returns:
            Created Permission object.
        Raises:
            PermissionAlreadyExistsError: If permission with same name exists.
        """
        log.debug("Creating permission", name=permission_create.name)

        if not permission_create.name or not permission_create.name.strip():
            raise ValueError("Permission name is required and cannot be empty")

        name = permission_create.name.strip()

        existing = self.session.exec(
            select(Permission).where(Permission.name == name)
        ).first()
        if existing:
            log.warning("Permission with name already exists", name=name)
            raise PermissionAlreadyExistsError(
                f"Permission with name '{name}' already exists"
            )

        permission = Permission(
            name=name,
            description=permission_create.description,
        )
        self.session.add(permission)
        try:
            self.session.commit()
            self.session.refresh(permission)
            log.info(
                "Permission created successfully",
                permission_id=str(permission.id),
                name=permission.name,
            )
            return permission
        except PermissionAlreadyExistsError:
            raise
        except Exception as e:
            log.error("Failed to create permission", name=name, error=str(e))
            self.session.rollback()
            raise AuthorizationError("Failed to create permission") from e

    def get_permission_by_id(self, permission_id: int) -> Permission:
        """
        Retrieve a permission by ID.
        Args:
            permission_id: ID of the permission.
        Returns:
            Permission object.
        Raises:
            PermissionNotFoundError: If permission does not exist.
        """
        log.debug("Fetching permission by ID", permission_id=permission_id)
        permission = self.session.get(Permission, permission_id)
        if not permission:
            log.warning("Permission not found by ID", permission_id=permission_id)
            raise PermissionNotFoundError(
                f"Permission with ID {permission_id} not found"
            )
        log.info(
            "Permission retrieved successfully",
            permission_id=permission_id,
            name=permission.name,
        )
        return permission

    def update_permission(
        self, permission_id: int, permission_update: PermissionUpdate
    ) -> Permission:
        """
        Update a permission's fields.
        Args:
            permission_id: ID of the permission to update.
            permission_update: PermissionUpdate schema with new data.
        Returns:
            Updated Permission object.
        Raises:
            PermissionNotFoundError: If permission does not exist.
            PermissionAlreadyExistsError: If new name is taken.
        """
        log.debug(
            "Updating permission",
            permission_id=permission_id,
            update_data=permission_update.model_dump(exclude_unset=True),
        )
        permission = self.session.get(Permission, permission_id)
        if not permission:
            log.warning("Permission not found for update", permission_id=permission_id)
            raise PermissionNotFoundError(
                f"Permission with ID {permission_id} not found"
            )

        # Get only fields that were provided (exclude_unset=True)
        update_data = permission_update.model_dump(exclude_unset=True)

        # If no fields were provided, return early
        if not update_data:
            log.debug("No fields to update", permission_id=permission_id)
            return permission

        # Check if name is being updated and is unique
        if "name" in update_data:
            new_name = update_data["name"].strip()
            # Only validate if name is changing
            if new_name.lower() != permission.name.lower():
                existing = self.session.exec(
                    select(Permission).where(Permission.name == new_name)
                ).first()
                if existing:
                    log.warning(
                        "Cannot update permission: name already exists",
                        new_name=new_name,
                    )
                    raise PermissionAlreadyExistsError(
                        f"Permission with name '{new_name}' already exists"
                    )
                permission.name = new_name

        # Update description if provided
        if "description" in update_data:
            permission.description = update_data["description"]

        # Update timestamp
        permission.updated_at = datetime.utcnow()

        try:
            self.session.add(permission)
            self.session.commit()
            self.session.refresh(permission)
            log.info(
                "Permission updated successfully",
                permission_id=permission_id,
                name=permission.name,
            )
            return permission
        except Exception as e:
            log.error(
                "Failed to update permission", permission_id=permission_id, error=str(e)
            )
            self.session.rollback()
            raise AuthorizationError("Failed to update permission") from e

    def delete_permission(self, permission_id: int) -> None:
        """
        Delete a permission by ID.
        Args:
            permission_id: ID of the permission to delete.
        Raises:
            PermissionNotFoundError: If permission does not exist.
        """
        log.debug("Deleting permission", permission_id=permission_id)
        permission = self.session.get(Permission, permission_id)
        if not permission:
            log.warning(
                "Permission not found for deletion", permission_id=permission_id
            )
            raise PermissionNotFoundError(
                f"Permission with ID {permission_id} not found"
            )

        try:
            self.session.delete(permission)
            self.session.commit()
            log.info(
                "Permission deleted successfully",
                permission_id=permission_id,
                name=permission.name,
            )
        except Exception as e:
            log.error(
                "Failed to delete permission", permission_id=permission_id, error=str(e)
            )
            self.session.rollback()
            raise AuthorizationError("Failed to delete permission") from e

    def list_permissions(
        self,
        limit: int = 10,
        offset: int = 0,
        name: Optional[str] = None,
        sort: str = "created_at:desc",
    ) -> tuple[List[Permission], int]:
        """
        Retrieve a paginated list of permissions with filters and sorting.
        Args:
            limit: Number of permissions to return.
            offset: Number of permissions to skip.
            name: Filter by name (partial match).
            sort: Sort by field:direction (e.g., name:asc, created_at:desc).
        Returns:
            Tuple of (list of permissions, total count).
        """
        log.debug(
            "Listing permissions", limit=limit, offset=offset, name=name, sort=sort
        )

        query = select(Permission)

        if name:
            query = query.where(Permission.name.contains(name))

        sort_field, direction = (
            sort.split(":") if ":" in sort else ("created_at", "desc")
        )
        if sort_field not in ["name", "created_at", "updated_at"]:
            raise ValueError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise ValueError(f"Invalid sort direction: {direction}")

        column = getattr(Permission, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        count_query = query.with_only_columns(Permission.id).order_by()
        total = len(self.session.exec(count_query).all())

        query = query.offset(offset).limit(limit)
        permissions = self.session.exec(query).all()

        log.info("Permissions listed successfully", count=len(permissions), total=total)
        return permissions, total

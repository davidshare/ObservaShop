from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    AuthorizationError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from src.domain.models import Role
from src.interfaces.http.schemas import RoleCreate, RoleUpdate


class RoleService:
    """
    Service class for handling role management logic.
    Encapsulates CRUD operations for roles.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_role(self, role_create: RoleCreate) -> Role:
        """
        Create a new role.
        Args:
            role_create: RoleCreate schema with new data.
        Returns:
            Created Role object.
        Raises:
            RoleAlreadyExistsError: If role with same name exists.
        """
        log.debug("Creating role", role_name=role_create.name)

        if not role_create.name or not role_create.name.strip():
            raise ValueError("Role name is required and cannot be empty")

        name = role_create.name.strip()

        existing = self.session.exec(select(Role).where(Role.name == name)).first()
        if existing:
            log.warning("Role with name already exists", name=name)
            raise RoleAlreadyExistsError(f"Role with name '{name}' already exists")

        role = Role(
            name=name,
            description=role_create.description,
        )
        self.session.add(role)
        try:
            self.session.commit()
            self.session.refresh(role)
            log.info("Role created successfully", role_id=str(role.id), name=role.name)
            return role
        except RoleAlreadyExistsError:
            raise
        except Exception as e:
            log.error("Failed to create role in database", name=name, error=str(e))
            self.session.rollback()
            raise AuthorizationError("Failed to create role") from e

    def get_role_by_id(self, role_id: UUID) -> Role:
        """
        Retrieve a role by ID.
        Args:
            role_id: UUID of the role.
        Returns:
            Role object.
        Raises:
            RoleNotFoundError: If role does not exist.
        """
        log.debug("Fetching role by ID", role_id=str(role_id))
        role = self.session.get(Role, role_id)
        if not role:
            log.warning("Role not found by ID", role_id=str(role_id))
            raise RoleNotFoundError(f"Role with ID {role_id} not found")
        log.info("Role retrieved successfully", role_id=str(role.id), name=role.name)
        return role

    def update_role(self, role_id: UUID, role_update: RoleUpdate) -> Role:
        """
        Update a role's fields.
        Args:
            role_id: UUID of the role to update.
            role_update: RoleUpdate schema with new data.
        Returns:
            Updated Role object.
        Raises:
            RoleNotFoundError: If role does not exist.
            RoleAlreadyExistsError: If new name is taken.
        """
        log.debug(
            "Updating role",
            role_id=str(role_id),
            update_data=role_update.model_dump(exclude_unset=True),
        )
        role = self.session.get(Role, role_id)
        if not role:
            log.warning("Role not found for update", role_id=str(role_id))
            raise RoleNotFoundError(f"Role with ID {role_id} not found")

        update_data = role_update.model_dump(exclude_unset=True)
        if not update_data:
            log.debug("No fields to update", role_id=str(role_id))
            return role

        # Check if name is being changed and if it's unique
        if "name" in update_data:
            new_name = update_data["name"].strip()
            if new_name == role.name:
                del update_data["name"]
            else:
                existing = self.session.exec(
                    select(Role).where(Role.name == new_name)
                ).first()
                if existing:
                    log.warning(
                        "Cannot update role: name already exists", new_name=new_name
                    )
                    raise RoleAlreadyExistsError(
                        f"Role with name '{new_name}' already exists"
                    )
                role.name = new_name

        # Update other fields
        if "description" in update_data:
            role.description = update_data["description"]

        role.updated_at = datetime.utcnow()

        try:
            self.session.add(role)
            self.session.commit()
            self.session.refresh(role)
            log.info("Role updated successfully", role_id=str(role.id), name=role.name)
            return role
        except Exception as e:
            log.error(
                "Failed to update role in database", role_id=str(role_id), error=str(e)
            )
            self.session.rollback()
            raise AuthorizationError("Failed to update role") from e

    def delete_role(self, role_id: UUID) -> None:
        """
        Delete a role by ID.
        Args:
            role_id: UUID of the role to delete.
        Raises:
            RoleNotFoundError: If role does not exist.
        """
        log.debug("Deleting role", role_id=str(role_id))
        role = self.session.get(Role, role_id)
        if not role:
            log.warning("Role not found for deletion", role_id=str(role_id))
            raise RoleNotFoundError(f"Role with ID {role_id} not found")

        try:
            self.session.delete(role)
            self.session.commit()
            log.info("Role deleted successfully", role_id=str(role.id), name=role.name)
        except Exception as e:
            log.error(
                "Failed to delete role from database",
                role_id=str(role_id),
                error=str(e),
            )
            self.session.rollback()
            raise AuthorizationError("Failed to delete role") from e

    def list_roles(
        self,
        limit: int = 10,
        offset: int = 0,
        name: Optional[str] = None,
        sort: str = "created_at:desc",
    ) -> tuple[List[Role], int]:
        """
        Retrieve a paginated list of roles with filters and sorting.
        Args:
            limit: Number of roles to return.
            offset: Number of roles to skip.
            name: Filter by role name (partial match).
            sort: Sort by field:direction (e.g., name:asc, created_at:desc).
        Returns:
            Tuple of (list of roles, total count).
        """
        log.debug("Listing roles", limit=limit, offset=offset, name=name, sort=sort)

        query = select(Role)

        if name:
            query = query.where(Role.name.contains(name))

        sort_field, direction = (
            sort.split(":") if ":" in sort else ("created_at", "desc")
        )
        if sort_field not in ["name", "created_at", "updated_at"]:
            raise ValueError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise ValueError(f"Invalid sort direction: {direction}")

        column = getattr(Role, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        count_query = query.with_only_columns(Role.id).order_by()
        total = len(self.session.exec(count_query).all())

        query = query.offset(offset).limit(limit)
        roles = self.session.exec(query).all()

        log.info("Roles listed successfully", count=len(roles), total=total)
        return roles, total

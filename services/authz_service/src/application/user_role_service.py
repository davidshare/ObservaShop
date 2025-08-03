# src/application/user_role_service.py

from typing import List
from uuid import UUID

from httpx import AsyncClient, HTTPStatusError, RequestError
from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    UserNotFoundError,
    UserRoleAlreadyExistsError,
    UserRoleNotFoundError,
)
from src.domain.models import UserRole


class UserRoleService:
    """
    Service class for handling user-role assignment logic.
    Encapsulates CRUD operations for user_roles.
    """

    def __init__(self, session: Session, http_client: AsyncClient):
        self.session = session
        self.http_client = http_client
        self.auth_service_url = "http://auth-service:8000"

    async def validate_user_exists(self, user_id: UUID) -> bool:
        """
        Validate that a user exists by calling auth-service.
        Returns True if user exists and is active.
        """
        try:
            response = await self.http_client.get(
                f"{self.auth_service_url}/auth/users/{user_id}"
            )
            response.raise_for_status()
            return True
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                log.warning("User not found in auth-service", user_id=str(user_id))
                return False
            log.warning(
                "Auth-service returned error",
                status=e.response.status_code,
                user_id=str(user_id),
            )
            return False
        except RequestError as e:
            log.critical(
                "Failed to connect to auth-service", error=str(e), exc_info=True
            )
            raise UserNotFoundError("User validation service unavailable") from e

    def validate_role_exists(self, role_id: UUID) -> bool:
        """
        Validate that a role exists in the authz database.
        """
        role = self.session.get(Role, role_id)
        return role is not None

    def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> UserRole:
        """
        Assign a role to a user.
        """
        log.debug("Assigning role to user", user_id=str(user_id), role_id=str(role_id))

        # Check if already assigned
        existing = self.session.exec(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        ).first()
        if existing:
            log.warning(
                "User already has role", user_id=str(user_id), role_id=str(role_id)
            )
            raise UserRoleAlreadyExistsError(
                f"User {user_id} already has role {role_id}"
            )

        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(user_role)
        try:
            self.session.commit()
            self.session.refresh(user_role)
            log.info(
                "Role assigned to user", user_id=str(user_id), role_id=str(role_id)
            )
            return user_role
        except Exception as e:
            log.error("Failed to assign role to user", error=str(e))
            self.session.rollback()
            raise

    def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """
        Remove a role from a user.
        """
        log.debug("Removing role from user", user_id=str(user_id), role_id=str(role_id))

        user_role = self.session.exec(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        ).first()

        if not user_role:
            log.warning(
                "User-role assignment not found",
                user_id=str(user_id),
                role_id=str(role_id),
            )
            raise UserRoleNotFoundError(f"User {user_id} does not have role {role_id}")

        try:
            self.session.delete(user_role)
            self.session.commit()
            log.info(
                "Role removed from user", user_id=str(user_id), role_id=str(role_id)
            )
        except Exception as e:
            log.error("Failed to remove role from user", error=str(e))
            self.session.rollback()
            raise

    def get_user_roles(
        self, user_id: UUID, limit: int = 10, offset: int = 0
    ) -> tuple[List[UserRole], int]:
        """
        Get all roles assigned to a user.
        """
        log.debug("Fetching roles for user", user_id=str(user_id))

        query = select(UserRole).where(UserRole.user_id == user_id)
        total = len(self.session.exec(query).all())

        query = query.offset(offset).limit(limit)
        user_roles = self.session.exec(query).all()

        log.info("User roles retrieved", user_id=str(user_id), count=len(user_roles))
        return user_roles, total

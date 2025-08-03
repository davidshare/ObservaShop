from typing import Optional, Set
from uuid import UUID
from sqlmodel import Session
from sqlalchemy import text
from src.config.logger_config import log
from src.core.exceptions import AuthorizationError
from src.infrastructure.services import redis_service


class AuthorizationService:
    """
    Service class for handling authorization logic.
    Encapsulates permission checks based on user roles.
    Uses a single SQL query to retrieve all permissions and detect superadmin status.
    """

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.
        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    async def check_permission(
        self, user_id: UUID, action: str, resource: str
    ) -> tuple[bool, list[str]]:
        """
        Check if a user has the required permission.
        Uses cache first, falls back to DB.
        Returns (allowed, missing_permissions).
        """
        log.debug(
            "Checking permission",
            user_id=str(user_id),
            action=action,
            resource=resource,
        )

        # Validate inputs
        if not user_id:
            log.warning("Invalid user_id: None or empty")
            return False, [f"{resource}:{action}"]

        if not action or not resource:
            log.warning(
                "Missing action or resource",
                action=action,
                resource=resource,
            )
            return False, [f"{resource}:{action}"]

        # 1. Try cache
        result = await self._check_permission_from_cache(user_id, action, resource)
        if result is not None:
            return result

        # 2. Fallback to DB
        return await self._check_permission_from_db(user_id, action, resource)

    async def _check_permission_from_cache(
        self, user_id: UUID, action: str, resource: str
    ) -> Optional[tuple[bool, list[str]]]:
        """
        Try to get permission decision from Redis cache.
        Returns None if cache is unavailable or miss.
        """
        try:
            cached_data = await redis_service.get_user_permissions(user_id)
            if cached_data is None:
                log.debug("Permission cache miss", user_id=str(user_id))
                return None

            is_superadmin: bool = cached_data.get("is_superadmin", False)
            permissions: Set[str] = cached_data.get("permissions", set())

            if is_superadmin:
                log.info("Superadmin access granted (cache)", user_id=str(user_id))
                return True, []

            required_permission = f"{resource}:{action}"
            allowed = required_permission in permissions
            missing = [] if allowed else [required_permission]
            return allowed, missing

        except Exception as e:
            log.warning("Permission cache check failed", error=str(e))
            return None  # Fail-soft: continue to DB

    async def _check_permission_from_db(
        self, user_id: UUID, action: str, resource: str
    ) -> tuple[bool, list[str]]:
        """
        Check permission directly from the database.
        Updates cache on success.
        """
        required_permission = f"{resource}:{action}"

        # ✅ Fixed query: Removed OVER(), use proper GROUP BY
        query = """
        SELECT
            p.name,
            BOOL_OR(r.name = 'superadmin') FILTER (WHERE r.name IS NOT NULL) AS is_superadmin
        FROM authz.user_roles ur
        JOIN authz.roles r ON ur.role_id = r.id
        LEFT JOIN authz.role_permissions rp ON r.id = rp.role_id
        LEFT JOIN authz.permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = :user_id
        GROUP BY p.name;
        """

        try:
            result = self.session.exec(
                text(query), params={"user_id": str(user_id)}
            ).all()

            if not result:
                log.warning("User has no roles or does not exist", user_id=str(user_id))
                return False, [required_permission]

            permissions = {row[0] for row in result if row[0] is not None}
            is_superadmin = any(row[1] for row in result)

            # Update cache
            try:
                cache_data = {
                    "permissions": permissions,
                    "is_superadmin": is_superadmin,
                }
                await redis_service.set_user_permissions(user_id, cache_data)
            except Exception as e:
                log.warning("Failed to update permission cache", error=str(e))

            if is_superadmin:
                log.info("Superadmin access granted (DB)", user_id=str(user_id))
                return True, []

            if required_permission in permissions:
                log.info(
                    "Permission granted (DB)",
                    user_id=str(user_id),
                    permission=required_permission,
                )
                return True, []

            log.warning(
                "Permission denied (DB)",
                user_id=str(user_id),
                required=required_permission,
                available=list(permissions),
            )
            return False, [required_permission]

        except AuthorizationError:
            raise

        except ValueError as e:
            log.warning("Invalid input during DB permission check", error=str(e))
            raise AuthorizationError("Invalid input provided") from e

        except ConnectionError as e:
            log.critical(
                "Database connection failed during permission check", exc_info=True
            )
            raise AuthorizationError("Database unavailable") from e

        except Exception as e:
            log.critical(
                "Unexpected error during DB permission check",
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            raise AuthorizationError("Internal authorization error") from e

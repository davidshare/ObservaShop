# src/infrastructure/http/authz_client.py

from typing import Dict
from uuid import UUID
from httpx import AsyncClient, RequestError, HTTPStatusError
from src.config.logger_config import log
from src.config.config import config
from src.core.exceptions import (
    UserValidationError,
    ServiceUnavailableError,
    PermissionDeniedError,
)


class AuthzServiceClient:
    """
    Client for calling authz-service internal endpoints.
    Uses a shared secret for authentication.
    """

    def __init__(self):
        self.authz_service_url = config.AUTHZ_SERVICE_URL

    async def get_user_permissions(self, user_id: UUID) -> Dict[str, object]:
        """
        Fetch user's permissions from authz-service using shared secret.
        """
        headers = {"X-Internal-Secret": config.INTERNAL_SHARED_SECRET}
        url = f"{self.authz_service_url}/authz/internal/users/{user_id}/permissions"

        async with AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()

            except HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code == 404:
                    log.warning("User not found in authz-service", user_id=str(user_id))
                    raise UserValidationError(
                        f"User with ID {user_id} not found"
                    ) from e
                elif status_code == 403:
                    log.critical("Internal shared secret mismatch")
                    raise PermissionDeniedError("Service authentication failed") from e
                else:
                    log.error("Unexpected error from authz-service", status=status_code)
                    raise UserValidationError(
                        f"User validation failed: {status_code}"
                    ) from e

            except RequestError as e:
                log.critical(
                    "Failed to connect to authz-service", error=str(e), exc_info=True
                )
                raise ServiceUnavailableError(
                    "Authorization service unavailable"
                ) from e

            except Exception as e:
                log.critical("Unexpected error", exc_info=True)
                raise UserValidationError("Internal authorization error") from e

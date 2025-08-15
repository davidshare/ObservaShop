from uuid import UUID

from fastapi import Depends, HTTPException

from src.config.logger_config import log
from src.infrastructure.services import jwt_service


def require_permission(action: str, resource: str):
    """
    Dependency that checks if the user has the required permission.
    Uses permissions embedded in the JWT — no HTTP call to authz-service.
    """

    def dependency(
        current_user_id_and_claims: tuple[UUID, dict] = Depends(
            jwt_service.get_current_user_id_with_claims
        ),
    ) -> UUID:
        current_user_id, claims = current_user_id_and_claims

        # Check superadmin
        if claims.get("is_superadmin", False):
            log.info("Superadmin access granted", user_id=str(current_user_id))
            return current_user_id

        # Check permissions
        required = f"{resource}:{action}"
        if required in claims.get("permissions", []):
            log.info(
                "Permission granted", user_id=str(current_user_id), permission=required
            )
            return current_user_id

        log.warning(
            "Permission denied", user_id=str(current_user_id), required=required
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    return dependency

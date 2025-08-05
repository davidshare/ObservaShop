from uuid import UUID
from fastapi import Depends, HTTPException
from sqlmodel import Session
from src.config.logger_config import log
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.application.authorization_service import AuthorizationService


def require_permission(action: str, resource: str):
    """
    Dependency that ensures the current user has the required permission.
    Checks:
    1. Is the user in the 'superadmin' role? → allow
    2. Does the user have the '{resource}:{action}' permission? → allow
    Uses a single call to check_permission, which returns both role and permission data.
    """

    async def dependency(
        current_user_id_and_token: [UUID, str] = Depends(
            jwt_service.get_current_user_id
        ),
        session: Session = Depends(get_session),
    ) -> UUID:
        current_user_id, _ = current_user_id_and_token

        log.debug(
            "Checking permission",
            user_id=str(current_user_id),
            action=action,
            resource=resource,
        )

        authz_service = AuthorizationService(session=session)

        try:
            # Single call to get ALL permissions and superadmin status
            allowed, missing = await authz_service.check_permission(
                user_id=current_user_id,
                action=action,
                resource=resource,
            )
        except Exception as e:
            log.critical(
                "Unexpected error during permission check",
                user_id=str(current_user_id),
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            ) from e

        if allowed:
            log.info(
                "Permission granted",
                user_id=str(current_user_id),
                permission=f"{resource}:{action}",
            )
            return current_user_id

        log.warning(
            "Permission denied",
            user_id=str(current_user_id),
            required=f"{resource}:{action}",
            missing=missing,
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    return dependency

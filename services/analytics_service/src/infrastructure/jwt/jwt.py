"""
JWT Service Module

Provides secure, observable, and dependency-injectable JWT validation for the payment-service.
Uses the shared JWT_SECRET to verify tokens issued by auth-service, ensuring zero-trust
between microservices. Does NOT call auth-service for validation — all checks are local.

This service is responsible for:
- Verifying JWT signature and expiry
- Extracting user_id from the 'sub' claim
- Converting internal domain exceptions to HTTP responses
- Integrating with FastAPI dependency injection via OAuth2PasswordBearer

The service is designed to be:
- Secure: Validates tokens locally with shared secret
- Observable: Full structured logging with loguru
- Resilient: Handles signature, expiry, format, and claim errors
- Dependency-injectable: Used via Depends(jwt_service.get_current_user_id)

Example usage in FastAPI endpoint:
    @router.get("/protected")
    async def protected_route(user_id: UUID = Depends(jwt_service.get_current_user_id)):
        return {"user_id": user_id}
"""

from typing import Any, Dict
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt

from src.config.config import JWTConfig
from src.config.logger_config import log
from src.core.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingClaimError,
)


# ------------------------
# OAuth2 Password Bearer Scheme
# ------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
"""
OAuth2 scheme for Bearer token authentication.
Enables:
- Swagger UI "Authorize" button
- Automatic extraction of Authorization: Bearer <token>
- Standard OAuth2 password flow
"""


# ------------------------
# JWT Service
# ------------------------


class JWTService:
    """
    A secure, observable, and testable service for JWT validation.
    Validates tokens locally using the shared JWT_SECRET — does NOT call auth-service.
    Converts domain exceptions to HTTP responses for FastAPI integration.

    This service is a singleton, instantiated once in src/infrastructure/services.py
    with config from src/config/config.py.

    Attributes:
        config (JWTConfig): The JWT configuration (secret, algorithm, expiry)
    """

    def __init__(self, config: JWTConfig):
        """
        Initialize the JWTService with configuration.
        Logs service startup for observability.

        Args:
            config (JWTConfig): The JWT configuration object.
        """
        self.config = config
        log.info(
            "JWTService initialized [algorithm={}, access_ttl={}m]",
            config.ALGORITHM,
            config.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.
        Does NOT extract user_id — returns full payload for further processing.

        Args:
            token (str): The raw JWT token string (without 'Bearer ' prefix).

        Returns:
            Dict[str, Any]: The decoded JWT payload (e.g., {'sub': 'user-id', 'exp': 123456}).

        Raises:
            TokenExpiredError: If the token has expired.
            TokenInvalidError: If the token signature is invalid, malformed, or decoding fails.
        """
        log.debug("Verifying JWT token (length={})", len(token))

        try:
            payload = jwt.decode(
                token,
                self.config.JWT_SECRET,
                algorithms=[self.config.ALGORITHM],
            )
            log.success("Token decoded successfully [sub={}]", payload.get("sub"))
            return payload

        except ExpiredSignatureError as e:
            log.warning("Token verification failed: expired")
            raise TokenExpiredError("Token has expired") from e

        except JWTError as e:
            log.error("JWT decoding failed (signature, format, etc.)", error=str(e))
            raise TokenInvalidError(f"Invalid token: {str(e)}") from e

        except Exception as e:
            log.exception("Unexpected error during token verification", error=str(e))
            raise TokenInvalidError("Internal token validation error") from e

    def get_current_user_id(
        self, token: str = Depends(oauth2_scheme)
    ) -> tuple[UUID, str]:
        """
        FastAPI dependency: extracts and validates the user_id from a Bearer token
        and returns both the user_id and the raw token.

        This method is the primary entry point for JWT authentication in endpoints.
        It validates the token's signature and expiration,
        extracts the 'sub' claim, and verifies it is a valid UUID.
        The raw token is returned alongside the user_id to enable secure
        service-to-service communication (e.g., forwarding the token to auth-service).

        Flow:
            1. Extract token via OAuth2PasswordBearer.
            2. Verify signature and expiry using `verify_token`.
            3. Extract the 'sub' claim (user ID).
            4. Validate the 'sub' claim is a valid UUID.
            5. Return the UUID and the raw token string.

        Args:
            token (str): The Bearer token, automatically injected by FastAPI via the oauth2_scheme dependency.

        Returns:
            tuple[UUID, str]: A tuple containing:
                - The user_id extracted from the 'sub' claim.
                - The original raw JWT token string, for forwarding to other services.

        Raises:
            HTTPException: 401 if the token is missing, expired, invalid, or missing the 'sub' claim.
            HTTPException: 500 if an unexpected internal error occurs during validation.

        Example:
            This dependency is used in endpoints like:

            @router.get("/authz/user-roles/{user_id}")
            async def get_user_roles(
                user_id: UUID,
                current_user: tuple[UUID, str] = Depends(jwt_service.get_current_user_id)
            ):
                current_user_id, raw_token = current_user
                # Use current_user_id for authorization checks
                # Use raw_token to call auth-service for user validation
        """
        log.info("Authenticating user from Bearer token")

        try:
            payload = self.verify_token(token)
            user_id_str = payload.get("sub")

            if not user_id_str:
                log.warning("Token is missing 'sub' claim")
                raise TokenMissingClaimError("Token is missing 'sub' (user ID)")

            try:
                user_id = UUID(user_id_str)
                log.info("Successfully authenticated user_id={}", user_id)
                return user_id, token  # Return both the UUID and the raw token
            except ValueError as e:
                log.warning(
                    "Token contains invalid UUID format in 'sub' claim",
                    sub_value=user_id_str,
                )
                raise TokenInvalidError("Invalid user ID format in token") from e

        except TokenExpiredError as e:
            log.info("Authentication failed: token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except TokenInvalidError as e:
            log.info("Authentication failed: invalid or malformed token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except TokenMissingClaimError as e:
            log.warning("Authentication failed: missing user ID in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing user ID (claim 'sub')",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except HTTPException:
            # Re-raise HTTPException (401, 403, etc.)
            raise

        except Exception as e:
            log.exception(
                "Unexpected error during authentication", error=str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error",
            ) from e

    def get_current_user_id_with_claims(
        self, token: str = Depends(oauth2_scheme)
    ) -> tuple[UUID, dict]:
        """
        Extract user_id and authorization claims from JWT.
        Returns both for permission checks.
        """
        try:
            payload = self.verify_token(token)
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise TokenMissingClaimError("Token is missing 'sub' claim")
            user_id = UUID(user_id_str)

            claims = {
                "permissions": payload.get("permissions", []),
                "is_superadmin": payload.get("is_superadmin", False),
            }
            return user_id, claims

        except TokenExpiredError as e:
            log.info("Authentication failed: token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except TokenInvalidError as e:
            log.info("Authentication failed: invalid or malformed token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except Exception as e:
            log.exception("Unexpected error", exc_info=True)
            raise HTTPException(500, "Internal authentication error") from e

# src/infrastructure/jwt/jwt.py

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import (
    jwt,
    JWTError,
    ExpiredSignatureError,
    InvalidTokenError,
    ClaimValidationError,
)
from loguru import logger
from pydantic import BaseModel

from src.core.exceptions import (
    TokenExpiredError,
    TokenMissingClaimError,
    TokenInvalidError,
)


# ------------------------
# OAuth2 Password Bearer Scheme
# ------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
"""
Enables:
- Swagger UI "Authorize" button
- Automatic extraction of Bearer tokens
- Standard OAuth2 password flow
"""


# ------------------------
# Configuration
# ------------------------


class JWTConfig(BaseModel):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


# ------------------------
# JWT Service
# ------------------------


class JWTService:
    """
    A secure, observable, and testable service for JWT creation and validation.
    Uses domain exceptions internally and logs key operations with loguru.
    """

    def __init__(self, config: JWTConfig):
        self.config = config
        logger.info(
            "JWTService initialized [algorithm={}, access_ttl={}m, refresh_ttl={}d]",
            config.algorithm,
            config.access_token_expire_minutes,
            config.refresh_token_expire_days,
        )

    def create_access_token(
        self, user_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a short-lived access token.
        """
        expire = expires_delta or timedelta(
            minutes=self.config.access_token_expire_minutes
        )
        logger.debug(
            "Creating access token for user_id={} with expiry={}", user_id, expire
        )

        try:
            token = self._create_token(data={"sub": str(user_id)}, expires_delta=expire)
            logger.success("Access token created successfully for user_id={}", user_id)
            return token
        except Exception as e:
            logger.error(
                "Failed to create access token for user_id={}: {}", user_id, str(e)
            )
            raise RuntimeError("Could not generate access token") from e

    def create_refresh_token(
        self, user_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a long-lived refresh token.
        """
        expire = expires_delta or timedelta(days=self.config.refresh_token_expire_days)
        logger.debug(
            "Creating refresh token for user_id={} with expiry={}", user_id, expire
        )

        try:
            token = self._create_token(
                data={"sub": str(user_id), "type": "refresh"}, expires_delta=expire
            )
            logger.success("Refresh token created successfully for user_id={}", user_id)
            return token
        except Exception as e:
            logger.error(
                "Failed to create refresh token for user_id={}: {}", user_id, str(e)
            )
            raise RuntimeError("Could not generate refresh token") from e

    def _create_token(self, data: Dict[str, Any], expires_delta: timedelta) -> str:
        """
        Internal: sign and encode a JWT token.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})

        try:
            encoded = jwt.encode(
                to_encode, self.config.secret_key, algorithm=self.config.algorithm
            )
            logger.trace("Token encoded successfully [exp={}]", expire.isoformat())
            return encoded
        except Exception as e:
            logger.error("JWT encoding failed: {}", str(e))
            raise

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.
        :raises TokenError: With specific subtype if validation fails
        """
        logger.debug("Verifying JWT token (length={})", len(token))

        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )
            logger.success("Token decoded successfully [sub={}]", payload.get("sub"))
            return payload

        except ExpiredSignatureError as e:
            logger.warning("Token verification failed: expired")
            raise TokenExpiredError("Token has expired") from e

        except InvalidTokenError as e:
            logger.warning("Token verification failed: invalid token - {}", str(e))
            raise TokenInvalidError(f"Invalid token: {str(e)}") from e

        except ClaimValidationError as e:
            logger.warning("Token verification failed: invalid claims - {}", str(e))
            raise TokenInvalidError(f"Token claims are invalid: {str(e)}") from e

        except JWTError as e:
            logger.error("Unexpected JWT error during verification: {}", str(e))
            raise TokenInvalidError(f"Token validation failed: {str(e)}") from e

        except Exception as e:
            logger.critical("Unexpected error during token verification: {}", str(e))
            raise TokenInvalidError("Internal token validation error") from e

    def get_current_user_id(self, token: str = Depends(oauth2_scheme)) -> UUID:
        """
        FastAPI dependency: extracts user_id from Bearer token.
        Converts internal exceptions to HTTPException with proper logging.
        """
        logger.info("Authenticating user from Bearer token")

        try:
            payload = self.verify_token(token)
            user_id_str = payload.get("sub")

            if not user_id_str:
                logger.warning("Token is missing 'sub' claim")
                raise TokenMissingClaimError("Token is missing 'sub' (user ID)")

            user_id = UUID(user_id_str)
            logger.info("Successfully authenticated user_id={}", user_id)
            return user_id

        except TokenExpiredError as e:
            logger.info("Authentication failed: token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except TokenInvalidError as e:
            logger.info("Authentication failed: invalid or malformed token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except TokenMissingClaimError as e:
            logger.warning("Authentication failed: missing user ID in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing user ID (claim 'sub')",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except ValueError as e:
            logger.warning(
                "Authentication failed: invalid UUID format in token: {}", str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except Exception as e:
            logger.critical("Unexpected error during authentication: {}", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error",
            ) from e

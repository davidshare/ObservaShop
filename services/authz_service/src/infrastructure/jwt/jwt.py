# src/infrastructure/jwt/jwt.py

from typing import Dict, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from config.logger_config import log
from pydantic import BaseModel

from src.core.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingClaimError,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class JWTConfig(BaseModel):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7


class JWTService:
    def __init__(self, config: JWTConfig):
        self.config = config
        log.info(
            "JWTService initialized [algorithm={}, access_ttl={}m]",
            config.algorithm,
            config.access_token_expire_minutes,
        )

    def verify_token(self, token: str) -> Dict[str, Any]:
        log.debug("Verifying JWT token (length={})", len(token))

        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
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
            log.critical("Unexpected error during token verification", error=str(e))
            raise TokenInvalidError("Internal token validation error") from e

    def get_current_user_id(self, token: str = Depends(oauth2_scheme)) -> UUID:
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
                return user_id
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
            raise

        except Exception as e:
            log.critical(
                "Unexpected error during authentication", error=str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error",
            ) from e

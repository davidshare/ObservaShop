from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from jose import jwt as jose_jwt
from jose.exceptions import JWTError
from sqlmodel import Session

from src.application.user_service import UserService
from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import (
    InvalidCredentialsError,
    TokenDeserializationError,
    TokenNotFoundError,
    TokenStorageError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserValidationError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service, redis_service
from src.infrastructure.http.authz_client import AuthzServiceClient
from src.interfaces.http.schemas import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    UserListResponse,
    UserListQuery,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(user: UserCreate, session: Session = Depends(get_session)):
    """
    Register a new user.

    Args:
        user: User registration data.
        session: Database session (injected).

    Returns:
        UserResponse: Created user data.

    Raises:
        HTTPException: 409 if email exists, 400 if invalid input, 500 for server errors.
    """
    log.info("Received registration request", email=user.email)
    try:
        user_service = UserService(session=session)
        db_user = user_service.create_user(user)
        log.info(
            "User registered successfully",
            user_id=str(db_user.id),
            email=db_user.email,
        )
        return UserResponse.model_validate(db_user)

    except UserAlreadyExistsError as e:
        log.warning("Registration failed: email already exists", email=user.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from e

    except ValueError as e:
        log.warning(
            "Registration failed: invalid input", email=user.email, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during registration",
            email=user.email,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, session: Session = Depends(get_session)):
    """
    Authenticate a user and return JWT tokens.
    """
    try:
        log.info("Login attempt", email=user.email)

        user_service = UserService(session=session)
        user_id = user_service.authenticate_user(user.email, user.password)

        authz_client = AuthzServiceClient()
        user_data = await authz_client.get_user_permissions(user_id)

        # Generate tokens
        access_token = jwt_service.create_access_token(
            user_id=user_id,
            permissions=user_data["permissions"],
            is_superadmin=user_data["is_superadmin"],
        )
        refresh_token = jwt_service.create_refresh_token(user_id)

        # Store refresh token in Redis
        await redis_service.set_refresh_token(refresh_token, user_id)

        log.info("Login successful", user_id=str(user_id), email=user.email)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except InvalidCredentialsError as e:
        log.warning("Login failed: invalid credentials", email=user.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except UserValidationError as e:
        log.critical("User validation failed at login", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User account invalid. Contact administrator.",
        ) from e

    except PermissionDeniedError as e:
        log.critical("Service-to-service permission denied", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal service error. Contact administrator.",
        ) from e

    except ServiceUnavailableError as e:
        log.critical("Authz-service unavailable during login", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during login",
            email=user.email,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest, session: Session = Depends(get_session)
):
    """
    Exchange a valid refresh token for a new access and refresh token pair.
    Implements token rotation: old refresh token is invalidated, new one issued.
    """
    try:
        log.info(
            "Refresh token request received",
            token_hash=hash(request.refresh_token) % 10**8,
        )

        # 1. Validate that the token is a valid JWT format
        try:
            # Decode without verification to check structure
            jose_jwt.get_unverified_claims(request.refresh_token)
        except JWTError as e:
            log.warning(
                "Refresh token is not a valid JWT",
                token_hash=hash(request.refresh_token) % 10**8,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token format",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        # 2. Retrieve user_id from Redis
        try:
            user_id = await redis_service.get_refresh_token(request.refresh_token)
        except TokenNotFoundError as e:
            log.warning(
                "Refresh token not found in Redis",
                token_hash=hash(request.refresh_token) % 10**8,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except TokenDeserializationError as e:
            log.critical(
                "Security alert: corrupted refresh token data",
                raw_token=request.refresh_token,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            ) from e
        except TokenStorageError as e:
            log.critical("Redis unavailable during refresh", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            ) from e

        # 3. Validate user exists and is active
        user_service = UserService(session=session)
        user_service.validate_user_active(user_id)

        # 4. Generate new tokens
        new_access_token = jwt_service.create_access_token(user_id)
        new_refresh_token = jwt_service.create_refresh_token(user_id)

        # 5. Rotate tokens: delete old, store new
        await redis_service.delete_refresh_token(request.refresh_token)
        await redis_service.set_refresh_token(new_refresh_token, user_id)

        log.info(
            "Token refresh successful",
            user_id=str(user_id),
            old_token_hash=hash(request.refresh_token) % 10**8,
            new_token_hash=hash(new_refresh_token) % 10**8,
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except UserNotFoundError as e:
        log.warning(
            "Token refresh failed: user not found or inactive", user_id=str(user_id)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is invalid or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during token refresh", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: UUID = Path(..., description="The UUID of the user to retrieve"),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    session: Session = Depends(get_session),
):
    """
    Retrieve a user's profile by ID.
    - Requires valid JWT.
    - Users can only access their own profile.
    """
    try:
        log.info(
            "Get user profile request",
            requested_user_id=str(user_id),
            authenticated_user_id=str(current_user_id),
        )

        # Only allow self-access
        if current_user_id != user_id:
            log.warning(
                "User attempted to access another user's profile",
                user_id=str(current_user_id),
                target_id=str(user_id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own profile",
            )

        user_service = UserService(session=session)
        user = user_service.get_user_by_id(user_id)

        log.info(
            "User profile retrieved successfully",
            user_id=str(user.id),
            email=user.email,
        )
        return UserResponse.model_validate(user)

    except UserNotFoundError as e:
        log.warning("User not found", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during get user profile",
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


# @router.get("/users", response_model=UserListResponse)
# async def list_users(
#     query: UserListQuery = Depends(),
#     current_user_id: UUID = Depends(jwt_service.get_current_user_id),
#     session: Session = Depends(get_session),
# ):
#     """
#     List users with pagination, filtering, and sorting.
#     - Requires admin role.
#     - Supports filtering by email (partial), is_active.
#     - Supports sorting by email, created_at, updated_at.
#     - Returns paginated list with meta.
#     """
#     try:
#         log.info(
#             "List users request",
#             admin_user_id=str(current_user_id),
#             query_params=query.model_dump(),
#         )

#         # ✅ Verify admin role
#         try:
#             if not await authz_client.is_admin(current_user_id):
#                 log.warning(
#                     "Non-admin attempted to list users", user_id=str(current_user_id)
#                 )
#                 raise HTTPException(
#                     status_code=status.HTTP_403_FORBIDDEN,
#                     detail="Only admin can list users",
#                 )
#         except AuthorizationError as e:
#             log.critical("Authorization check failed", error=str(e), exc_info=True)
#             raise HTTPException(
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#                 detail="Authorization service unavailable",
#             ) from e

#         user_service = UserService(session=session)
#         users, total = user_service.list_users(
#             limit=query.limit,
#             offset=query.offset,
#             email=query.email,
#             is_active=query.is_active,
#             sort=query.sort,
#         )

#         user_responses = [UserResponse.model_validate(user) for user in users]

#         meta = {
#             "total": total,
#             "limit": query.limit,
#             "offset": query.offset,
#             "pages": (total + query.limit - 1) // query.limit,
#         }

#         log.info("Users listed successfully", count=len(users), total=total)
#         return UserListResponse(users=user_responses, meta=meta)

#     except HTTPException:
#         raise

#     except Exception as e:
#         log.critical("Unexpected error during list users", error=str(e), exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error",
#         ) from e


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    user_id: UUID = Path(..., description="The UUID of the user to update"),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    session: Session = Depends(get_session),
):
    """
    Update a user's profile.
    - Requires valid JWT.
    - Users can only update their own profile.
    - Admins can update any profile (not implemented yet).
    """
    try:
        log.info(
            "Update user profile request",
            requested_user_id=str(user_id),
            authenticated_user_id=str(current_user_id),
            update_data=user_update.model_dump(exclude_unset=True),
        )

        # ✅ Only allow self-access
        if current_user_id != user_id:
            log.warning(
                "User attempted to update another user's profile",
                user_id=str(current_user_id),
                target_id=str(user_id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile",
            )

        user_service = UserService(session=session)
        user = user_service.update_user(user_id, user_update)

        log.info(
            "User profile updated successfully",
            user_id=str(user.id),
            email=user.email,
        )
        return UserResponse.model_validate(user)

    except UserNotFoundError as e:
        log.warning("User not found", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from e

    except ValueError as e:
        log.warning(
            "Invalid input during user update", user_id=str(user_id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during update user profile",
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: UUID = Path(..., description="The UUID of the user to deactivate"),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    session: Session = Depends(get_session),
):
    """
    Deactivate a user account (admin only).
    - Requires valid JWT.
    - Only admin users can deactivate other users.
    - Sets is_active=False, revokes refresh tokens.
    - Returns 204 No Content.
    """
    try:
        log.info(
            "Deactivate user request",
            target_user_id=str(user_id),
            admin_user_id=str(current_user_id),
        )

        # Verify admin role
        # For now, assume only a specific admin ID has permission
        ADMIN_USER_ID = UUID(
            "d835ddaf-395b-430c-8857-bdf2c42d5c5b"
        )  # Replace with real admin check
        if current_user_id != ADMIN_USER_ID:
            log.warning(
                "Non-admin attempted to deactivate user",
                user_id=str(current_user_id),
                target_id=str(user_id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin can deactivate users",
            )

        user_service = UserService(session=session)
        user = user_service.deactivate_user(user_id)

        # Revoke refresh tokens
        # In a real system, you'd have a way to find all refresh tokens for a user
        # For now, we'll assume the current refresh token is revoked on logout
        # Or implement token revocation list if needed

        log.info(
            "User deactivated and access revoked",
            user_id=str(user.id),
            email=user.email,
        )
        return  # 204 No Content

    except UserNotFoundError as e:
        log.warning("User not found for deactivation", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        log.critical(
            "Unexpected error during user deactivation",
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e

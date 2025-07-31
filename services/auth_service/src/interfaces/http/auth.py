from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from src.config.logger_config import log

from src.config.config import config
from src.core.exceptions import UserAlreadyExistsError, InvalidCredentialsError
from src.infrastructure.database.session import get_session
from src.infrastructure.services import redis_service, jwt_service
from src.application.user_service import UserService
from src.interfaces.http.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
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
        user_service = UserService(session=session)
        user_id = user_service.authenticate_user(user.email, user.password)

        # Generate tokens
        access_token = jwt_service.create_access_token(user_id)
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

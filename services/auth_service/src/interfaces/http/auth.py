from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from src.config.logger_config import log

from src.core.exceptions import UserAlreadyExistsError
from src.infrastructure.database.session import get_session
from src.application.user_service import UserService
from src.interfaces.http.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(user: UserCreate, session: Session = Depends(get_session)):
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

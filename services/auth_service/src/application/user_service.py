from uuid import UUID
from datetime import datetime

from passlib.context import CryptContext
from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from src.domain.models import User
from src.interfaces.http.schemas import UserCreate, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """
    Service class for handling user-related business logic.
    Encapsulates operations like user creation, validation, and retrieval.
    """

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def create_user(self, user: UserCreate) -> User:
        """
        Create a new user in the database.

        Args:
            user: UserCreate schema containing user data.

        Returns:
            The created User object.

        Raises:
            UserAlreadyExistsError: If a user with the given email already exists.
        """
        log.debug("Checking for existing user", email=user.email)
        existing = self.session.exec(
            select(User).where(User.email == user.email)
        ).first()
        if existing:
            log.warning("User with email already exists", email=user.email)
            raise UserAlreadyExistsError(f"User with email {user.email} already exists")

        log.debug("Hashing password for user", email=user.email)
        hashed_password = pwd_context.hash(user.password)

        db_user = User(
            email=user.email,
            hashed_password=hashed_password,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            address=user.address,
            date_of_birth=user.date_of_birth,
            is_active=True,
        )

        log.debug("Saving new user to database", email=user.email)
        self.session.add(db_user)
        try:
            self.session.commit()
            self.session.refresh(db_user)
            log.info(
                "User created successfully",
                user_id=str(db_user.id),
                email=db_user.email,
            )
            return db_user
        except Exception as e:
            log.error(
                "Failed to commit user to database", email=user.email, error=str(e)
            )
            self.session.rollback()
            raise

    def authenticate_user(self, email: str, password: str) -> UUID:
        """
        Authenticate a user by email and password.

        Args:
            email: User's email
            password: Raw password (will be hashed and compared)

        Returns:
            UUID of the authenticated user.

        Raises:
            InvalidCredentialsError: If email not found, password is incorrect, or user is inactive.
        """
        log.debug("Authenticating user", email=email)

        try:
            # Query user by email
            user = self.session.exec(select(User).where(User.email == email)).first()

            if not user:
                log.warning("Authentication failed: user not found", email=email)
                # Do NOT distinguish between "user not found" and "invalid password"
                # to prevent user enumeration attacks
                raise InvalidCredentialsError("Incorrect email or password")

            if not user.is_active:
                log.warning(
                    "Authentication failed: user is inactive", user_id=str(user.id)
                )
                raise InvalidCredentialsError("User account is inactive")

            # Verify password
            if not pwd_context.verify(password, user.hashed_password):
                log.warning(
                    "Authentication failed: invalid password", user_id=str(user.id)
                )
                raise InvalidCredentialsError("Incorrect email or password")

            log.info(
                "User authenticated successfully", user_id=str(user.id), email=email
            )
            return user.id

        except InvalidCredentialsError:
            # Re-raise known auth errors
            raise
        except Exception as e:
            # Catch unexpected errors (e.g., DB connection failure)
            log.critical(
                "Unexpected error during user authentication",
                email=email,
                error=str(e),
                exc_info=True,
            )
            raise InvalidCredentialsError(
                "Authentication failed due to internal error"
            ) from e

    def get_user_by_id(self, user_id: UUID) -> User:
        """
        Retrieve a user by ID and ensure they are active.

        Args:
            user_id: UUID of the user.

        Returns:
            User object.

        Raises:
            UserNotFoundError: If user does not exist or is inactive.
        """
        log.debug("Fetching user by ID", user_id=str(user_id))
        user = self.session.get(User, user_id)
        if not user:
            log.warning("User not found by ID", user_id=str(user_id))
            raise UserNotFoundError(f"User with ID {user_id} not found")

        if not user.is_active:
            log.warning("Inactive user access attempt", user_id=str(user_id))
            raise UserNotFoundError("User account is inactive")

        log.info(
            "User validated for token refresh", user_id=str(user_id), email=user.email
        )
        return user

    def validate_user_active(self, user_id: UUID) -> None:
        """
        Verify that a user exists and is active.
        Does not return the user object.

        Args:
            user_id: UUID of the user to validate.

        Raises:
            UserNotFoundError: If user does not exist or is inactive.
        """
        log.debug("Validating user is active", user_id=str(user_id))
        user = self.session.get(User, user_id)
        if not user:
            log.warning("User not found", user_id=str(user_id))
            raise UserNotFoundError(f"User with ID {user_id} not found")

        if not user.is_active:
            log.warning("User is inactive", user_id=str(user_id))
            raise UserNotFoundError("User account is inactive")

        log.info("User is valid and active", user_id=str(user_id))

    def update_user(self, user_id: UUID, user_update: UserUpdate) -> User:
        """
        Update a user's profile fields.
        Args:
            user_id: UUID of the user to update.
            user_update: UserUpdate schema with new data.
        Returns:
            Updated User object.
        Raises:
            UserNotFoundError: If user does not exist or is inactive.
        """
        log.debug(
            "Updating user",
            user_id=str(user_id),
            update_data=user_update.model_dump(exclude_unset=True),
        )
        user = self.session.get(User, user_id)
        if not user:
            log.warning("User not found for update", user_id=str(user_id))
            raise UserNotFoundError(f"User with ID {user_id} not found")

        if not user.is_active:
            log.warning("Inactive user update attempt", user_id=str(user_id))
            raise UserNotFoundError("User account is inactive")

        # Update only fields that are provided
        for key, value in user_update.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        # Update timestamp
        user.updated_at = datetime.utcnow()

        try:
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
            log.info(
                "User updated successfully", user_id=str(user.id), email=user.email
            )
            return user
        except Exception as e:
            log.error(
                "Failed to update user in database", user_id=str(user_id), error=str(e)
            )
            self.session.rollback()
            raise

    def deactivate_user(self, user_id: UUID) -> User:
        """
        Deactivate a user by setting is_active=False.
        Args:
            user_id: UUID of the user to deactivate.
        Returns:
            Updated User object.
        Raises:
            UserNotFoundError: If user does not exist.
        """
        log.debug("Deactivating user", user_id=str(user_id))
        user = self.session.get(User, user_id)
        if not user:
            log.warning("User not found for deactivation", user_id=str(user_id))
            raise UserNotFoundError(f"User with ID {user_id} not found")

        if not user.is_active:
            log.info("User already inactive", user_id=str(user_id))
            return user

        user.is_active = False
        user.updated_at = datetime.utcnow()

        try:
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
            log.info(
                "User deactivated successfully", user_id=str(user.id), email=user.email
            )
            return user
        except Exception as e:
            log.error(
                "Failed to deactivate user in database",
                user_id=str(user_id),
                error=str(e),
            )
            self.session.rollback()
            raise

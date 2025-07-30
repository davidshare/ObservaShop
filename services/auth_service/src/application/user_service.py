from sqlmodel import Session, select
from passlib.context import CryptContext
from src.config.logger_config import log

from src.core.exceptions import UserAlreadyExistsError
from src.domain.models import User
from src.interfaces.http.schemas import UserCreate

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

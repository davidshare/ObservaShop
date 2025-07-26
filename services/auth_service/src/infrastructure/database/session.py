from sqlmodel import create_engine, Session
from contextlib import contextmanager
from src.config.config import config
from loguru import logger
from typing import Generator

# Global engine instance
engine = None


def init_sqlmodel() -> None:
    """
    Initialize the SQLModel engine using configuration from `config`.
    Must be called before any database operations.
    """
    global engine
    if engine is not None:
        logger.warning(
            "Database engine already initialized. Skipping re-initialization."
        )
        return

    engine = create_engine(
        config.DATABASE_URL,
        echo=False,  # Set to True in development
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "sslmode": "disable"  # Change to "require" in production with SSL
        },
    )

    logger.info(
        "SQLModel engine initialized",
    )


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager that yields a database session.
    Ensures rollback on error and proper cleanup.

    Yields:
        Session: An active SQLModel session.

    Raises:
        RuntimeError: If engine is not initialized.
    """
    if engine is None:
        logger.critical("Database session requested, but engine is not initialized")
        raise RuntimeError(
            "Database engine not initialized. Call init_sqlmodel() first."
        )

    session = Session(engine)
    try:
        yield session
    except Exception as e:
        logger.error("Database session error, rolling back", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()

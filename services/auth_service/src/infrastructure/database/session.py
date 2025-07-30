from typing import Generator

from sqlmodel import Session, create_engine
from sqlalchemy import text

from src.config.config import config
from src.config.logger_config import log

# Global engine instance
engine = None


def init_sqlmodel() -> None:
    """
    Initialize the SQLModel engine using configuration from `config`.
    Must be called before any database operations.
    """
    global engine
    if engine is not None:
        log.warning("Database engine already initialized. Skipping re-initialization.")
        return

    try:
        engine = create_engine(
            config.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"sslmode": "disable"},
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("SQLModel engine initialized and connection verified")
    except Exception as e:
        log.critical(
            "Failed to initialize SQLModel engine", error=str(e), exc_info=True
        )
        raise RuntimeError("Failed to initialize database engine") from e


def get_session() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Ensures proper cleanup after use.

    Yields:
        Session: An active SQLModel session.

    Raises:
        RuntimeError: If engine is not initialized.
    """
    if engine is None:
        log.critical("Database session requested, but engine is not initialized")
        raise RuntimeError(
            "Database engine not initialized. Call init_sqlmodel() first."
        )

    session = Session(engine)
    try:
        yield session
    except Exception as e:
        log.error("Database session error, rolling back", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()

import os
import sys
from loguru import logger
from pathlib import Path


def configure_logger(
    env: str = "development",
    console_level: str = None,
    file_level: str = "DEBUG",
    error_file_level: str = "ERROR",
) -> None:
    """
    Configure the Loguru logger with console and file sinks for different log levels.

    Args:
        env: Environment ("development" or "production") to set default log levels.
        console_level: Log level for console output (overrides env-based default).
        file_level: Log level for general log file.
        error_file_level: Log level for error-specific log file.
    """
    # Remove default logger
    logger.remove()

    # Common log format
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | "
        "{module}:{function}:{line} - {message} | {extra}"
    )

    # Set default console log level based on environment
    default_console_level = "DEBUG" if env.lower() == "development" else "INFO"
    console_level = console_level or os.getenv(
        "CONSOLE_LOG_LEVEL", default_console_level
    )

    # Ensure log directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Console sink
    logger.add(
        sys.stderr,
        format=log_format,
        level=console_level.upper(),
        backtrace=True,
        diagnose=True,
        colorize=True,
    )

    # General file sink (all logs at file_level and above)
    general_log_file = log_dir / "app.log"
    logger.add(
        general_log_file,
        format=log_format,
        level=file_level.upper(),
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
    )

    # Error-specific file sink (ERROR and CRITICAL logs)
    error_log_file = log_dir / "error.log"
    logger.add(
        error_log_file,
        format=log_format,
        level=error_file_level.upper(),
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
    )

    logger.info(
        f"Logger configured for {env} environment",
        console_level=console_level,
        file_level=file_level,
        error_file_level=error_file_level,
    )


# Configure logger based on environment variables
configure_logger(
    env=os.getenv("ENV", "development"),
    console_level=os.getenv("CONSOLE_LOG_LEVEL"),
    file_level=os.getenv("FILE_LOG_LEVEL", "DEBUG"),
    error_file_level=os.getenv("ERROR_LOG_LEVEL", "ERROR"),
)

# Export the configured logger
log = logger

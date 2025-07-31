from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.logger_config import log
from src.infrastructure.database.session import init_sqlmodel
from src.infrastructure.services import redis_service  # Import shared instance
from src.interfaces.http.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler: runs on startup and shutdown.
    Initializes database engine and Redis connection.
    """
    log.info("Starting auth-service initialization")

    # Startup
    try:
        init_sqlmodel()
        log.info("Database engine initialized")

        await redis_service.connect()
        log.info("Redis connected")
    except Exception as e:
        log.critical("Failed to initialize dependencies", error=str(e), exc_info=True)
        raise

    yield

    # Shutdown
    await redis_service.close()
    log.info("auth-service shutdown complete")


app = FastAPI(
    title="auth-service",
    description="User authentication and session management for ObservaShop",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    return {"message": "Hello from auth-service!"}


@app.get("/health")
async def health_check():
    """Health check endpoint for liveness probe."""
    db_healthy = True  # Assume engine initialized
    redis_healthy = await redis_service.ping()  # ✅ Use public method

    return {
        "status": "healthy" if db_healthy and redis_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected",
    }


app.include_router(auth_router)

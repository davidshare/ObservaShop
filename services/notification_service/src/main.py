from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.config.logger_config import log
from src.infrastructure.database.session import init_sqlmodel
from src.infrastructure.services import redis_service
# from src.interfaces.http.notification import router as notification_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler: runs on startup and shutdown.
    Initializes database engine and Redis connection.
    """
    log.info("Starting notification-service initialization")

    # Startup
    try:
        init_sqlmodel()
        log.info("Database engine initialized")

        await redis_service.connect()
        log.info("Redis connected")
    except Exception as e:
        log.exception("Failed to initialize dependencies", error=str(e), exc_info=True)
        raise

    yield

    # Shutdown
    await redis_service.close()
    log.info("notification-service shutdown complete")


app = FastAPI(
    title="notification-service",
    description="Notification service for ObservaShop",
    version="0.1.0",
    lifespan=lifespan,
)  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from notification-service!"}


@app.get("/health")
async def health_check():
    """Health check endpoint for liveness probe."""
    db_healthy = True  # Assume engine initialized
    redis_healthy = await redis_service.ping()

    return {
        "status": "healthy" if db_healthy and redis_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected",
    }


# app.include_router(notification_router)

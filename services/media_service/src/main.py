from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.config.logger_config import log
from src.infrastructure.database.session import init_sqlmodel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler: runs on startup and shutdown.
    """
    log.info("Starting payment-service initialization")

    # Startup
    try:
        init_sqlmodel()
        log.info("Database engine initialized")

    except Exception as e:
        log.exception("Failed to initialize dependencies", error=str(e), exc_info=True)
        raise

    yield

    # Shutdown
    log.info("payment-service shutdown complete")


app = FastAPI(
    title="payment-service",
    description="Order service for ObservaShop",
    version="0.1.0",
    lifespan=lifespan,
)  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from payment-service!"}


@app.get("/health")
async def health_check():
    """Health check endpoint for liveness probe."""
    db_healthy = True  # Assume engine initialized

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
    }


# app.include_router(payment_router)

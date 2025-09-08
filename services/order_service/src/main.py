from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.config.logger_config import log
from src.infrastructure.database.session import init_sqlmodel
from src.infrastructure.services import redis_service
from src.interfaces.http.order import router as order_router
from shared.libs.observability.middleware import metrics_middleware
from shared.libs.observability.metrics import create_metrics_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler: runs on startup and shutdown.
    Initializes database engine and Redis connection.
    """
    log.info("Starting order-service initialization")

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
    log.info("order-service shutdown complete")


app = FastAPI(
    title="order-service",
    description="Order service for ObservaShop",
    version="0.1.0",
    lifespan=lifespan,
)  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from order-service!"}


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


app.middleware("http")(metrics_middleware)
app.include_router(order_router)
metrics_endpoint = create_metrics_endpoint()
app.add_api_route("/metrics", metrics_endpoint, name="metrics", include_in_schema=False)

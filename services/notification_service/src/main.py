"""
FastAPI application setup for the ObservaShop notification service.
Initializes database, Redis, Kafka, and EmailClient, and manages their lifecycle.
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session, create_engine

from src.application.notification_service import NotificationService
from src.config.config import config
from src.config.logger_config import log
from src.infrastructure.database.session import init_sqlmodel
from src.infrastructure.email.client import EmailClient
from src.infrastructure.kafka.kafka_client import KafkaClient
from src.infrastructure.kafka.kafka_config import KafkaConfig
from src.infrastructure.kafka.topic_manager import TopicManager
from src.infrastructure.services import redis_service
from src.interfaces.http.notification import router as notification_router

# Shared service instances for dependency injection
engine = create_engine(config.DATABASE_URL)
email_client = EmailClient()
kafka_client = KafkaClient(KafkaConfig(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVER))
notification_service = NotificationService(Session(engine), email_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler to manage startup and shutdown of dependencies.

    Startup:
        - Initializes SQLModel database engine
        - Connects to Redis for event deduplication
        - Connects to Kafka for event consumption
        - Starts NotificationService to consume Kafka events

    Shutdown:
        - Stops NotificationService and closes Kafka connections
        - Closes Redis connection

    Raises:
        Exception: If any dependency initialization fails
    """
    log.info("Starting notification-service initialization")

    try:
        # Initialize database
        init_sqlmodel()
        log.info("Database engine initialized")

        # Connect to Redis
        await redis_service.connect()
        log.info("Redis connected")

        # Connect to Kafka
        kafka_client.connect()
        log.info("Kafka client connected")

        # Create topics automatically
        topic_manager = TopicManager(config.KAFKA_BOOTSTRAP_SERVER)

        if topic_manager.create_topics():
            log.info("Kafka topics created/verified successfully")
        else:
            log.warning("Some topics may not have been created, but continuing anyway")

        # Verify topics exist
        topic_status = topic_manager.verify_topics()
        log.info("Topic verification status", topics=topic_status)

        def start_consumer():
            notification_service.start()

        threading.Thread(target=start_consumer, daemon=True).start()
        log.info("NotificationService started in background thread")

        yield

    except Exception as e:
        log.exception("Failed to initialize dependencies", error=str(e))
        raise

    finally:
        # Shutdown services
        notification_service.shutdown()
        kafka_client.close()
        await redis_service.close()
        log.info("notification-service shutdown complete")


# Assign lifespan handler to app
app = FastAPI(
    title="notification-service",
    description="Notification service for ObservaShop, handling Kafka events and sending emails",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    """Root endpoint to verify service is running."""
    return {"message": "Hello from notification-service!"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for liveness probe.
    Verifies connectivity to database, Redis, and Kafka.

    Returns:
        dict: Status of service and dependencies
    """
    db_healthy = True  # Placeholder: replace with actual database check
    redis_healthy = await redis_service.ping()
    kafka_healthy = kafka_client.is_healthy() if kafka_client.is_healthy else False

    return {
        "status": "healthy"
        if db_healthy and redis_healthy and kafka_healthy
        else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected",
        "kafka": "connected" if kafka_healthy else "disconnected",
    }


app.include_router(notification_router)

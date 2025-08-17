from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class JWTConfig(BaseModel):
    """JWT Config needed for authorization"""

    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int


class Config(BaseSettings):
    """Config settings for notification service"""

    # Postgres Database
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVER: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP_ID: str = "notification-service-group"

    # External Notification Services
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str

    # Redis (for rate limiting and caching)
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_TTL: int = 3600  # 1 hour TTL for rate limiting

    # JWT Configuration
    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Service URLs for inter-service communication
    AUTH_SERVICE_URL: str = "http://auth-service:8000"
    ORDER_SERVICE_URL: str = "http://order-service:8003"

    # Internal shared secret for service-to-service authentication
    INTERNAL_SHARED_SECRET: str

    @property
    def DATABASE_URL(self) -> str:
        """Method to return Database URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}/{self.POSTGRES_DB}"

    @property
    def jwt_config(self) -> JWTConfig:
        """Method to return JWT Config"""
        return JWTConfig(
            JWT_SECRET=self.JWT_SECRET,
            ALGORITHM=self.ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES=self.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env.notification",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

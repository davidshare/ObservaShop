from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class JWTConfig(BaseModel):
    """JWT Config needed for authorisation"""

    JWT_SECRET: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int


class Config(BaseSettings):
    # JWT
    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Postgres
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_TTL: int = 604800

    # Kafka
    KAFKA_BOOTSTRAP_SERVER: str = "kafka:9092"

    # Shared config
    INTERNAL_SHARED_SECRET: str

    @property
    def DATABASE_URL(self) -> str:
        """Method to return Database url"""
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
        env_file=Path(__file__).resolve().parent.parent.parent / ".env.analytics",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class JWTConfig(BaseModel):
    """JWT Config needed for authorisation"""

    secret_key: str
    algorithm: str = "HS256"


class Config(BaseSettings):
    """Config settings"""

    # JWT
    JWT_SECRET: str
    ALGORITHM: str = "HS256"

    # Postgres
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Kafka
    KAFKA_BOOTSTRAP_SERVER: str = "kafka:9092"

    # Auth Service URL
    AUTH_SERVICE_URL: str = "http://localhost:8010"

    @property
    def DATABASE_URL(self) -> str:
        """Method to return Database url"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}/{self.POSTGRES_DB}"

    @property
    def jwt_config(self) -> JWTConfig:
        """Method to return JWT Config"""
        return JWTConfig(
            secret_key=self.JWT_SECRET,
            algorithm=self.ALGORITHM,
        )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env.authz",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

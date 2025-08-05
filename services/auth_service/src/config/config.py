from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class JWTConfig(BaseModel):
    JWT_SECRET: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int


class Config(BaseSettings):
    # JWT
    JWT_SECRET: str
    JWT_AUDIENCE: str
    JWT_ISSUER: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Postgres
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_TTL: int = 604800

    # External Service ENVs
    INTERNAL_SHARED_SECRET: str
    AUTHZ_SERVICE_URL: str

    @property
    def DATABASE_URL(self) -> str:
        """Returns the database string"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}/{self.POSTGRES_DB}"

    @property
    def jwt_config(self) -> JWTConfig:
        """Returns JWTConfig"""
        return JWTConfig(
            JWT_SECRET=self.JWT_SECRET,
            ALGORITHM=self.ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES=self.ACCESS_TOKEN_EXPIRE_MINUTES,
            REFRESH_TOKEN_EXPIRE_DAYS=self.REFRESH_TOKEN_EXPIRE_DAYS,
        )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env.auth",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

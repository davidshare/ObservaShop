from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator
from typing import Optional


class Config(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: str
    JWT_SECRET: str
    JWT_AUDIENCE: str
    JWT_ISSUER: str
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file="services/auth_service/.env.auth",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

"""
Centralized service instances for the auth-service.
Ensures single, shared instances of RedisService, JWTService, etc.
"""

from src.infrastructure.redis.redis import RedisService
from src.infrastructure.jwt.jwt import JWTService
from src.config.config import config

# Single shared instances (singleton pattern)
redis_service = RedisService()
jwt_service = JWTService(config=config.jwt_config)

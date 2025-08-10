"""
Centralized service instances for the product-service.
Ensures single, shared instances of RedisService, JWTService, etc.
"""

from src.infrastructure.redis.redis import RedisService
from src.infrastructure.jwt.jwt import JWTService
from src.config.config import config

# Single shared instances
redis_service = RedisService()
jwt_service = JWTService(config=config.jwt_config)

"""
Centralized service instances for the authz-service.
Ensures single, shared instances of RedisService, JWTService, etc.
"""

from src.infrastructure.redis import RedisService
from src.infrastructure.jwt import JWTService
from src.config.config import config

# Single shared instances
redis_service = RedisService()
jwt_service = JWTService(config=config.jwt_config)

"""
Centralized service instances for the product-service.
Ensures single, shared instances of JWTService, etc.
"""

from src.infrastructure.jwt.jwt import JWTService
from src.config.config import config

# Single shared instances
jwt_service = JWTService(config=config.jwt_config)

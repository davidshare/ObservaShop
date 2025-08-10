from typing import Dict, Any
from uuid import UUID
from httpx import AsyncClient, ConnectTimeout, ReadTimeout
from src.config.logger_config import log
from src.core.exceptions import (
    ProductNotFoundError,
    InvalidInputError,
    ExternalServiceError,
)
from src.infrastructure.services import redis_service


class ProductClient:
    """
    Client for interacting with the product-service.
    Handles product validation, stock checks, and caching.
    Uses RedisService for cache operations with fail-soft behavior.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        """
        Initialize the client with the product-service base URL.
        Args:
            base_url: Base URL of the product-service (e.g., http://localhost:8012)
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get_product_from_cache(self, product_id: UUID) -> Dict[str, Any]:
        """
        Retrieve product data from Redis cache.
        Args:
            product_id: UUID of the product to retrieve.
        Returns:
            Product data if found and active, None otherwise.
        """
        try:
            cached = await redis_service.get_product(product_id)
            if cached:
                if not cached.get("is_active", True):
                    log.warning(
                        "Cached product is inactive", product_id=str(product_id)
                    )
                    raise ProductNotFoundError(
                        f"Product with ID {product_id} is inactive"
                    )
                log.debug("Product cache hit", product_id=str(product_id))
                return cached
            log.debug("Product cache miss", product_id=str(product_id))
        except Exception as e:
            log.warning("Product cache read failed", error=str(e))
        return None

    async def _get_product_from_database(
        self, product_id: UUID, jwt_token: str
    ) -> Dict[str, Any]:
        """
        Fetch product data from the product-service via HTTP.
        Args:
            product_id: UUID of the product to retrieve.
            jwt_token: JWT token for authentication.
        Returns:
            Product data from the service.
        Raises:
            ProductNotFoundError: If product is not found or is inactive.
            ExternalServiceError: If the service is unreachable or returns an error.
        """
        url = f"{self.base_url}/products/{product_id}"
        headers = {"accept": "application/json", "Authorization": f"Bearer {jwt_token}"}

        async with AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 404:
                    log.warning(
                        "Product not found in product-service",
                        product_id=str(product_id),
                    )
                    raise ProductNotFoundError(
                        f"Product with ID {product_id} not found"
                    )
                if response.status_code == 401:
                    log.warning("Unauthorized access to product-service", url=url)
                    raise ExternalServiceError(
                        service_name="product-service",
                        message="Unauthorized: Invalid or missing JWT",
                    )
                if response.status_code == 403:
                    log.warning("Forbidden access to product-service", url=url)
                    raise ExternalServiceError(
                        service_name="product-service",
                        message="Forbidden: Insufficient permissions",
                    )
                response.raise_for_status()
                data = response.json()

                if not data.get("is_active", True):
                    log.warning(
                        "Product from service is inactive", product_id=str(product_id)
                    )
                    raise ProductNotFoundError(
                        f"Product with ID {product_id} is inactive"
                    )

                # Cache for 5 minutes
                try:
                    await redis_service.set_product(product_id, data, ttl=300)
                except Exception as e:
                    log.warning("Product cache write failed", error=str(e))
                    # Fail-soft: don't block on cache failure

                log.info("Product fetched from database", product_id=str(product_id))
                return data

            except ConnectTimeout:
                log.critical("Connection timeout to product-service", url=url)
                raise ExternalServiceError(
                    "product-service", "Connection timeout"
                ) from ConnectTimeout()
            except ReadTimeout:
                log.critical("Read timeout from product-service", url=url)
                raise ExternalServiceError(
                    "product-service", "Read timeout"
                ) from ReadTimeout()
            except Exception as e:
                log.critical(
                    "Unexpected error fetching product",
                    product_id=str(product_id),
                    error=str(e),
                )
                raise ExternalServiceError(
                    "product-service", "Unexpected error during HTTP request"
                ) from e

    async def get_product(self, product_id: UUID, jwt_token: str) -> Dict[str, Any]:
        """
        Get product details from cache first, then fall back to database.
        Args:
            product_id: UUID of the product to retrieve.
            jwt_token: JWT token for authenticating with the product-service.
        Returns:
            Product data (id, name, price, stock, category_id, is_active).
        Raises:
            ProductNotFoundError: If product does not exist or is inactive.
            ExternalServiceError: If product-service is unreachable or returns 4xx/5xx.
        """
        log.debug("Fetching product", product_id=str(product_id))

        # Validate input
        if not product_id:
            raise InvalidInputError("Product ID is required")

        # Try cache first
        cached = await self._get_product_from_cache(product_id)
        if cached:
            return cached

        # Fallback to database
        return await self._get_product_from_database(product_id, jwt_token)

    async def check_stock(
        self, product_id: UUID, quantity: int, jwt_token: str
    ) -> bool:
        """
        Check if a product has sufficient stock.
        Args:
            product_id: UUID of the product.
            quantity: Quantity to check.
            jwt_token: JWT token for authentication.
        Returns:
            True if stock is sufficient, False otherwise.
        """
        if quantity <= 0:
            raise InvalidInputError("Quantity must be greater than zero")

        try:
            product = await self.get_product(product_id, jwt_token)
            has_stock = product.get("stock", 0) >= quantity
            log.debug(
                "Stock check result",
                product_id=str(product_id),
                requested=quantity,
                available=product.get("stock"),
                result=has_stock,
            )
            return has_stock
        except ProductNotFoundError:
            return False
        except ExternalServiceError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error during stock check",
                product_id=str(product_id),
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="product-service",
                message="Failed to check stock due to internal error",
            ) from e

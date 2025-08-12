# src/infrastructure/clients/order_client.py

from typing import Any, Dict
from uuid import UUID

from httpx import AsyncClient, ConnectTimeout, HTTPStatusError, ReadTimeout

from src.config.logger_config import log
from src.core.exceptions import (
    ExternalServiceError,
    InsufficientStockError,
    InvalidInputError,
    OrderNotFoundError,
    PaymentProcessingError,
    OrderStatusTransitionError,
)


class OrderClient:
    """
    Client for interacting with the order-service.
    Handles order validation, status checks, and proper error mapping.
    Designed to work behind Kong API gateway with JWT validation.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        """
        Initialize the client with the order-service base URL.
        Args:
            base_url: Base URL of the order-service (e.g., http://order-service:8003)
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _make_request(
        self, method: str, url: str, headers: Dict[str, str] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with error handling, timeout, and structured logging.
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            headers: Additional headers (e.g., Authorization)
            **kwargs: Additional arguments passed to httpx
        Returns:
            JSON response from the service
        Raises:
            OrderNotFoundError: If order does not exist
            InsufficientStockError: If product stock is insufficient
            PaymentProcessingError: If business logic prevents payment
            ExternalServiceError: If order-service is unreachable
            InvalidInputError: If request data is invalid
        """
        if headers is None:
            headers = {}
        headers["accept"] = "application/json"

        async with AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()

            except ConnectTimeout:
                log.critical("Connection timeout to order-service", url=url)
                raise ExternalServiceError(
                    service_name="order-service", message="Connection timeout"
                ) from None

            except ReadTimeout:
                log.critical("Read timeout from order-service", url=url)
                raise ExternalServiceError(
                    service_name="order-service", message="Read timeout"
                ) from None

            except HTTPStatusError as e:
                status_code = e.response.status_code
                response_text = e.response.text

                log.warning(
                    "HTTP error from order-service",
                    url=url,
                    status_code=status_code,
                    response=response_text[:500],  # Truncate long responses
                )

                if status_code == 400:
                    raise InvalidInputError(
                        f"Invalid request to order-service: {response_text}"
                    ) from e

                if status_code == 401:
                    raise ExternalServiceError(
                        service_name="order-service",
                        message="Unauthorized: JWT validation failed at order-service",
                    ) from e

                if status_code == 403:
                    raise ExternalServiceError(
                        service_name="order-service",
                        message="Forbidden: Insufficient permissions",
                    ) from e

                if status_code == 404:
                    raise OrderNotFoundError(
                        f"Order not found in order-service: {response_text}"
                    ) from e

                if status_code == 409:
                    if "InsufficientStockError" in response_text:
                        raise InsufficientStockError(response_text) from e
                    raise PaymentProcessingError(f"Conflict: {response_text}") from e

                if status_code == 422:
                    raise InvalidInputError(
                        f"Validation error in order-service: {response_text}"
                    ) from e

                if 500 <= status_code < 600:
                    raise ExternalServiceError(
                        service_name="order-service",
                        message=f"Internal server error: {status_code}",
                    ) from e

                raise ExternalServiceError(
                    service_name="order-service",
                    message=f"Unexpected status {status_code}: {response_text}",
                ) from e

            except Exception as e:
                log.critical(
                    "Unexpected error calling order-service", url=url, error=str(e)
                )
                raise ExternalServiceError(
                    service_name="order-service",
                    message="Unexpected error during order validation",
                ) from e

    async def get_order(self, order_id: UUID, jwt_token: str) -> Dict[str, Any]:
        """
        Get order details from order-service.
        Args:
            order_id: UUID of the order to retrieve.
        Returns:
            Order data (id, user_id, status, total_amount, etc.)
        Raises:
            OrderNotFoundError: If order does not exist.
            ExternalServiceError: If order-service is unreachable.
            InvalidInputError: If input is invalid.
        """
        log.debug("Fetching order from order-service", order_id=str(order_id))

        if not order_id:
            raise InvalidInputError("Order ID is required")

        url = f"{self.base_url}/orders/{order_id}"
        headers = {"accept": "application/json", "Authorization": f"Bearer {jwt_token}"}

        try:
            data = await self._make_request("GET", url, headers=headers)
            log.info("Order fetched successfully", order_id=str(order_id))
            return data

        except (
            OrderNotFoundError,
            InvalidInputError,
            ExternalServiceError,
            InsufficientStockError,
        ):
            raise

        except Exception as e:
            log.critical(
                "Unexpected error during order fetch",
                order_id=str(order_id),
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="order-service",
                message="Failed to fetch order due to internal error",
            ) from e

    async def check_order_status(
        self, order_id: UUID, required_status: str, jwt_token: str
    ) -> bool:
        """
        Check if an order has a specific status.
        Args:
            order_id: UUID of the order.
            required_status: Status to check (e.g., 'pending').
        Returns:
            True if status matches, False otherwise.
        """
        try:
            order = await self.get_order(order_id, jwt_token=jwt_token)
            return order.get("status") == required_status
        except Exception as e:
            log.warning(
                "Failed to check order status", order_id=str(order_id), error=str(e)
            )
            return False

    async def update_order_status(
        self, order_id: UUID, status: str, auth_header: str
    ) -> Dict[str, Any]:
        """
        Update the status of an existing order.
        Args:
            order_id: UUID of the order to update.
            status: New status (e.g., 'confirmed', 'shipped').
            auth_header: Authorization header (e.g., "Bearer <token>")
        Returns:
            updated order data.
        Raises:
            OrderNotFoundError: If order does not exist.
            OrderStatusTransitionError: If the transition is invalid.
            ExternalServiceError: If order-service is unreachable.
        """
        log.info(
            "Updating order status via order-service",
            order_id=str(order_id),
            status=status,
        )

        if not order_id:
            raise InvalidInputError("Order ID is required")
        if not status:
            raise InvalidInputError("Status is required")

        url = f"{self.base_url}/orders/{order_id}"
        headers = {
            "accept": "application/json",
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }
        json_data = {"status": status}

        try:
            data = await self._make_request(
                "PATCH", url, headers=headers, json=json_data
            )
            log.info(
                "Order status updated successfully",
                order_id=str(order_id),
                status=status,
            )
            return data

        except OrderStatusTransitionError:
            raise
        except ExternalServiceError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error during order status update",
                order_id=str(order_id),
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="order-service",
                message="Failed to update order status due to internal error",
            ) from e

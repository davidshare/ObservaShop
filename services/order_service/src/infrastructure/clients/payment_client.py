from typing import Any, Dict
from uuid import UUID

from httpx import AsyncClient, ConnectTimeout, HTTPStatusError, ReadTimeout

from src.config.logger_config import log
from src.core.exceptions import (
    ExternalServiceError,
    IdempotencyError,
    InvalidInputError,
    PaymentProcessingError,
)


class PaymentClient:
    """
    Client for interacting with the payment-service.
    Uses small, focused methods for maintainability.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def create_payment(
        self,
        order_id: UUID,
        amount: float,
        currency: str = "USD",
        payment_method: str = "mock",
        idempotency_key: str = None,
        auth_token: str = None,
    ) -> Dict[str, Any]:
        """
        Create a payment for an order.
        Orchestrates validation, request building, and error handling.
        """
        log.info(
            "Creating payment via payment-service",
            order_id=str(order_id),
            amount=amount,
        )

        self._validate_inputs(order_id, amount, idempotency_key, auth_token)

        url, headers, json_body = self._build_payment_request(
            order_id, amount, currency, payment_method, idempotency_key, auth_token
        )

        return await self._execute_request(url, headers, json_body)

    def _validate_inputs(
        self, order_id: UUID, amount: float, idempotency_key: str, auth_token: str
    ):
        """Validate required inputs."""
        if not order_id:
            raise InvalidInputError("Order ID is required")
        if amount <= 0:
            raise InvalidInputError("Amount must be greater than zero")
        if not idempotency_key:
            raise InvalidInputError("Idempotency-Key is required")
        if not auth_token:
            raise InvalidInputError("Authorization token is required")

    def _build_payment_request(
        self,
        order_id: UUID,
        amount: float,
        currency: str,
        payment_method: str,
        idempotency_key: str,
        auth_token: str,
    ) -> tuple[str, dict, dict]:
        """Build URL, headers, and JSON body for the request."""
        url = f"{self.base_url}/payments"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {auth_token}",
            "Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        }
        json_body = {
            "order_id": str(order_id),
            "amount": float(amount),
            "currency": currency,
            "payment_method": payment_method,
        }
        return url, headers, json_body

    async def _execute_request(
        self, url: str, headers: dict, json_body: dict
    ) -> Dict[str, Any]:
        """
        Execute the HTTP request with error handling.
        This is the only method that makes the actual call.
        """
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=json_body)
                response.raise_for_status()
                data = response.json()
                log.info("Payment created successfully", payment_id=data.get("id"))
                return data
        except TypeError as e:
            if "not JSON serializable" in str(e):
                log.critical(
                    "Non-serializable data in request body", url=url, data=json_body
                )
                raise InvalidInputError(
                    "Request contains non-serializable data (e.g., Decimal, UUID)"
                ) from e
            raise

        except ConnectTimeout:
            return self._handle_connect_timeout(url)

        except ReadTimeout:
            return self._handle_read_timeout(url)

        except HTTPStatusError as e:
            return self._handle_http_error(e, url)

        except Exception as e:
            log.critical(
                "Unexpected error calling payment-service", url=url, error=str(e)
            )
            raise ExternalServiceError(
                service_name="payment-service",
                message="Unexpected error during payment processing",
            ) from e

    def _handle_connect_timeout(self, url: str) -> None:
        log.critical("Connection timeout to payment-service", url=url)
        raise ExternalServiceError(
            service_name="payment-service", message="Connection timeout"
        )

    def _handle_read_timeout(self, url: str) -> None:
        log.critical("Read timeout from payment-service", url=url)
        raise ExternalServiceError(
            service_name="payment-service", message="Read timeout"
        )

    def _handle_http_error(self, e: HTTPStatusError, url: str) -> None:
        status_code = e.response.status_code
        response_text = e.response.text

        log.warning(
            "HTTP error from payment-service",
            url=url,
            status_code=status_code,
            response=response_text[:500],
        )

        if status_code == 400:
            raise InvalidInputError(
                f"Invalid request to payment-service: {response_text}"
            )

        if status_code == 401:
            raise ExternalServiceError(
                service_name="payment-service",
                message="Unauthorized: JWT validation failed",
            )

        if status_code == 403:
            raise ExternalServiceError(
                service_name="payment-service",
                message="Forbidden: Insufficient permissions",
            )

        if status_code == 404:
            raise PaymentProcessingError(f"Payment endpoint not found: {response_text}")

        if status_code == 409:
            if "IdempotencyError" in response_text:
                raise IdempotencyError(response_text)
            raise PaymentProcessingError(f"Conflict: {response_text}")

        if status_code == 422:
            raise InvalidInputError(
                f"Validation error in payment-service: {response_text}"
            )

        if 500 <= status_code < 600:
            raise ExternalServiceError(
                service_name="payment-service",
                message=f"Internal server error: {status_code}",
            )

        raise ExternalServiceError(
            service_name="payment-service",
            message=f"Unexpected status {status_code}: {response_text}",
        )

from uuid import UUID, uuid4

from src.config.logger_config import log


class PaymentClient:
    """
    Mocked PaymentClient for development.
    Simulates successful payment in non-production environments.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def create_payment(self, order_id: UUID, amount: float) -> dict:
        """
        Simulate a successful payment.
        In production, this would call the real payment-service.
        """
        log.info("Mock payment processed", order_id=str(order_id), amount=amount)
        return {
            "success": True,
            "transaction_id": str(uuid4()),
            "message": "Payment successful",
        }

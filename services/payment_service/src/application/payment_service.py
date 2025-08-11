# src/application/payment_service.py

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID
from sqlmodel import Session, select
from src.config.logger_config import log
from src.core.exceptions import (
    PaymentNotFoundError,
    PaymentAlreadyExistsError,
    InvalidInputError,
    IdempotencyError,
    PaymentProcessingError,
    DatabaseError,
    ExternalServiceError,
    OrderStatusTransitionError,
)
from src.domain.models import Payment
from src.interfaces.http.schemas import PaymentCreate, PaymentUpdate
from src.infrastructure.clients.order_client import OrderClient


class PaymentService:
    """
    Service class for handling payment-related business logic.
    Encapsulates CRUD operations for payments with ownership, permission checks,
    idempotency, and integration with order-service.
    No Kafka integration — for future extension.
    """

    def __init__(self, session: Session, order_client: OrderClient):
        """
        Initialize the service with a database session and order client.
        Args:
            session: SQLModel session for database operations.
            order_client: Client to interact with order-service for validation.
        """
        self.session = session
        self.order_client = order_client

    async def get_payment_by_id(
        self,
        payment_id: UUID,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Payment:
        """
        Retrieve a payment by ID with ownership/permission checks.
        Args:
            payment_id: UUID of the payment to retrieve.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Payment object.
        Raises:
            PaymentNotFoundError: If payment does not exist or user is not authorized.
        """
        log.debug(
            "Fetching payment by ID", payment_id=str(payment_id), user_id=str(user_id)
        )

        try:
            payment = self.session.get(Payment, payment_id)
        except Exception as e:
            log.critical(
                "Database error during payment lookup",
                payment_id=str(payment_id),
                error=str(e),
            )
            raise DatabaseError(
                "Failed to retrieve payment due to internal error"
            ) from e

        if not payment:
            log.warning("Payment not found", payment_id=str(payment_id))
            raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")

        if is_superadmin or "payment:read:all" in permissions:
            return payment

        try:
            order = await self.order_client.get_order(payment.order_id)
            if order["user_id"] != str(user_id):
                raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")
        except Exception as e:
            raise PaymentNotFoundError(f"Payment with ID {payment_id} not found") from e

        if "payment:read" in permissions:
            return payment

        log.warning(
            "Payment access denied: insufficient permissions",
            payment_id=str(payment_id),
            requester_id=str(user_id),
            permissions=list(permissions),
        )
        raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")

    def list_payments(
        self,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
        limit: int = 10,
        offset: int = 0,
        sort: str = "created_at:desc",
        status: Optional[str] = None,
        order_id: Optional[UUID] = None,
    ) -> Tuple[List[Payment], int]:
        """
        List payments with pagination, sorting, and permission-based access.
        Args:
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
            limit: Number of payments to return.
            offset: Number of payments to skip.
            sort: Sort by field:direction (e.g., created_at:desc).
            status: Optional filter by payment status.
            order_id: Optional filter by order ID.
        Returns:
            Tuple of (list of payments, total count).
        """
        log.debug("Listing payments", user_id=str(user_id), is_superadmin=is_superadmin)

        try:
            if is_superadmin or "payment:list:all" in permissions:
                query = select(Payment)
            else:
                query = select(Payment).where(Payment.order_id == user_id)

            if status:
                query = query.where(Payment.status == status)
            if order_id:
                query = query.where(Payment.order_id == order_id)

            sort_field, direction = (
                sort.split(":") if ":" in sort else ("created_at", "desc")
            )
            allowed_sort_fields = ["created_at", "updated_at", "amount", "status"]
            if sort_field not in allowed_sort_fields:
                raise InvalidInputError(f"Invalid sort field: {sort_field}")
            if direction not in ["asc", "desc"]:
                raise InvalidInputError(f"Invalid sort direction: {direction}")

            column = getattr(Payment, sort_field)
            if direction == "desc":
                column = column.desc()
            query = query.order_by(column)

            count_query = query.with_only_columns(Payment.id).order_by()
            total = len(self.session.exec(count_query).all())

            query = query.offset(offset).limit(limit)
            payments = self.session.exec(query).all()

            log.info("Payments listed successfully", count=len(payments), total=total)
            return payments, total

        except InvalidInputError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error during list payments", error=str(e), exc_info=True
            )
            raise DatabaseError("Failed to list payments due to internal error") from e

    async def create_payment(
        self,
        payment_create: PaymentCreate,
        idempotency_key: Optional[str] = None,
        jwt_token: str = None,
    ) -> Payment:
        """
        Create a new payment.
        Args:
            payment_create: PaymentCreate schema with new data.
            idempotency_key: Optional key to prevent duplicate payments.
        Returns:
            Created Payment object.
        Raises:
            InvalidInputError: If input data is invalid.
            IdempotencyError: If idempotency key is reused.
            PaymentAlreadyExistsError: If a payment already exists for the order.
            PaymentProcessingError: If order is invalid or gateway fails.
            ExternalServiceError: If order-service is unreachable.
            DatabaseError: If there is a database-level error.
        """
        log.info(
            "Creating payment",
            order_id=str(payment_create.order_id),
            amount=str(payment_create.amount),
            idempotency_key=idempotency_key,
        )

        if payment_create.amount <= 0:
            raise InvalidInputError("Payment amount must be greater than zero")
        if not payment_create.payment_method:
            raise InvalidInputError("Payment method is required")
        if not payment_create.currency:
            raise InvalidInputError("Currency is required")

        if idempotency_key:
            try:
                existing = self.session.exec(
                    select(Payment).where(Payment.transaction_id == idempotency_key)
                ).first()
                if existing:
                    log.warning(
                        "Idempotency key reused", idempotency_key=idempotency_key
                    )
                    raise IdempotencyError(
                        f"Payment with idempotency key {idempotency_key} already exists"
                    )
            except Exception as e:
                log.critical("Database error during idempotency check", error=str(e))
                raise DatabaseError(
                    "Failed to check idempotency due to internal error"
                ) from e
        else:
            raise InvalidInputError("Idempotency-Key header is required")

        try:
            order = await self.order_client.get_order(
                payment_create.order_id, jwt_token=jwt_token
            )
            if order["status"] != "pending":
                raise PaymentProcessingError(
                    f"Cannot pay for order in '{order['status']}' status"
                )
        except Exception as e:
            log.warning("Order validation failed", error=str(e))
            raise PaymentProcessingError("Failed to validate order") from e

        existing_payment = self.session.exec(
            select(Payment).where(Payment.order_id == payment_create.order_id)
        ).first()
        if existing_payment:
            log.warning(
                "Payment already exists for order",
                order_id=str(payment_create.order_id),
            )
            raise PaymentAlreadyExistsError(
                f"Payment already exists for order {payment_create.order_id}"
            )

        success = self._mock_payment_gateway(payment_create.amount)
        if not success:
            log.warning(
                "Mock payment gateway failed", order_id=str(payment_create.order_id)
            )
            raise PaymentProcessingError(
                "Mock payment gateway: failed to process payment"
            )

        transaction_id = idempotency_key
        status = "succeeded"

        payment = Payment(
            order_id=payment_create.order_id,
            amount=payment_create.amount,
            currency=payment_create.currency,
            status=status,
            payment_method=payment_create.payment_method,
            transaction_id=transaction_id,
        )

        try:
            self.session.add(payment)
            self.session.commit()
            self.session.refresh(payment)

            log.info(
                "Payment created successfully",
                payment_id=str(payment.id),
                status=payment.status,
                transaction_id=transaction_id,
            )

            try:
                await self.order_client.update_order_status(
                    order_id=payment.order_id,
                    status="confirmed",
                    auth_header=f"Bearer {jwt_token}",
                )
            except OrderStatusTransitionError as e:
                log.critical("Order cannot be confirmed", error=str(e))
                # Handle error: alert, retry, or manual intervention
            except ExternalServiceError as e:
                log.critical("Failed to update order status", error=str(e))
            return payment

        except Exception as e:
            log.critical(
                "Unexpected error during payment creation", error=str(e), exc_info=True
            )
            raise DatabaseError("Failed to create payment due to internal error") from e

    def _mock_payment_gateway(self, amount: Decimal) -> bool:
        """
        Simulates an external payment gateway.
        - Always succeeds for amounts < 1000
        - 90% success rate for higher amounts
        - 5% chance of timeout
        """
        import random

        if amount < 1000:
            return True
        if random.random() < 0.05:
            raise TimeoutError("Mock gateway timed out")
        return random.random() > 0.1

    async def update_payment_status(
        self,
        payment_id: UUID,
        payment_update: PaymentUpdate,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Payment:
        """
        Update the status of an existing payment.
        Args:
            payment_id: UUID of the payment to update.
            payment_update: PaymentUpdate schema with new data.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Updated Payment object.
        """
        log.info(
            "Updating payment status",
            payment_id=str(payment_id),
            update_data=payment_update.model_dump(exclude_unset=True),
            user_id=str(user_id),
        )

        payment = await self.get_payment_by_id(
            payment_id, user_id, permissions, is_superadmin
        )

        can_update = (
            is_superadmin
            or "payment:update:all" in permissions
            or (payment.order_id == user_id and "payment:update" in permissions)
        )
        if not can_update:
            log.warning(
                "User not authorized to update payment", payment_id=str(payment_id)
            )
            raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")

        update_data = payment_update.model_dump(exclude_unset=True)
        if not update_data:
            log.debug("No fields to update", payment_id=str(payment_id))
            return payment

        if "status" in update_data:
            new_status = update_data["status"]
            allowed_statuses = ["pending", "succeeded", "failed", "refunded"]
            if new_status not in allowed_statuses:
                raise InvalidInputError(f"Invalid status: {new_status}")
            if payment.status == "refunded" and new_status != "refunded":
                raise InvalidInputError("Cannot change status of a refunded payment")
            payment.status = new_status

        payment.updated_at = datetime.utcnow()

        try:
            self.session.add(payment)
            self.session.commit()
            self.session.refresh(payment)

            log.info("Payment updated successfully", payment_id=str(payment.id))
            return payment
        except Exception as e:
            log.critical(
                "Unexpected error during payment update",
                payment_id=str(payment.id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError("Failed to update payment due to internal error") from e

    async def refund_payment(
        self,
        payment_id: UUID,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Payment:
        """
        Refund an existing payment.
        Args:
            payment_id: UUID of the payment to refund.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Updated Payment object.
        """
        log.info("Refunding payment", payment_id=str(payment_id), user_id=str(user_id))
        payment = await self.get_payment_by_id(
            payment_id, user_id, permissions, is_superadmin
        )

        can_refund = (
            is_superadmin
            or "payment:refund:all" in permissions
            or (payment.order_id == user_id and "payment:refund" in permissions)
        )
        if not can_refund:
            log.warning(
                "User not authorized to refund payment", payment_id=str(payment_id)
            )
            raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")

        if payment.status != "succeeded":
            raise InvalidInputError(
                f"Cannot refund payment with status '{payment.status}'"
            )

        payment.status = "refunded"
        payment.updated_at = datetime.utcnow()

        try:
            self.session.add(payment)
            self.session.commit()
            self.session.refresh(payment)

            log.info("Payment refunded successfully", payment_id=str(payment.id))
            return payment
        except Exception as e:
            log.critical(
                "Unexpected error during payment refund",
                payment_id=str(payment.id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError("Failed to refund payment due to internal error") from e

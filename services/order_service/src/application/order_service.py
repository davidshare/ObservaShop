# src/application/order_service.py

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID
from sqlmodel import Session, select
from src.config.logger_config import log
from src.core.exceptions import (
    OrderNotFoundError,
    OrderStatusTransitionError,
    OrderCancellationError,
    InsufficientStockError,
    ProductUnavailableError,
    PaymentProcessingError,
    ExternalServiceError,
    DatabaseError,
    InvalidInputError,
)
from src.domain.models import Order, OrderItem
from src.interfaces.http.schemas import OrderCreate, OrderUpdate
from src.infrastructure.clients.product_client import ProductClient
from src.infrastructure.clients.payment_client import PaymentClient


class OrderService:
    """
    Service class for handling order-related business logic.
    Encapsulates CRUD operations for orders with product validation, payment integration,
    and cache-aware operations.

    This service:
    - Validates product availability and stock
    - Locks prices at order time
    - Integrates with payment-service for confirmation
    - Uses Redis caching for performance
    - Fails gracefully on downstream service errors
    """

    def __init__(
        self,
        session: Session,
        product_client: ProductClient,
        payment_client: PaymentClient,
    ):
        """
        Initialize the service with a database session and external clients.
        Args:
            session: SQLModel session for database operations.
            product_client: Client to interact with product-service.
            payment_client: Client to interact with payment-service.
        """
        self.session = session
        self.product_client = product_client
        self.payment_client = payment_client

    def _validate_order_create_input(self, order_create: OrderCreate) -> None:
        """
        Validate input data for order creation.
        Raises InvalidInputError if validation fails.
        """
        if not order_create.items:
            raise InvalidInputError("Order must contain at least one item")
        for item in order_create.items:
            if item.quantity <= 0:
                raise InvalidInputError(
                    f"Quantity for product {item.product_id} must be greater than zero"
                )

    async def create_order(
        self, user_id: UUID, order_create: OrderCreate, jwt_token: str
    ) -> Order:
        """
        Create a new order.
        Args:
            user_id: UUID of the user placing the order.
            order_create: OrderCreate schema with new data.
        Returns:
            Created Order object.
        Raises:
            InvalidInputError: If input data is invalid (e.g., no items, negative quantity).
            ProductUnavailableError: If a product does not exist or is inactive.
            InsufficientStockError: If a product does not have enough stock.
            ExternalServiceError: If product-service is unreachable.
            DatabaseError: If there is a database-level error.
        """
        log.info(
            "Creating order", user_id=str(user_id), item_count=len(order_create.items)
        )

        # Validate input
        self._validate_order_create_input(order_create)

        # Fetch product details and validate stock
        total_amount = Decimal("0.00")
        order_items = []

        for item in order_create.items:
            try:
                product = await self.product_client.get_product(
                    item.product_id, jwt_token=jwt_token
                )
            except ProductUnavailableError:
                log.warning(
                    "Order creation failed: product not found or inactive",
                    product_id=str(item.product_id),
                )
                raise
            except ExternalServiceError as e:
                log.exception(
                    "Order creation failed: product-service error", error=str(e)
                )
                raise ExternalServiceError(
                    "product-service", "Failed to validate product", e
                ) from e

            if not await self.product_client.check_stock(
                item.product_id, item.quantity, jwt_token
            ):
                log.warning(
                    "Order creation failed: insufficient stock",
                    product_id=str(item.product_id),
                    requested=item.quantity,
                    available=product.get("stock"),
                )
                raise InsufficientStockError(
                    f"Insufficient stock for product {item.product_id}. "
                    f"Requested: {item.quantity}, Available: {product['stock']}"
                )

            unit_price = Decimal(str(product["price"]))
            total_amount += unit_price * item.quantity

            order_item = OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                price=float(unit_price),
            )
            order_items.append(order_item)

        # Create order
        order = Order(
            user_id=user_id, status="pending", total_amount=float(total_amount)
        )
        self.session.add(order)
        self.session.flush()  # Assign ID to order before adding items

        for item in order_items:
            item.order_id = order.id
            self.session.add(item)

        try:
            self.session.commit()
            self.session.refresh(order)
            log.info(
                "Order created successfully",
                order_id=str(order.id),
                total_amount=float(total_amount),
            )
            return order
        except Exception as e:
            log.exception(
                "Unexpected error during order creation",
                order_id=str(order.id),
                error=str(e),
            )
            raise DatabaseError("Failed to create order due to internal error") from e

    def get_order_by_id(
        self, order_id: UUID, user_id: UUID, permissions: set[str], is_superadmin: bool
    ) -> Order:
        """
        Retrieve an order by ID.
        Args:
            order_id: UUID of the order to retrieve.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Order object.
        Raises:
            OrderNotFoundError: If order does not exist or user is not authorized.
            DatabaseError: If there is a database-level error.
        """
        log.debug("Fetching order by ID", order_id=str(order_id), user_id=str(user_id))

        try:
            order = self.session.exec(select(Order).where(Order.id == order_id)).first()
        except Exception as e:
            log.critical(
                "Unexpected error during database read",
                order_id=str(order_id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError("Failed to retrieve order due to internal error") from e

        if not order:
            log.warning("Order not found", order_id=str(order_id))
            raise OrderNotFoundError(f"Order with ID {order_id} not found")

        if is_superadmin or "order:read:all" in permissions:
            return order

        if order.user_id == user_id and "order:read" in permissions:
            return order

        log.warning(
            "Order access denied: insufficient permissions",
            order_id=str(order_id),
            requester_id=str(user_id),
            permissions=list(permissions),
        )
        raise OrderNotFoundError(f"Order with ID {order_id} not found")

    def list_orders(
        self,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
        limit: int = 10,
        offset: int = 0,
        sort: str = "created_at:desc",
        status: Optional[str] = None,
    ) -> Tuple[List[Order], int]:
        """
        List orders for a user with pagination, sorting, and optional status filter.
        Args:
            user_id: UUID of the user.
            limit: Number of orders to return.
            offset: Number of orders to skip.
            sort: Sort by field:direction (e.g., created_at:desc).
            status: Optional filter by order status.
        Returns:
            Tuple of (list of orders, total count).
        Raises:
            InvalidInputError: If sort field or direction is invalid.
        """
        log.debug(
            "Listing orders",
            user_id=str(user_id),
            limit=limit,
            offset=offset,
            sort=sort,
            status=status,
        )

        if is_superadmin or "order:list:all" in permissions:
            query = select(Order)
        else:
            query = select(Order).where(Order.user_id == user_id)

        if status:
            query = query.where(Order.status == status)

        # Parse sort
        sort_field, direction = (
            sort.split(":") if ":" in sort else ("created_at", "desc")
        )
        allowed_sort_fields = ["created_at", "updated_at", "total_amount", "status"]
        if sort_field not in allowed_sort_fields:
            raise InvalidInputError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise InvalidInputError(f"Invalid sort direction: {direction}")

        column = getattr(Order, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        # Get total count
        count_query = query.with_only_columns(Order.id).order_by()
        total = len(self.session.exec(count_query).all())

        # Apply pagination
        query = query.offset(offset).limit(limit)
        orders = self.session.exec(query).all()

        log.info("Orders listed successfully", count=len(orders), total=total)
        return orders, total

    async def update_order_status(
        self,
        order_id: UUID,
        order_update: OrderUpdate,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Order:
        """
        Update the status of an existing order.
        Args:
            order_id: UUID of the order to update.
            order_update: OrderUpdate schema with new data (e.g., status).
            user_id: UUID of the requesting user (for ownership check).
        Returns:
            Updated Order object.
        Raises:
            OrderNotFoundError: If order does not exist or user is not authorized.
            OrderStatusTransitionError: If status transition is invalid.
            PaymentProcessingError: If payment fails during confirmation.
            ExternalServiceError: If payment-service is unreachable.
        """
        log.info(
            "Updating order status",
            order_id=str(order_id),
            update_data=order_update.model_dump(exclude_unset=True),
            user_id=str(user_id),
        )

        order = self.get_order_by_id(order_id, user_id, permissions, is_superadmin)

        can_update = (
            is_superadmin
            or "order:update:all" in permissions
            or (order.user_id == user_id and "order:update" in permissions)
        )

        if not can_update:
            log.warning("User not authorized to update order", order_id=str(order_id))
            raise OrderNotFoundError(f"Order with ID {order_id} not found")

        # Get only the fields that were provided
        update_data = order_update.model_dump(exclude_unset=True)
        if not update_data:
            log.debug("No fields to update", order_id=str(order_id))
            return order

        # Extract status
        status = update_data["status"]  # Guaranteed by OrderUpdate schema

        # Validate status transition
        valid_transitions = {
            "pending": ["confirmed", "cancelled"],
            "confirmed": ["shipped", "cancelled"],
            "shipped": ["delivered"],
            "delivered": [],
            "cancelled": [],
        }
        current_status = order.status
        if status not in valid_transitions.get(current_status, []):
            log.warning(
                "Order status update failed: invalid transition",
                order_id=str(order_id),
                from_status=current_status,
                to_status=status,
            )
            raise OrderStatusTransitionError(
                f"Cannot transition order from '{current_status}' to '{status}'"
            )

        # Handle payment for confirmation
        if status == "confirmed" and current_status == "pending":
            try:
                payment_result = await self.payment_client.create_payment(
                    order_id, order.total_amount
                )
                if not payment_result.get("success"):
                    raise PaymentProcessingError(
                        payment_result.get("message", "Payment failed")
                    )
                log.info("Payment processed successfully", order_id=str(order_id))
            except ExternalServiceError:
                raise
            except Exception as e:
                log.error(
                    "Payment processing failed", order_id=str(order_id), error=str(e)
                )
                raise PaymentProcessingError("Payment processing failed") from e

        order.status = status
        order.updated_at = datetime.utcnow()

        try:
            self.session.add(order)
            self.session.commit()
            self.session.refresh(order)
            log.info(
                "Order status updated successfully",
                order_id=str(order.id),
                status=status,
            )
            return order
        except Exception as e:
            log.exception(
                "Unexpected error during order status update",
                order_id=str(order.id),
                error=str(e),
            )
            raise DatabaseError(
                "Failed to update order status due to internal error"
            ) from e

    async def cancel_order(
        self, order_id: UUID, user_id: UUID, permissions: set[str], is_superadmin: bool
    ) -> None:
        """
        Cancel an existing order.
        Args:
            order_id: UUID of the order to cancel.
            user_id: UUID of the requesting user (for ownership check).
        Raises:
            OrderNotFoundError: If order does not exist or user is not authorized.
            OrderCancellationError: If order cannot be cancelled.
        """
        log.info("Cancelling order", order_id=str(order_id), user_id=str(user_id))

        order = self.get_order_by_id(order_id, user_id, permissions, is_superadmin)

        can_cancel = (
            is_superadmin
            or "order:cancel:all" in permissions
            or (order.user_id == user_id and "order:cancel" in permissions)
        )
        if not can_cancel:
            raise OrderNotFoundError(f"Order with ID {order_id} not found")

        if order.status not in ["pending", "confirmed"]:
            log.warning(
                "Order cancellation failed: invalid status",
                order_id=str(order_id),
                status=order.status,
            )
            raise OrderCancellationError(
                f"Order with status '{order.status}' cannot be cancelled"
            )

        order.status = "cancelled"
        order.updated_at = datetime.utcnow()

        try:
            self.session.add(order)
            self.session.commit()
            log.info("Order cancelled successfully", order_id=str(order.id))
        except Exception as e:
            log.exception(
                "Unexpected error during order cancellation",
                order_id=str(order.id),
                error=str(e),
            )
            raise DatabaseError("Failed to cancel order due to internal error") from e

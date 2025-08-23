"""
Notification service for handling Kafka events and sending notifications.
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from sqlmodel import Session, select, func

from src.core.exceptions import (
    NotificationNotFoundError,
    NotificationCreationError,
    EventProcessingError,
    SchemaValidationError,
    DatabaseError,
    PermissionDeniedError,
)

from src.events.topics import (
    USER_CREATED,
    ORDER_CREATED,
    PAYMENT_FAILED,
    PRODUCT_BACK_IN_STOCK,
)

from src.config.logger_config import log
from src.events.event_consumer import EventConsumer
from src.infrastructure.kafka.kafka_client import KafkaClient
from src.infrastructure.kafka.kafka_config import KafkaConfig
from src.infrastructure.email.client import EmailClient
from src.domain.models import Notification


class NotificationService:
    """
    Main service class for handling notifications.
    - Saves notification records to the database
    - Reacts to Kafka events by sending emails and saving records
    """

    def __init__(self, session: Session, email_client: EmailClient):
        self.session = session
        self.email_client = email_client

        # Kafka components
        config = KafkaConfig()
        self.kafka_client = KafkaClient(config)
        self.event_consumer = EventConsumer(self.kafka_client)

        # Register event handlers
        self.event_consumer.register_handler("user.created", self._on_user_created)
        self.event_consumer.register_handler("order.created", self._on_order_created)
        self.event_consumer.register_handler("payment.failed", self._on_payment_failed)
        self.event_consumer.register_handler(
            "product.back_in_stock", self._on_product_back_in_stock
        )

    def shutdown(self):
        """
        Stop Kafka consumer and close connections gracefully.
        """
        self.event_consumer.stop()
        self.kafka_client.close()
        log.info("NotificationService shutdown completed")

    def start(self):
        """Start consuming Kafka events in background"""
        try:
            self.event_consumer.start(
                [
                    USER_CREATED,
                    ORDER_CREATED,
                    PAYMENT_FAILED,
                    PRODUCT_BACK_IN_STOCK,
                ]
            )
        except Exception as e:
            log.critical("Failed to start event consumer", error=str(e), exc_info=True)
            raise

    # === DATABASE OPERATIONS ===

    def create_notification(
        self,
        user_id: UUID,
        recipient: str,
        notification_type: str,
        subject: str,
        content: str,
        event_type: str,
        event_id: Optional[str] = None,
    ) -> Notification:
        """Save a notification record to the database"""
        try:
            notification = Notification(
                id=UUID(event_id) if event_id else uuid4(),
                user_id=user_id,
                recipient=recipient,
                notification_type=notification_type,
                subject=subject,
                content=content,
                status="pending",
                event_type=event_type,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(notification)
            self.session.commit()
            self.session.refresh(notification)
            return notification

        except Exception as e:
            log.critical(
                "Failed to save notification to DB",
                error=str(e),
                user_id=str(user_id),
                event_type=event_type,
                exc_info=True,
            )
            raise NotificationCreationError(
                f"Failed to save notification: {str(e)}"
            ) from e

    def get_notification(self, notification_id: UUID) -> Notification:
        """Retrieve a notification by ID"""
        try:
            notification = self.session.get(Notification, notification_id)
            if not notification:
                raise NotificationNotFoundError(str(notification_id))
            return notification
        except Exception as e:
            log.critical(
                "Failed to retrieve notification",
                notification_id=str(notification_id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError(f"Database query failed: {str(e)}") from e

    def list_notifications(
        self,
        limit: int = 10,
        offset: int = 0,
        status: Optional[str] = None,
        notification_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        requesting_user_id: Optional[UUID] = None,
        permissions: Optional[set] = None,
        is_superadmin: bool = False,
    ) -> Tuple[List[Notification], int]:
        """
        List notifications with comprehensive filtering and pagination.
        """
        try:
            # 1. Validate inputs
            self._validate_list_parameters(limit, offset, status, notification_type)
            self._validate_date_range(start_date, end_date)

            # 2. Check permissions
            target_user_id = user_id or requesting_user_id
            if not self._has_permission_to_access_user_data(
                requesting_user_id=requesting_user_id,
                target_user_id=target_user_id,
                permissions=permissions or set(),
                is_superadmin=is_superadmin,
            ):
                raise PermissionDeniedError(
                    action="list",
                    user_id=str(requesting_user_id) if requesting_user_id else None,
                )

            # 3. Build query
            query = self._build_notification_query(
                status=status,
                notification_type=notification_type,
                user_id=target_user_id,
                event_type=event_type,
                start_date=start_date,
                end_date=end_date,
            )

            # 4. Execute query
            notifications, total = self._execute_query_with_pagination(
                query, limit, offset
            )

            log.info(
                "Successfully retrieved notifications",
                count=len(notifications),
                total=total,
                limit=limit,
                offset=offset,
                user_id=str(requesting_user_id) if requesting_user_id else "unknown",
            )

            return notifications, total

        except (SchemaValidationError, PermissionDeniedError):
            raise

        except Exception as e:
            log.critical(
                "Unexpected error in list_notifications",
                error=str(e),
                exc_info=True,
                limit=limit,
                offset=offset,
                status=status,
                notification_type=notification_type,
                user_id=str(user_id) if user_id else "all",
            )
            raise DatabaseError(f"Failed to retrieve notifications: {str(e)}") from e

    def mark_as_sent(self, notification_id: UUID) -> None:
        """Update notification status to 'sent'"""
        try:
            notification = self.session.get(Notification, notification_id)
            if notification:
                notification.status = "sent"
                notification.sent_at = datetime.now(timezone.utc)
                self.session.add(notification)
                self.session.commit()
        except Exception as e:
            log.critical(
                "Failed to update notification status",
                notification_id=str(notification_id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError(f"Failed to update status: {str(e)}") from e

    def mark_as_failed(self, notification_id: UUID, error: str) -> None:
        """Update notification status to 'failed'"""
        try:
            notification = self.session.get(Notification, notification_id)
            if notification:
                notification.status = "failed"
                notification.sent_at = datetime.now(timezone.utc)
                self.session.add(notification)
                self.session.commit()
        except Exception as e:
            log.critical(
                "Failed to mark notification as failed",
                notification_id=str(notification_id),
                error=str(e),
                exc_info=True,
                original_error=error,
            )

    # === EVENT HANDLERS ===

    def _on_user_created(self, data: dict):  # ← Fixed: add type hint
        """Handle user.created event"""
        try:
            user_id = UUID(data["user_id"])
            email = data["email"]
            event_id = data.get("event_id", str(uuid4()))
            correlation_id = data.get("correlation_id")
            log.info(
                "Processing user.created event",
                user_id=str(user_id),
                email=email,
                event_id=event_id,
                correlation_id=correlation_id,
            )

            notification = self.create_notification(
                user_id=user_id,
                recipient=email,
                notification_type="email",
                subject="Welcome to ObservaShop!",
                content="Welcome! Start shopping now.",
                event_type="user.created",
                event_id=event_id,
            )

            success = self.email_client.send_email(
                to=email,
                subject=data.get("subject", "Notification") or "Notification",
                body=notification.content,
            )

            if success:
                self.mark_as_sent(notification.id)
            else:
                self.mark_as_failed(notification.id, "Email send failed")

        except KeyError as e:
            log.error(
                "Missing required field in user.created event",
                required_field=str(e),
                data=data,
            )
            raise SchemaValidationError(f"Missing required field: {str(e)}") from e

        except Exception as e:
            log.critical(
                "Failed to handle user.created event",
                data=data,
                error=str(e),
                exc_info=True,
            )
            raise EventProcessingError("user.created", str(e)) from e

    def _on_order_created(self, data: dict):  # ← Fixed: add type hint
        """Handle order.created event"""
        try:
            user_id = UUID(data["user_id"])
            email = data["email"]
            order_id = data["order_id"]
            total = data["total"]

            notification = self.create_notification(
                user_id=user_id,
                recipient=email,
                notification_type="email",
                subject=f"Order Confirmed #{order_id}",
                content=f"Thank you for your order! Order #{order_id} for ${total:.2f} is confirmed.",
                event_type="order.created",
                event_id=data.get("event_id", str(uuid4())),
            )

            success = self.email_client.send_email(
                to=email,
                subject=data.get("subject", "Notification") or "Notification",
                body=notification.content,
            )

            if success:
                self.mark_as_sent(notification.id)
            else:
                self.mark_as_failed(notification.id, "Email send failed")

        except (KeyError, ValueError) as e:
            log.error("Invalid order.created event data", error=str(e), data=data)
            raise SchemaValidationError(f"Invalid order data: {str(e)}") from e

        except Exception as e:
            log.critical(
                "Failed to handle order.created", data=data, error=str(e), exc_info=True
            )
            raise EventProcessingError("order.created", str(e)) from e

    def _on_payment_failed(self, data: dict):  # ← Fixed: add type hint
        """Handle payment.failed event"""
        try:
            user_id = UUID(data["user_id"])
            email = data["email"]
            order_id = data["order_id"]
            reason = data.get("reason", "Unknown")

            notification = self.create_notification(
                user_id=user_id,
                recipient=email,
                notification_type="email",
                subject=f"Payment Failed for Order #{order_id}",
                content=f"Your payment for order #{order_id} failed: {reason}. Please update your payment method.",
                event_type="payment.failed",
                event_id=data.get("event_id", str(uuid4())),
            )

            success = self.email_client.send_email(
                to=email,
                subject=data.get("subject", "Notification") or "Notification",
                body=notification.content,
            )

            if success:
                self.mark_as_sent(notification.id)
            else:
                self.mark_as_failed(notification.id, "Email send failed")

        except Exception as e:
            log.critical(
                "Failed to handle payment.failed",
                data=data,
                error=str(e),
                exc_info=True,
            )
            raise EventProcessingError("payment.failed", str(e)) from e

    def _on_product_back_in_stock(self, data: dict):  # ← Fixed: add type hint
        """Handle product.back_in_stock event"""
        try:
            user_id = UUID(data["user_id"])
            email = data["email"]
            product_id = data["product_id"]
            product_name = data["product_name"]

            notification = self.create_notification(
                user_id=user_id,
                recipient=email,
                notification_type="email",
                subject=f"{product_name} (ID: {product_id}) is Back in Stock!",
                content=f"Great news! {product_name} is now available. Shop now before it's gone!",
                event_type="product.back_in_stock",
                event_id=data.get("event_id", str(uuid4())),
            )

            success = self.email_client.send_email(
                to=email,
                subject=data.get("subject", "Notification") or "Notification",
                body=notification.content,
            )

            if success:
                self.mark_as_sent(notification.id)
            else:
                self.mark_as_failed(notification.id, "Email send failed")

        except Exception as e:
            log.critical(
                "Failed to handle product.back_in_stock",
                data=data,
                error=str(e),
                exc_info=True,
            )
            raise EventProcessingError("product.back_in_stock", str(e)) from e

    def _validate_list_parameters(
        self,
        limit: int,
        offset: int,
        status: Optional[str],
        notification_type: Optional[str],
    ) -> None:
        """Validate basic list parameters."""
        if limit < 1 or limit > 100:
            raise SchemaValidationError(f"Limit must be between 1 and 100, got {limit}")

        if offset < 0:
            raise SchemaValidationError(f"Offset must be non-negative, got {offset}")

        valid_statuses = {"pending", "sent", "failed", "read"}
        if status and status not in valid_statuses:
            raise SchemaValidationError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        valid_types = {"email", "sms"}
        if notification_type and notification_type not in valid_types:
            raise SchemaValidationError(
                f"Invalid notification_type: {notification_type}. Must be one of {valid_types}"
            )

    def _validate_date_range(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> None:
        """Validate date range parameters."""
        if start_date and end_date and end_date < start_date:
            raise SchemaValidationError("End date cannot be before start date")

    def _has_permission_to_access_user_data(
        self,
        requesting_user_id: Optional[UUID],
        target_user_id: Optional[UUID],
        permissions: set,
        is_superadmin: bool,
    ) -> bool:
        """
        Check if the requesting user has permission to access another user's data.
        """
        if not target_user_id:
            return True  # Can access own notifications

        if is_superadmin:
            return True

        if "notification:list:all" in permissions:
            return True

        if requesting_user_id and requesting_user_id == target_user_id:
            return True

        return False

    def _build_notification_query(
        self,
        status: Optional[str] = None,
        notification_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Build the base query with filters."""
        query = select(Notification)

        if user_id:
            query = query.where(Notification.user_id == user_id)

        if status:
            query = query.where(Notification.status == status)

        if notification_type:
            query = query.where(Notification.notification_type == notification_type)

        if event_type:
            query = query.where(Notification.event_type == event_type)

        if start_date:
            query = query.where(Notification.created_at >= start_date)

        if end_date:
            query = query.where(Notification.created_at <= end_date)

        return query.order_by(Notification.created_at.desc())  # type: ignore # pylint: disable=no-member

    def _execute_query_with_pagination(self, query, limit: int, offset: int):
        """Execute query with pagination and return results."""
        # Get total count
        count_query = select(func.count(1)).select_from(query.subquery())
        total = self.session.exec(count_query).one()

        # Apply pagination
        paginated_query = query.offset(offset).limit(limit)
        notifications = self.session.exec(paginated_query).all()

        return notifications, total

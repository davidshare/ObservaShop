"""
Event consumer for notification-service.
Handles event routing, deduplication, and error management.
"""

from typing import Dict, Any, Callable, Optional
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from confluent_kafka import KafkaError, KafkaException

from src.config.logger_config import log
from src.infrastructure.kafka.kafka_client import KafkaClient
from src.infrastructure.services import redis_service
from src.core.exceptions import (
    EventProcessingError,
    SchemaValidationError,
    ExternalServiceError,
    KafkaConnectionError,
)
from src.events.schemas import BaseEvent
from src.events.topics import NOTIFICATION_SERVICE_DLQ
from src.events.schemas import (
    UserCreated,
    OrderCreated,
    PaymentFailed,
    ProductBackInStock,
)


class EventConsumer:
    """
    Consumes Kafka events and routes them to registered handlers.
    Uses a registry pattern - no need to write consume() for each event.
    """

    def __init__(self, kafka_client: KafkaClient):
        self.kafka_client = kafka_client
        self.handlers: Dict[str, Callable] = {}
        self._running = False

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type"""
        self.handlers[event_type] = handler
        log.info("Handler registered", event_type=event_type)

    def start(self, topics: list[str]) -> None:
        """Start consuming events with graceful shutdown support"""
        try:
            self._running = True
            if not self.kafka_client._connected:
                log.info("Kafka client not connected, attempting to connect")
                self.kafka_client.connect()

            if not self.kafka_client.consumer:
                log.critical("Kafka consumer not initialized after connect attempt")
                raise KafkaConnectionError("Kafka consumer not initialized")

            self.kafka_client.consumer.subscribe(topics)
            log.info("Event consumer started", topics=topics)

            while self._running:
                try:
                    msg = self.kafka_client.consumer.poll(timeout=1.0)
                    if msg is None:
                        continue

                    if msg.error():
                        self._handle_kafka_error(msg.error())
                        continue

                    self._process_message(msg)

                except KeyboardInterrupt:
                    log.info("Shutting down consumer due to keyboard interrupt")
                    break
                except Exception as e:
                    log.critical(
                        "Unexpected error in consumer loop", error=str(e), exc_info=True
                    )
                    # Continue loop - don't crash on transient errors

        except Exception as e:
            log.critical("Fatal error starting consumer", error=str(e), exc_info=True)
            raise
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer gracefully"""
        self._running = False
        if self.kafka_client.consumer:
            try:
                self.kafka_client.consumer.unsubscribe()
                log.info("Consumer unsubscribed from topics")
            except Exception as e:
                log.warning("Error during unsubscribe", error=str(e))
        self.kafka_client.close()

    def _handle_kafka_error(self, error) -> None:
        """Handle Kafka-specific errors"""
        # pylint: disable=protected-access
        if error.code() == KafkaError._PARTITION_EOF:
            log.debug(
                "End of partition reached", topic=error.topic, partition=error.partition
            )
        elif error.code() == KafkaError._TIMED_OUT:
            log.warning("Kafka poll timeout", error=str(error))
        else:
            log.error("Kafka error", error=str(error))

    def _process_message(self, msg) -> None:
        """Process a single Kafka message with full error handling"""
        # Decode message
        raw_event = None

        try:
            raw_value = msg.value().decode("utf-8")
            raw_event = json.loads(raw_value)

            # Validate event structure
            event = self._validate_event(raw_event)
            if not event:
                return  # Skip invalid events

            # Deduplicate using Redis
            if self._is_duplicate(event.event_id):
                log.debug("Duplicate event ignored", event_id=event.event_id)
                if not self.kafka_client.consumer:
                    log.error("Kafka consumer not initialized")
                    return
                self.kafka_client.consumer.commit(msg)
                return

            # Route to handler
            self._handle_event_with_retry(event, msg)

        except json.JSONDecodeError as e:
            log.warning("Invalid JSON in message", value=msg.value(), error=str(e))
            self.kafka_client.produce_dlq(
                NOTIFICATION_SERVICE_DLQ,
                {"raw_value": str(msg.value()), "error": str(e)},
                "JSON decode error",
            )

        except SchemaValidationError as e:
            log.warning(
                "Schema validation failed",
                event_type=raw_event.get("event_type") if raw_event else None,
                error=str(e),
            )
            self.kafka_client.produce_dlq(
                NOTIFICATION_SERVICE_DLQ,
                raw_event or {"raw_value": "unknown"},
                f"Schema validation: {str(e)}",
            )

        except Exception as e:
            log.critical(
                "Unexpected error processing message",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                error=str(e),
                exc_info=True,
            )
            self.kafka_client.produce_dlq(
                NOTIFICATION_SERVICE_DLQ,
                {"raw_value": str(msg.value()), "error": str(e)},
                "Unexpected processing error",
            )

    def _validate_event(self, raw_event: Dict[str, Any]) -> Optional[BaseEvent]:
        """Validate event against schema"""
        try:
            # Basic structure check
            required_fields = ["event_id", "event_type", "source", "timestamp"]
            missing = [field for field in required_fields if field not in raw_event]
            if missing:
                raise SchemaValidationError(f"Missing required fields: {missing}")

            # Validate against Pydantic model
            event_type = raw_event.get("event_type")
            if event_type == "user.created":
                return UserCreated(**raw_event)
            elif event_type == "order.created":
                return OrderCreated(**raw_event)
            elif event_type == "payment.failed":
                return PaymentFailed(**raw_event)
            elif event_type == "product.back_in_stock":
                return ProductBackInStock(**raw_event)
            else:
                log.warning("Unknown event type", event_type=event_type)
                return None

        except Exception as e:
            raise SchemaValidationError(f"Event validation failed: {str(e)}") from e

    async def _is_duplicate(self, event_id: str) -> bool:
        """Check if event has already been processed"""
        try:
            return await redis_service.exists(f"event:{event_id}")
        except Exception as e:
            log.warning(
                "Error checking for duplicates", event_id=event_id, error=str(e)
            )
            return False  # Proceed if deduplication fails

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type((ExternalServiceError,)),
        reraise=True,
    )
    def _handle_event_with_retry(self, event: BaseEvent, msg) -> None:
        """Handle event with retry logic for transient failures"""
        try:
            handler = self.handlers.get(event.event_type)
            if not handler:
                log.warning("No handler for event type", event_type=event.event_type)
                if not self.kafka_client.consumer:
                    log.error("Kafka consumer not initialized")
                    return
                self.kafka_client.consumer.commit(msg)
                return

            # Execute handler
            handler(event.data)

            # Commit offset only after successful processing
            if not self.kafka_client.consumer:
                raise KafkaConnectionError("Kafka consumer not initialized")
            self.kafka_client.consumer.commit(msg)
            log.info(
                "Event processed successfully",
                event_type=event.event_type,
                event_id=event.event_id,
                correlation_id=event.correlation_id,
            )
        except (EventProcessingError, ExternalServiceError) as e:
            log.critical(
                "Handler failed",
                event_type=event.event_type,
                event_id=event.event_id,
                error=str(e),
                exc_info=True,
            )
            raise
        except Exception as e:
            log.critical(
                "Handler failed",
                event_type=event.event_type,
                event_id=event.event_id,
                error=str(e),
                exc_info=True,
            )
            raise EventProcessingError(event.event_type, str(e)) from e
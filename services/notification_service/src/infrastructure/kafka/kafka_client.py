"""
Reusable Kafka client for notification-service.
Handles connection lifecycle and error management.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from loguru import logger

from src.core.exceptions import (
    KafkaAuthenticationError,
    KafkaConnectionError,
    KafkaTimeoutError,
)
from src.infrastructure.kafka.kafka_config import KafkaConfig


class KafkaClient:
    """
    Manages Kafka consumer and producer connections for the notification service.
    Provides methods to connect, produce to DLQ, and check health.
    Singleton instance can be shared across the service.
    """

    def __init__(self, config: KafkaConfig):
        """
        Initialize KafkaClient with configuration.

        Args:
            config: KafkaConfig object with bootstrap servers, group ID, etc.
        """
        self.config = config
        self.consumer: Optional[Consumer] = None
        self.producer: Optional[Producer] = None
        self._connected = False

    def connect(self) -> None:
        """
        Establish Kafka consumer and producer connections.

        Validates configuration and initializes consumer/producer with error handling.

        Raises:
            KafkaConnectionError: If bootstrap servers are missing or connection fails
            KafkaAuthenticationError: If authentication fails
            KafkaTimeoutError: If connection times out
        """
        try:
            # Validate configuration
            if not self.config.bootstrap_servers:
                raise KafkaConnectionError("KAFKA_BOOTSTRAP_SERVER is required")

            # Initialize consumer
            consumer_config = self.config.to_consumer_dict()
            logger.debug(
                "Initializing consumer with config",
                extra={"consumer_config": consumer_config},
            )
            self.consumer = Consumer(consumer_config)
            if not self.consumer:
                raise KafkaConnectionError(
                    "Failed to initialize Kafka consumer: Consumer object is None"
                )

            # Initialize producer
            producer_config = self.config.to_producer_dict()
            logger.debug(
                "Initializing producer with config",
                extra={"producer_config": producer_config},
            )
            self.producer = Producer(producer_config)
            if not self.producer:
                raise KafkaConnectionError(
                    "Failed to initialize Kafka producer: Producer object is None"
                )

            # Verify connection by listing topics
            self.consumer.list_topics(timeout=5)
            logger.info(
                "Kafka client connected",
                extra={
                    "bootstrap_servers": self.config.bootstrap_servers,
                    "group_id": self.config.group_id,
                },
            )
            self._connected = True

        except KafkaException as e:
            logger.error("Kafka exception during connection", extra={"error": str(e)})
            if e.args[0].code() == KafkaError._ALL_BROKERS_DOWN:
                raise KafkaConnectionError(f"All brokers down: {e}") from e
            elif e.args[0].code() == KafkaError._AUTHENTICATION:
                raise KafkaAuthenticationError(f"Authentication failed: {e}") from e
            elif e.args[0].code() in (KafkaError._TIMED_OUT, KafkaError._TRANSPORT):
                raise KafkaTimeoutError(f"Connection timeout: {e}") from e
            else:
                raise KafkaConnectionError(f"Kafka connection failed: {e}") from e

        except Exception as e:
            logger.critical(
                "Failed to connect to Kafka",
                extra={
                    "error": str(e),
                    "config": self.config.model_dump(),
                    "exc_info": True,
                },
            )
            self.consumer = None
            self.producer = None
            self._connected = False
            raise KafkaConnectionError(f"Connection failed: {str(e)}") from e

    def close(self) -> None:
        """Safely close Kafka connections"""
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.warning("Error closing Kafka consumer", extra={"error": str(e)})
            finally:
                self.consumer = None

        if self.producer:
            try:
                self.producer.flush()
                logger.info("Kafka producer flushed and closed")
            except Exception as e:
                logger.warning("Error closing Kafka producer", extra={"error": str(e)})
            finally:
                self.producer = None

        self._connected = False

    def produce_dlq(self, topic: str, message: Dict[str, Any], error: str) -> None:
        """Produce message to DLQ with error context"""
        try:
            if not self.producer:
                raise KafkaConnectionError("Producer not initialized")

            dlq_message = {
                "original_message": message,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "notification-service",
            }

            self.producer.produce(
                topic=topic,
                value=json.dumps(dlq_message).encode("utf-8"),
                on_delivery=self._delivery_report,
            )
            self.producer.flush()

        except Exception as e:
            logger.critical(
                "Failed to produce to DLQ",
                extra={"topic": topic, "error": str(e), "exc_info": True},
            )

    def is_healthy(self) -> bool:
        """
        Check if Kafka is responsive by listing topics.

        Returns:
            bool: True if Kafka is connected and responsive, False otherwise
        """
        if not self._connected or not self.consumer:
            logger.debug("Healthcheck failed: Consumer not connected or initialized")
            return False
        try:
            self.consumer.list_topics(timeout=5)
            return True
        except Exception as e:
            logger.error("Kafka healthcheck failed", extra={"error": str(e)})
            return False

    def _delivery_report(self, err, msg):
        """Callback for Kafka produce delivery"""
        if err is not None:
            logger.error(
                "Message delivery failed",
                extra={"topic": msg.topic() if msg else None, "error": str(err)},
            )
        else:
            logger.debug(
                "Message delivered",
                extra={
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                },
            )

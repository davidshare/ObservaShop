"""
Kafka configuration for the ObservaShop notification service.
Defines settings for Kafka consumer and producer with environment variable support.
"""

from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from src.config.config import config as setting


class KafkaConfig(BaseSettings):
    """
    Kafka configuration class with settings for Confluent Platform 7.7.0.
    Loads settings from environment variables prefixed with 'KAFKA_'.
    """

    bootstrap_servers: str = setting.KAFKA_BOOTSTRAP_SERVER
    group_id: str = setting.KAFKA_CONSUMER_GROUP_ID
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False
    session_timeout_ms: int = 45000
    fetch_message_max_bytes: int = (
        1048576  # Default from librdkafka, controls max bytes per partition fetch
    )
    queued_max_messages_kbytes: int = (
        65536  # Default from librdkafka, controls consumer queue size
    )

    # Producer settings
    enable_idempotence: bool = True
    acks: str = "all"
    retries: int = 2147483647  # Default from librdkafka
    request_timeout_ms: int = 30000  # Valid for producer

    # Security (for production)
    security_protocol: str = "PLAINTEXT"
    ssl_cafile: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None

    def to_consumer_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to a dictionary for Kafka consumer initialization.

        Returns:
            Dict[str, Any]: Configuration dictionary for confluent_kafka.Consumer
        """
        config = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": self.auto_offset_reset,
            "enable.auto.commit": self.enable_auto_commit,
            "session.timeout.ms": self.session_timeout_ms,
            "fetch.message.max.bytes": self.fetch_message_max_bytes,
            "queued.max.messages.kbytes": self.queued_max_messages_kbytes,
            "security.protocol": self.security_protocol,
            "log.connection.close": False,
        }
        if self.security_protocol != "PLAINTEXT":
            config.update(
                {
                    "ssl.ca.location": self.ssl_cafile,
                    "ssl.certificate.location": self.ssl_certfile,
                    "ssl.key.location": self.ssl_keyfile,
                }
            )
        return config

    def to_producer_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to a dictionary for Kafka producer initialization.

        Returns:
            Dict[str, Any]: Configuration dictionary for confluent_kafka.Producer
        """
        config = {
            "bootstrap.servers": self.bootstrap_servers,
            "enable.idempotence": self.enable_idempotence,
            "acks": self.acks,
            "retries": self.retries,
            "request.timeout.ms": self.request_timeout_ms,
            "security.protocol": self.security_protocol,
        }
        if self.security_protocol != "PLAINTEXT":
            config.update(
                {
                    "ssl.ca.location": self.ssl_cafile,
                    "ssl.certificate.location": self.ssl_certfile,
                    "ssl.key.location": self.ssl_keyfile,
                }
            )
        return config

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        env_file=".env.notification",
        env_file_encoding="utf-8",
        extra="ignore",
    )

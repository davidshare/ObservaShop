"""
Manages Kafka topics - creates them automatically if they don't exist.
Similar to how Alembic handles database migrations.
"""

from typing import Dict
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import KafkaException
from src.config.logger_config import log
from src.events.topics import (
    USER_CREATED,
    ORDER_CREATED,
    PAYMENT_FAILED,
    PRODUCT_BACK_IN_STOCK,
    NOTIFICATION_SERVICE_DLQ,
)


class TopicManager:
    """
    Manages Kafka topics for the notification service.
    Creates required topics on startup if they don't exist.
    """

    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})
        self.required_topics = [
            USER_CREATED,
            ORDER_CREATED,
            PAYMENT_FAILED,
            PRODUCT_BACK_IN_STOCK,
            NOTIFICATION_SERVICE_DLQ,
        ]
        # self.topic_configs = {
        #     "replication.factor": 1,
        #     "min.insync.replicas": 1,
        #     "cleanup.policy": "delete",
        #     "retention.ms": 604800000,  # 7 days
        # }
        self.topic_creation_params = {
            "num_partitions": 1,
            "replication_factor": 1,
            "config": {
                # These are the actual topic-level configs
                "cleanup.policy": "delete",
                "retention.ms": "604800000",  # 7 days
                "min.insync.replicas": "1",
            },
        }

    def create_topics(self, timeout: int = 30) -> bool:
        """
        Create all required topics if they don't exist.

        Args:
            timeout: Timeout in seconds for topic creation

        Returns:
            True if all topics exist (created or already existed)
        """
        try:
            # Get existing topics
            metadata = self.admin_client.list_topics(timeout=timeout)
            existing_topics = set(metadata.topics.keys())

            # Find topics that need to be created
            topics_to_create = [
                topic for topic in self.required_topics if topic not in existing_topics
            ]

            if not topics_to_create:
                log.info("All required topics already exist")
                return True

            log.info(
                "Creating missing topics",
                topics=topics_to_create,
                total=len(topics_to_create),
            )

            # Create new topics
            new_topics = [
                NewTopic(
                    topic=topic,
                    num_partitions=self.topic_creation_params["num_partitions"],
                    replication_factor=self.topic_creation_params["replication_factor"],
                    config=self.topic_creation_params["config"],
                )
                for topic in topics_to_create
            ]

            # Create topics asynchronously
            fs = self.admin_client.create_topics(
                new_topics, validate_only=False, operation_timeout=timeout
            )

            # Wait for completion
            success = True
            for topic, f in fs.items():
                try:
                    f.result()  # The result itself is None
                    log.info("Topic created successfully", topic=topic)
                except Exception as e:
                    log.error("Failed to create topic", topic=topic, error=str(e))
                    success = False

            return success

        except KafkaException as e:
            log.critical("Kafka admin operation failed", error=str(e))
            return False

        except Exception as e:
            log.critical(
                "Unexpected error creating topics", error=str(e), exc_info=True
            )
            return False

    def verify_topics(self) -> Dict[str, bool]:
        """
        Verify all required topics exist and are healthy.

        Returns:
            Dictionary mapping topic names to their existence status
        """
        try:
            metadata = self.admin_client.list_topics(timeout=10)
            existing_topics = set(metadata.topics.keys())

            return {topic: topic in existing_topics for topic in self.required_topics}

        except Exception as e:
            log.critical("Failed to verify topics", error=str(e), exc_info=True)
            return {topic: False for topic in self.required_topics}

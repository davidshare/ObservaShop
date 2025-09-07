"""
Manages Kafka topics - creates them automatically if they don't exist.
Similar to how Alembic handles database migrations.
"""
import time
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
            for topic, f in fs.items():
                try:
                    f.result()  # The result itself is None
                    log.info("Topic created successfully", topic=topic)
                except Exception as e:
                    log.error("Failed to create topic", topic=topic, error=str(e))

            return self._wait_for_topics_ready(timeout=30)

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

    def _wait_for_topics_ready(self, timeout: int = 30) -> bool:
        """
        Poll metadata until all required topics have leaders assigned and are ready.
        This avoids the 'UNKNOWN_TOPIC_OR_PART' error due to KRaft metadata lag.
        """
        start_time = time.time()
        last_log = 0

        while time.time() - start_time < timeout:
            try:
                metadata = self.admin_client.list_topics(timeout=10)
                ready = True
                missing_or_unavailable = []

                for topic in self.required_topics:
                    if topic not in metadata.topics:
                        ready = False
                        missing_or_unavailable.append(topic)
                        continue

                    topic_metadata = metadata.topics[topic]
                    if not topic_metadata.partitions:
                        ready = False
                        missing_or_unavailable.append(f"{topic} (no partitions)")
                        continue

                    # Check if any partition has leader == -1
                    for partition in topic_metadata.partitions.values():
                        if partition.leader == -1:
                            ready = False
                            missing_or_unavailable.append(
                                f"{topic}/P{partition.id} (leader -1)"
                            )
                            break

                if ready:
                    log.info(
                        "All topics are ready for consumption",
                        topics=self.required_topics,
                    )
                    return True

                # Avoid spamming logs
                if time.time() - last_log > 5:
                    log.warning(
                        "Waiting for topics to be fully ready",
                        missing_or_unavailable=missing_or_unavailable,
                    )
                    last_log = time.time()

                time.sleep(2)

            except Exception as e:
                log.warning("Error checking topic readiness", error=str(e))
                time.sleep(2)

        log.error("Timeout waiting for topics to be ready", topics=self.required_topics)
        return False

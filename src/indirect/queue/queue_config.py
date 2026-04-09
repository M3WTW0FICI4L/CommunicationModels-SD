"""
RabbitMQ queue configuration and utilities.
"""

from typing import Dict, Any
import pika


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class QueueConfig:
    """Centralised queue names and settings."""

    PURCHASE_QUEUE = "ticket_purchases"
    RESPONSE_QUEUE = "ticket_responses"

    QUEUE_DURABLE = True
    QUEUE_EXCLUSIVE = False
    QUEUE_AUTO_DELETE = False

    # Dead-letter exchange for unprocessable messages
    DLX_NAME = "ticket_dlx"
    DLX_QUEUE = "ticket_dlq"

    # Message TTL: 30 minutes (ms)
    MESSAGE_TTL = 1_800_000


def get_queue_arguments() -> Dict[str, Any]:
    """Return standard arguments used when declaring the purchase queue."""
    return {
        "x-message-ttl": QueueConfig.MESSAGE_TTL,
        "x-dead-letter-exchange": QueueConfig.DLX_NAME,
    }


def get_connection_url(host: str, port: int, user: str, password: str,
                       vhost: str = "/") -> str:
    """Build a pika-compatible AMQP URL."""
    import urllib.parse
    vhost_encoded = urllib.parse.quote(vhost, safe="")
    return f"amqp://{user}:{password}@{host}:{port}/{vhost_encoded}"


# ---------------------------------------------------------------------------
# QueueManager
# ---------------------------------------------------------------------------

class QueueManager:
    """Low-level helper that wraps a pika BlockingConnection."""

    def __init__(self):
        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.adapters.blocking_connection.BlockingChannel | None = None

    def connect(self, connection_url: str) -> None:
        """Open a blocking AMQP connection and create a channel."""
        params = pika.URLParameters(connection_url)
        params.heartbeat = 600
        params.blocked_connection_timeout = 300
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

    def disconnect(self) -> None:
        """Gracefully close channel and connection."""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception:
            pass
        self.channel = None
        self.connection = None

    def declare_queue(self, queue_name: str, durable: bool = True,
                      arguments: Dict[str, Any] | None = None) -> None:
        """Idempotent queue declaration."""
        self.channel.queue_declare(
            queue=queue_name,
            durable=durable,
            arguments=arguments or {},
        )

    def declare_exchange(self, exchange_name: str,
                         exchange_type: str = "direct",
                         durable: bool = True) -> None:
        """Idempotent exchange declaration."""
        self.channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=durable,
        )

    def bind_queue(self, queue_name: str, exchange_name: str,
                   routing_key: str = "") -> None:
        """Bind a queue to an exchange."""
        self.channel.queue_bind(
            queue=queue_name,
            exchange=exchange_name,
            routing_key=routing_key,
        )

    def setup_dlq(self) -> None:
        """Declare the dead-letter exchange and queue."""
        self.declare_exchange(QueueConfig.DLX_NAME, exchange_type="fanout")
        self.channel.queue_declare(queue=QueueConfig.DLX_QUEUE, durable=True)
        self.bind_queue(QueueConfig.DLX_QUEUE, QueueConfig.DLX_NAME)

    def purge_queue(self, queue_name: str) -> None:
        """Remove all pending messages from a queue."""
        self.channel.queue_purge(queue=queue_name)

    def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """
        Passive declare returns message/consumer counts.
        Returns {} if the queue does not exist.
        """
        try:
            result = self.channel.queue_declare(
                queue=queue_name, passive=True
            )
            return {
                "message_count": result.method.message_count,
                "consumer_count": result.method.consumer_count,
            }
        except Exception:
            return {}

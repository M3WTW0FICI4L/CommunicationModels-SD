"""
Indirect communication producer (client side).
Sends purchase requests to RabbitMQ queue.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import pika

from ...common.config import Config
from ...common.logger import setup_logger
from ..queue.queue_config import (
    QueueConfig,
    QueueManager,
    get_connection_url,
    get_queue_arguments,
)


logger = setup_logger(__name__)


class IndirectProducer:
    """Publishes ticket-purchase requests onto the RabbitMQ purchase queue."""

    def __init__(self, queue_url: Optional[str] = None):
        self.queue_url = queue_url or self._default_queue_url()
        self._mgr = QueueManager()
        self._publish_lock = threading.Lock()  # Synchronize concurrent publishes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _default_queue_url(self) -> str:
        return get_connection_url(
            host=Config.RABBITMQ_HOST,
            port=Config.RABBITMQ_PORT,
            user=Config.RABBITMQ_USER,
            password=Config.RABBITMQ_PASS,
            vhost=Config.RABBITMQ_VHOST,
        )

    def _publish(self, body: dict) -> None:
        """Publish a JSON-encoded message to the purchase queue (thread-safe)."""
        with self._publish_lock:
            self._mgr.channel.basic_publish(
                exchange="",
                routing_key=QueueConfig.PURCHASE_QUEUE,
                body=json.dumps(body),
                properties=pika.BasicProperties(
                    delivery_mode=2,       # persistent
                    content_type="application/json",
                ),
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to RabbitMQ and ensure the purchase queue exists."""
        self._mgr.connect(self.queue_url)
        self._mgr.setup_dlq()
        self._mgr.declare_queue(
            QueueConfig.PURCHASE_QUEUE,
            durable=True,
            arguments=get_queue_arguments(),
        )
        logger.info("Producer connected to RabbitMQ")

    def disconnect(self) -> None:
        """Close the RabbitMQ connection."""
        self._mgr.disconnect()
        logger.info("Producer disconnected")

    # ------------------------------------------------------------------
    # Send methods
    # ------------------------------------------------------------------

    def send_unnumbered_request(self, client_id: str, request_id: str) -> None:
        """Enqueue an unnumbered ticket purchase request."""
        self._publish({
            "client_id": client_id,
            "request_id": request_id,
            "ticket_type": "unnumbered",
        })

    def send_numbered_request(self, client_id: str, request_id: str,
                               seat_id: int) -> None:
        """Enqueue a numbered seat purchase request."""
        self._publish({
            "client_id": client_id,
            "request_id": request_id,
            "ticket_type": "numbered",
            "seat_id": seat_id,
        })

    def send_batch(self, requests: List[dict]) -> None:
        """Send a list of request dicts sequentially."""
        for req in requests:
            self._publish(req)

    def send_with_priority(self, request: dict, priority: int = 0) -> None:
        """Publish with an AMQP priority header (0–9)."""
        self._mgr.channel.basic_publish(
            exchange="",
            routing_key=QueueConfig.PURCHASE_QUEUE,
            body=json.dumps(request),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                priority=max(0, min(priority, 9)),
            ),
        )


# ---------------------------------------------------------------------------
# BulkProducer – high-throughput batched sender
# ---------------------------------------------------------------------------

class BulkProducer(IndirectProducer):
    """
    Optimised producer for benchmark runs.

    Buffers messages locally and flushes in batches.  Uses publisher
    confirms for reliability.
    """

    def __init__(self, queue_url: Optional[str] = None, batch_size: int = 500):
        super().__init__(queue_url)
        self.batch_size = batch_size
        self._buffer: List[dict] = []
        self._lock = threading.Lock()

    def connect(self) -> None:
        super().connect()
        # Enable publisher confirms so we know messages were accepted
        self._mgr.channel.confirm_delivery()

    def add_request(self, request: dict) -> None:
        """Buffer a request; auto-flush when the batch is full."""
        with self._lock:
            self._buffer.append(request)
            if len(self._buffer) >= self.batch_size:
                self._flush_locked()

    def flush(self) -> None:
        """Force-send all buffered requests."""
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        """Send all buffered messages (must hold self._lock)."""
        for req in self._buffer:
            self._publish(req)
        self._buffer.clear()

    def load_and_send_file(self, file_path: str,
                            ticket_type: str = "unnumbered",
                            max_workers: int = 1) -> int:
        """
        Read a benchmark file and publish all lines to the queue.

        Returns the number of messages sent.
        """
        entries = []
        with open(file_path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0] != "BUY":
                    continue
                if ticket_type == "unnumbered":
                    # BUY client_id request_id
                    entries.append({
                        "client_id": parts[1],
                        "request_id": parts[2],
                        "ticket_type": "unnumbered",
                    })
                else:
                    # BUY client_id seat_id request_id
                    entries.append({
                        "client_id": parts[1],
                        "request_id": parts[3],
                        "ticket_type": "numbered",
                        "seat_id": int(parts[2]),
                    })

        count = 0
        for entry in entries:
            self.add_request(entry)
            count += 1
        self.flush()
        logger.info(f"BulkProducer sent {count} messages from {file_path}")
        return count

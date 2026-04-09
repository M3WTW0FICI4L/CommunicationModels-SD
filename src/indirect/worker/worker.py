"""
Indirect communication worker (server side).
Consumes messages from RabbitMQ queue and processes ticket purchases.
"""

import json
import signal
import sys
import threading
import time
from typing import Dict, Any, Optional

import pika

from ...backend.storage import RedisBackend
from ...backend.ticket_manager import TicketManager
from ...common.config import Config
from ...common.logger import setup_logger
from ...common.models import BuyRequest, TicketType
from ..queue.queue_config import (
    QueueConfig,
    QueueManager,
    get_connection_url,
    get_queue_arguments,
)


logger = setup_logger(__name__)


class IndirectWorker:
    """
    RabbitMQ consumer that processes ticket-purchase messages.

    Each worker:
    1. Connects to RabbitMQ and Redis independently.
    2. Sets QoS prefetch = 1 so RabbitMQ distributes messages fairly.
    3. ACKs a message only after successfully storing the result.
    4. NACKs (with requeue=False) on unrecoverable errors so the message
       goes to the dead-letter queue instead of being silently lost.
    """

    def __init__(self, worker_id: str, queue_url: Optional[str] = None):
        self.worker_id = worker_id
        self.queue_url = queue_url or self._default_queue_url()

        self._mgr = QueueManager()

        # Each worker gets its own Redis + TicketManager instance.
        # Redis operations are already atomic; having separate Python-level
        # managers is fine and allows independent in-process idempotency caches.
        self.storage = RedisBackend(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
        )
        self.ticket_manager = TicketManager(self.storage)

        self.running = False
        self.processed_count = 0
        self.error_count = 0
        self._start_time: Optional[float] = None

        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

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

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Worker {self.worker_id} received shutdown signal {signum}")
        self.stop()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to RabbitMQ, declare queue, and set QoS."""
        self._mgr.connect(self.queue_url)
        self._mgr.setup_dlq()
        self._mgr.declare_queue(
            QueueConfig.PURCHASE_QUEUE,
            durable=True,
            arguments=get_queue_arguments(),
        )
        # Declare response queue for optional result logging
        self._mgr.declare_queue(QueueConfig.RESPONSE_QUEUE, durable=True)
        # Fair dispatch: don't give more than 1 unacknowledged message per worker
        self._mgr.channel.basic_qos(prefetch_count=1)
        logger.info(f"Worker {self.worker_id} connected to RabbitMQ")

    def disconnect(self) -> None:
        """Close RabbitMQ and Redis connections."""
        self._mgr.disconnect()
        self.storage.disconnect()

    def start(self) -> None:
        """
        Begin consuming messages.  Blocks until stop() is called.
        """
        self.connect()
        self.storage.connect()
        self.running = True
        self._start_time = time.time()

        logger.info(f"Worker {self.worker_id} starting consumption")

        self._mgr.channel.basic_consume(
            queue=QueueConfig.PURCHASE_QUEUE,
            on_message_callback=self._on_message,
            auto_ack=False,
        )
        try:
            self._mgr.channel.start_consuming()
        except Exception as e:
            if self.running:
                logger.error(f"Worker {self.worker_id} consuming error: {e}")
        finally:
            logger.info(
                f"Worker {self.worker_id} stopped. "
                f"Processed={self.processed_count}, Errors={self.error_count}"
            )

    def stop(self) -> None:
        """Signal the worker to stop consuming."""
        self.running = False
        try:
            if self._mgr.channel and self._mgr.channel.is_open:
                self._mgr.channel.stop_consuming()
        except Exception:
            pass
        self.disconnect()

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    def _on_message(self, channel, method, properties, body: bytes) -> None:
        """Callback invoked by pika for each incoming message."""
        self._process_message(body.decode("utf-8"), channel, method)

    def _process_message(self, message_body: str, channel=None, method=None) -> None:
        """Parse, process, and acknowledge a single message."""
        try:
            data = json.loads(message_body)
            ticket_type_str = data.get("ticket_type", "unnumbered")
            ticket_type = TicketType(ticket_type_str)

            request = BuyRequest(
                client_id=data["client_id"],
                request_id=data["request_id"],
                ticket_type=ticket_type,
                seat_id=data.get("seat_id"),
            )

            response = self.ticket_manager.buy_ticket(request)

            # Optionally push result to response queue
            if channel and channel.is_open:
                resp_body = json.dumps({
                    "request_id": response.request_id,
                    "client_id": response.client_id,
                    "status": response.status.value,
                    "seat_id": response.seat_id,
                    "message": response.message,
                    "worker_id": self.worker_id,
                })
                channel.basic_publish(
                    exchange="",
                    routing_key=QueueConfig.RESPONSE_QUEUE,
                    body=resp_body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type="application/json",
                    ),
                )

            # Acknowledge the message only after successful processing
            if channel and method:
                channel.basic_ack(delivery_tag=method.delivery_tag)

            self.processed_count += 1
            logger.debug(
                f"Worker {self.worker_id} processed {request.request_id}: "
                f"{response.status.value}"
            )

        except Exception as e:
            logger.error(f"Worker {self.worker_id} error processing message: {e}")
            self.error_count += 1
            # NACK without requeue → goes to DLQ
            if channel and method:
                channel.basic_nack(
                    delivery_tag=method.delivery_tag, requeue=False
                )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "running": self.running,
            "processed": self.processed_count,
            "errors": self.error_count,
            "uptime": self.get_uptime(),
        }

    def get_uptime(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time


# ---------------------------------------------------------------------------
# WorkerPool – dynamic scaling
# ---------------------------------------------------------------------------

class WorkerPool:
    """
    Manages a set of IndirectWorker threads.

    Workers are started in daemon threads so the process exits cleanly
    when the main thread finishes.  New workers can be added (and
    stopped) at runtime without interrupting existing ones.
    """

    def __init__(self, initial_workers: int = 1,
                 queue_url: Optional[str] = None):
        self.queue_url = queue_url
        self.workers: Dict[str, IndirectWorker] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._next_id = 0

        for _ in range(initial_workers):
            self.add_worker()

    # ------------------------------------------------------------------

    def add_worker(self) -> str:
        """Spin up a new worker in a background daemon thread."""
        with self._lock:
            worker_id = f"worker-{self._next_id}"
            self._next_id += 1

        worker = IndirectWorker(worker_id=worker_id, queue_url=self.queue_url)

        t = threading.Thread(target=worker.start, daemon=True, name=worker_id)
        t.start()

        with self._lock:
            self.workers[worker_id] = worker
            self._threads[worker_id] = t

        logger.info(f"WorkerPool: added {worker_id}")
        return worker_id

    def remove_worker(self, worker_id: str) -> None:
        """Gracefully stop and remove a worker."""
        with self._lock:
            worker = self.workers.pop(worker_id, None)
            self._threads.pop(worker_id, None)

        if worker:
            worker.stop()
            logger.info(f"WorkerPool: removed {worker_id}")
        else:
            logger.warning(f"WorkerPool: unknown worker_id {worker_id}")

    def get_worker_count(self) -> int:
        """Number of registered workers (some may still be stopping)."""
        with self._lock:
            return len(self.workers)

    def get_all_stats(self) -> Dict[str, Any]:
        """Aggregated stats for all workers."""
        with self._lock:
            workers_copy = dict(self.workers)

        total_processed = 0
        total_errors = 0
        worker_stats = {}
        for wid, w in workers_copy.items():
            s = w.get_stats()
            worker_stats[wid] = s
            total_processed += s["processed"]
            total_errors += s["errors"]

        return {
            "worker_count": len(workers_copy),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "workers": worker_stats,
        }

    def stop_all(self) -> None:
        """Stop every worker in the pool."""
        with self._lock:
            ids = list(self.workers.keys())
        for wid in ids:
            self.remove_worker(wid)

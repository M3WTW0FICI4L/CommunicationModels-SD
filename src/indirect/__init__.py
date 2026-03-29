"""
Indirect communication architecture module.
RabbitMQ-based asynchronous message processing.
"""

from .producer.producer import IndirectProducer, BulkProducer
from .queue.queue_config import QueueConfig, QueueManager
from .worker.worker import IndirectWorker, WorkerPool

__all__ = [
    "IndirectProducer",
    "BulkProducer",
    "QueueConfig",
    "QueueManager",
    "IndirectWorker",
    "WorkerPool"
]

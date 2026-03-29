"""
Indirect communication worker (server side).
Consumes messages from RabbitMQ queue and processes ticket purchases.
"""

import json
import time
from typing import Dict, Any, Optional
import signal
import sys

from ...backend.storage import RedisBackend
from ...backend.ticket_manager import TicketManager
from ...common.models import BuyRequest, BuyResponse, TicketType, RequestStatus
from ...common.config import Config
from ...common.logger import setup_logger


logger = setup_logger(__name__)


class IndirectWorker:
    """
    Worker that consumes ticket purchase requests from RabbitMQ queue
    and processes them against the shared storage backend.
    """
    
    def __init__(self, worker_id: str, queue_url: Optional[str] = None):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique worker identifier
            queue_url: RabbitMQ connection URL
        """
        self.worker_id = worker_id
        self.queue_url = queue_url or self._default_queue_url()
        self.connection = None
        self.channel = None
        
        # Initialize ticket management
        self.storage = RedisBackend(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        self.ticket_manager = TicketManager(self.storage)
        
        # Worker state
        self.running = False
        self.processed_count = 0
        self.error_count = 0
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _default_queue_url(self) -> str:
        """Build default RabbitMQ connection URL from config."""
        # TODO: Build URL from Config
        pass
    
    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on signals."""
        logger.info(f"Worker {self.worker_id} received shutdown signal")
        self.stop()
        sys.exit(0)
    
    def connect(self) -> None:
        """Establish connection to RabbitMQ and initialize queue."""
        # TODO: Implement connection and queue setup
        pass
    
    def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        # TODO: Implement disconnection
        pass
    
    def start(self) -> None:
        """
        Start consuming messages from queue.
        This method blocks until stop() is called.
        """
        self.connect()
        self.storage.connect()
        self.running = True
        
        logger.info(f"Worker {self.worker_id} started, consuming messages...")
        
        # TODO: Implement message consumption loop
        # 1. Set up callback for message handling
        # 2. Start consuming from queue
        # 3. Block until stop() is called
    
    def stop(self) -> None:
        """Stop consuming messages and clean up."""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopping...")
        
        if self.channel:
            # TODO: Stop consuming
            pass
        
        self.disconnect()
        self.storage.disconnect()
        
        logger.info(f"Worker {self.worker_id} stopped. "
                   f"Processed: {self.processed_count}, Errors: {self.error_count}")
    
    def _process_message(self, message_body: str) -> None:
        """
        Process a single message from the queue.
        
        Args:
            message_body: Message body (JSON)
        """
        try:
            # TODO: Implement message processing
            # 1. Parse JSON message
            # 2. Extract client_id, request_id, ticket_type, seat_id (if numbered)
            # 3. Call ticket_manager.buy_ticket()
            # 4. Log result
            # 5. Optionally send response to response queue
            self.processed_count += 1
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get worker statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "worker_id": self.worker_id,
            "running": self.running,
            "processed": self.processed_count,
            "errors": self.error_count,
            "uptime": self.get_uptime()
        }
    
    def get_uptime(self) -> float:
        """Get worker uptime in seconds."""
        # TODO: Implement uptime calculation
        return 0.0


class WorkerPool:
    """
    Manages a pool of workers for parallel message processing.
    Allows dynamic scaling of workers.
    """
    
    def __init__(self, initial_workers: int = 1, queue_url: Optional[str] = None):
        """
        Initialize worker pool.
        
        Args:
            initial_workers: Number of workers to create initially
            queue_url: RabbitMQ connection URL
        """
        self.queue_url = queue_url
        self.workers: Dict[str, IndirectWorker] = {}
        self.next_worker_id = 0
        
        # Create initial workers
        for _ in range(initial_workers):
            self.add_worker()
    
    def add_worker(self) -> str:
        """
        Add a new worker to the pool.
        
        Returns:
            Worker ID
        """
        # TODO: Implement worker creation and startup
        pass
    
    def remove_worker(self, worker_id: str) -> None:
        """
        Remove a worker from the pool.
        
        Args:
            worker_id: Worker ID to remove
        """
        # TODO: Implement worker shutdown and removal
        pass
    
    def get_worker_count(self) -> int:
        """Get current number of running workers."""
        # TODO: Return count of active workers
        pass
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all workers in the pool."""
        # TODO: Aggregate stats from all workers
        pass

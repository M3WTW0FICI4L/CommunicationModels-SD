"""
Centralized configuration for the ticket acquisition system.
"""

import os
from typing import Dict, Any


class Config:
    """Base configuration class."""
    
    # Ticket constraints
    MAX_TICKETS = 20000
    MIN_SEAT_ID = 1
    MAX_SEAT_ID = 20000
    
    # Storage configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    
    # RabbitMQ configuration
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
    RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
    
    # Direct API configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_WORKERS = int(os.getenv("API_WORKERS", 4))
    
    # Indirect (RabbitMQ) configuration
    QUEUE_NAME = "ticket_purchases"
    QUEUE_MAX_PRIORITY = 10
    WORKER_COUNT = int(os.getenv("WORKER_COUNT", 1))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Timeout and retry configuration
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {k: getattr(cls, k) for k in dir(cls) 
                if not k.startswith('_') and k.isupper()}

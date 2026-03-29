"""
Ticket acquisition backend module.
Core business logic for ticket management.
"""

from .storage import StorageBackend, RedisBackend
from .ticket_manager import TicketManager
from .consistency import ConsistencyManager

__all__ = ["StorageBackend", "RedisBackend", "TicketManager", "ConsistencyManager"]

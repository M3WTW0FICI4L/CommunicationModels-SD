"""
Abstract storage layer for ticket management.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to storage."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to storage."""
        pass
    
    @abstractmethod
    def get_unnumbered_count(self) -> int:
        """Get current count of sold unnumbered tickets."""
        pass
    
    @abstractmethod
    def increment_unnumbered(self) -> bool:
        """
        Atomically increment unnumbered tickets counter.
        
        Returns:
            True if < 20000, False if overflow
        """
        pass
    
    @abstractmethod
    def set_numbered_seat(self, seat_id: int) -> bool:
        """
        Atomically set a numbered seat as sold.
        
        Args:
            seat_id: Seat number to mark as sold
        
        Returns:
            True if seat was available and is now sold, False if already sold
        """
        pass
    
    @abstractmethod
    def is_numbered_seat_sold(self, seat_id: int) -> bool:
        """Check if a numbered seat is sold."""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset all ticket state (for testing)."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        pass


class RedisBackend(StorageBackend):
    """Redis-based storage backend."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """Initialize Redis backend."""
        self.host = host
        self.port = port
        self.db = db
        self.client = None
    
    def connect(self) -> None:
        """Establish connection to Redis."""
        # TODO: Implement Redis connection
        pass
    
    def disconnect(self) -> None:
        """Close connection to Redis."""
        # TODO: Implement Redis disconnection
        pass
    
    def get_unnumbered_count(self) -> int:
        """Get current count of sold unnumbered tickets."""
        # TODO: Implement Redis GET
        return 0
    
    def increment_unnumbered(self) -> bool:
        """Atomically increment unnumbered tickets counter."""
        # TODO: Implement atomic INCR with overflow protection
        return False
    
    def set_numbered_seat(self, seat_id: int) -> bool:
        """Atomically set a numbered seat as sold."""
        # TODO: Implement atomic SETNX for numbered seats
        return False
    
    def is_numbered_seat_sold(self, seat_id: int) -> bool:
        """Check if a numbered seat is sold."""
        # TODO: Implement Redis GET for seat
        return False
    
    def reset(self) -> None:
        """Reset all ticket state."""
        # TODO: Implement Redis FLUSHDB or specific key cleanup
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        # TODO: Implement stats retrieval
        return {}

"""
Consistency enforcement and transaction handling.
"""

from typing import Callable, Any
from threading import Lock
import time
from contextlib import contextmanager


class ConsistencyManager:
    """Manages consistency guarantees across operations."""
    
    def __init__(self, redis_client=None):
        """Initialize consistency manager."""
        self.locks: dict[str, Lock] = {}
        self.redis_client = redis_client  # Optional Redis client for distributed locks
    
    def get_seat_lock(self, seat_id: int) -> Lock:
        """
        Get or create a lock for a specific seat.
        Used for fine-grained locking in numbered tickets.
        """
        key = f"seat_{seat_id}"
        if key not in self.locks:
            self.locks[key] = Lock()
        return self.locks[key]
    
    def acquire_lock(self, key: str, timeout: float = 10.0) -> bool:
        """
        Acquire a distributed lock.
        Can be implemented using Redis or similar.
        """
        if self.redis_client:
            # Use Redis for distributed lock
            lock_key = f"lock:{key}"
            # Set with NX (if not exists) and PX (expire in milliseconds)
            return self.redis_client.set(lock_key, "1", nx=True, px=int(timeout * 1000))
        else:
            # Fallback to in-memory lock (not distributed)
            if key not in self.locks:
                self.locks[key] = Lock()
            return self.locks[key].acquire(timeout=timeout)
    
    def release_lock(self, key: str) -> None:
        """Release a distributed lock."""
        if self.redis_client:
            lock_key = f"lock:{key}"
            self.redis_client.delete(lock_key)
        else:
            if key in self.locks:
                self.locks[key].release()
    
    @contextmanager
    def with_lock(self, key: str, timeout: float = 10.0):
        """
        Context manager for lock acquisition.
        
        Usage:
            with consistency_mgr.with_lock("seat_123"):
                # Protected code
        """
        acquired = self.acquire_lock(key, timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for {key} within {timeout}s")
        try:
            yield
        finally:
            self.release_lock(key)


def transactional(func: Callable) -> Callable:
    """
    Decorator for transactional operations.
    Ensures consistent state before/after execution.
    """
    def wrapper(*args, **kwargs) -> Any:
        # TODO: Implement transactional wrapper
        # For now, just execute the function
        # In a real implementation, this would:
        # 1. Begin transaction (e.g., Redis MULTI)
        # 2. Execute function
        # 3. Commit or rollback on exception
        try:
            result = func(*args, **kwargs)
            # Commit logic here if needed
            return result
        except Exception as e:
            # Rollback logic here if needed
            raise e
    return wrapper

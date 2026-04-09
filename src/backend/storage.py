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
            True if ticket was sold (count was < 20000), False if oversold.
        """
        pass

    @abstractmethod
    def set_numbered_seat(self, seat_id: int) -> bool:
        """
        Atomically set a numbered seat as sold.

        Args:
            seat_id: Seat number to mark as sold

        Returns:
            True if seat was available and is now sold, False if already sold.
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


# Lua script: atomic INCR with upper-bound guard.
# Returns 1 if the ticket was sold, 0 if the limit was already reached.
_INCR_BOUNDED_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current > tonumber(ARGV[1]) then
    redis.call('DECR', KEYS[1])
    return 0
end
return 1
"""

# Redis key names
_KEY_UNNUMBERED = "tickets:unnumbered:count"
_KEY_NUMBERED_PREFIX = "tickets:numbered:"


class RedisBackend(StorageBackend):
    """Redis-based storage backend.

    Uses:
    - A single integer counter for unnumbered tickets (atomic INCR with Lua
      guard so we never sell more than MAX_TICKETS).
    - One key per numbered seat (SET … NX for atomic claim).
    """

    MAX_TICKETS = 20_000

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client = None
        self._incr_script = None  # registered Lua script handle

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish connection to Redis and register Lua scripts."""
        import redis  # imported here so the module is importable without redis
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True,
        )
        self.client.ping()  # fail fast if Redis is unreachable
        self._incr_script = self.client.register_script(_INCR_BOUNDED_SCRIPT)

    def disconnect(self) -> None:
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            self.client = None

    # ------------------------------------------------------------------
    # Unnumbered tickets
    # ------------------------------------------------------------------

    def get_unnumbered_count(self) -> int:
        """Return the current number of sold unnumbered tickets."""
        value = self.client.get(_KEY_UNNUMBERED)
        return int(value) if value else 0

    def increment_unnumbered(self) -> bool:
        """
        Atomically try to sell one unnumbered ticket.

        Uses a Lua script so the check-and-increment is atomic even under
        heavy concurrency.
        """
        result = self._incr_script(keys=[_KEY_UNNUMBERED], args=[self.MAX_TICKETS])
        return bool(result)

    # ------------------------------------------------------------------
    # Numbered tickets
    # ------------------------------------------------------------------

    def _seat_key(self, seat_id: int) -> str:
        return f"{_KEY_NUMBERED_PREFIX}{seat_id}"

    def set_numbered_seat(self, seat_id: int) -> bool:
        """
        Atomically claim a numbered seat.

        Uses SET … NX (set if not exists) which is atomic in Redis.
        """
        result = self.client.set(self._seat_key(seat_id), "sold", nx=True)
        return result is True  # True = key was set (seat was free)

    def is_numbered_seat_sold(self, seat_id: int) -> bool:
        """Check if a numbered seat is already sold."""
        return self.client.exists(self._seat_key(seat_id)) == 1

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Delete all ticket-related keys (for testing / re-runs)."""
        # Delete unnumbered counter
        self.client.delete(_KEY_UNNUMBERED)
        # Delete all numbered-seat keys
        pattern = f"{_KEY_NUMBERED_PREFIX}*"
        cursor = 0
        while True:
            cursor, keys = self.client.scan(cursor, match=pattern, count=1000)
            if keys:
                self.client.delete(*keys)
            if cursor == 0:
                break

    def get_stats(self) -> Dict[str, Any]:
        """Return a stats dictionary with current sold counts."""
        unnumbered = self.get_unnumbered_count()
        # Count numbered seats by scanning keys
        numbered = len(list(self.client.scan_iter(
            match=f"{_KEY_NUMBERED_PREFIX}*", count=1000
        )))
        return {
            "unnumbered_sold": unnumbered,
            "unnumbered_remaining": max(0, self.MAX_TICKETS - unnumbered),
            "numbered_sold": numbered,
        }

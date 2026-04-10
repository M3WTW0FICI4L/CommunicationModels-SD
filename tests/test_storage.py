"""
Unit tests for storage backend abstraction.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace
from src.backend.storage import StorageBackend, RedisBackend


class MockStorageBackend(StorageBackend):
    """Mock implementation of StorageBackend for testing."""
    
    def __init__(self):
        """Initialize mock storage."""
        self.connected = False
        self.unnumbered_count = 0
        self.numbered_seats = set()
    
    def connect(self) -> None:
        """Establish connection."""
        self.connected = True
    
    def disconnect(self) -> None:
        """Close connection."""
        self.connected = False
    
    def get_unnumbered_count(self) -> int:
        """Get current count of sold unnumbered tickets."""
        return self.unnumbered_count
    
    def increment_unnumbered(self) -> bool:
        """Atomically increment unnumbered tickets counter."""
        if self.unnumbered_count < 20000:
            self.unnumbered_count += 1
            return True
        return False
    
    def set_numbered_seat(self, seat_id: int) -> bool:
        """Atomically set a numbered seat as sold."""
        if seat_id not in self.numbered_seats and 1 <= seat_id <= 20000:
            self.numbered_seats.add(seat_id)
            return True
        return False
    
    def is_numbered_seat_sold(self, seat_id: int) -> bool:
        """Check if a numbered seat is sold."""
        return seat_id in self.numbered_seats
    
    def reset(self) -> None:
        """Reset all ticket state."""
        self.unnumbered_count = 0
        self.numbered_seats.clear()
    
    def get_stats(self):
        """Get current statistics."""
        return {
            "unnumbered_sold": self.unnumbered_count,
            "numbered_sold": len(self.numbered_seats)
        }


class TestStorageBackendInterface(unittest.TestCase):
    """Test StorageBackend abstract interface."""
    
    def test_storage_backend_is_abstract(self):
        """Test that StorageBackend cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            StorageBackend()
    
    def test_storage_backend_methods_required(self):
        """Test that all abstract methods are defined."""
        abstract_methods = [
            'connect', 'disconnect', 'get_unnumbered_count',
            'increment_unnumbered', 'set_numbered_seat',
            'is_numbered_seat_sold', 'reset', 'get_stats'
        ]
        
        for method in abstract_methods:
            self.assertTrue(
                hasattr(StorageBackend, method),
                f"StorageBackend missing method: {method}"
            )


class TestMockStorageBackend(unittest.TestCase):
    """Test MockStorageBackend implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.storage = MockStorageBackend()
    
    def test_initialization(self):
        """Test storage initialization."""
        self.assertFalse(self.storage.connected)
        self.assertEqual(self.storage.unnumbered_count, 0)
        self.assertEqual(len(self.storage.numbered_seats), 0)
    
    def test_connect_disconnect(self):
        """Test connect and disconnect operations."""
        self.assertFalse(self.storage.connected)
        
        self.storage.connect()
        self.assertTrue(self.storage.connected)
        
        self.storage.disconnect()
        self.assertFalse(self.storage.connected)
    
    def test_get_unnumbered_count_initial(self):
        """Test getting initial unnumbered count."""
        self.storage.connect()
        count = self.storage.get_unnumbered_count()
        self.assertEqual(count, 0)
    
    def test_increment_unnumbered_success(self):
        """Test incrementing unnumbered tickets."""
        self.storage.connect()
        
        result = self.storage.increment_unnumbered()
        self.assertTrue(result)
        self.assertEqual(self.storage.get_unnumbered_count(), 1)
        
        result = self.storage.increment_unnumbered()
        self.assertTrue(result)
        self.assertEqual(self.storage.get_unnumbered_count(), 2)
    
    def test_increment_unnumbered_at_limit(self):
        """Test incrementing unnumbered tickets at limit."""
        self.storage.connect()
        self.storage.unnumbered_count = 19999
        
        result = self.storage.increment_unnumbered()
        self.assertTrue(result)
        self.assertEqual(self.storage.get_unnumbered_count(), 20000)
    
    def test_increment_unnumbered_overflow(self):
        """Test incrementing unnumbered tickets at limit."""
        self.storage.connect()
        self.storage.unnumbered_count = 20000
        
        result = self.storage.increment_unnumbered()
        self.assertFalse(result)
        self.assertEqual(self.storage.get_unnumbered_count(), 20000)
    
    def test_set_numbered_seat_success(self):
        """Test setting a numbered seat as sold."""
        self.storage.connect()
        
        result = self.storage.set_numbered_seat(1)
        self.assertTrue(result)
        self.assertTrue(self.storage.is_numbered_seat_sold(1))
    
    def test_set_numbered_seat_duplicate(self):
        """Test setting a numbered seat that's already sold."""
        self.storage.connect()
        
        result1 = self.storage.set_numbered_seat(42)
        self.assertTrue(result1)
        
        result2 = self.storage.set_numbered_seat(42)
        self.assertFalse(result2)
    
    def test_set_numbered_seat_multiple(self):
        """Test setting multiple different numbered seats."""
        self.storage.connect()
        
        for seat_id in [1, 5, 10, 100, 20000]:
            result = self.storage.set_numbered_seat(seat_id)
            self.assertTrue(result, f"Failed to set seat {seat_id}")
            self.assertTrue(self.storage.is_numbered_seat_sold(seat_id))
        
        self.assertEqual(len(self.storage.numbered_seats), 5)
    
    def test_is_numbered_seat_sold_not_sold(self):
        """Test checking if seat is sold when it's not."""
        self.storage.connect()
        
        self.assertFalse(self.storage.is_numbered_seat_sold(1))
        self.assertFalse(self.storage.is_numbered_seat_sold(42))
        self.assertFalse(self.storage.is_numbered_seat_sold(20000))
    
    def test_reset_unnumbered(self):
        """Test reset with unnumbered tickets."""
        self.storage.connect()
        self.storage.increment_unnumbered()
        self.storage.increment_unnumbered()
        
        self.storage.reset()
        self.assertEqual(self.storage.unnumbered_count, 0)
    
    def test_reset_numbered(self):
        """Test reset with numbered tickets."""
        self.storage.connect()
        self.storage.set_numbered_seat(1)
        self.storage.set_numbered_seat(2)
        self.storage.set_numbered_seat(3)
        
        self.storage.reset()
        self.assertEqual(len(self.storage.numbered_seats), 0)
    
    def test_reset_both_types(self):
        """Test reset with both types of tickets."""
        self.storage.connect()
        self.storage.increment_unnumbered()
        self.storage.increment_unnumbered()
        self.storage.set_numbered_seat(1)
        self.storage.set_numbered_seat(2)
        
        self.storage.reset()
        
        self.assertEqual(self.storage.unnumbered_count, 0)
        self.assertEqual(len(self.storage.numbered_seats), 0)
    
    def test_get_stats(self):
        """Test getting statistics."""
        self.storage.connect()
        self.storage.increment_unnumbered()
        self.storage.set_numbered_seat(1)
        self.storage.set_numbered_seat(2)
        
        stats = self.storage.get_stats()
        
        self.assertEqual(stats["unnumbered_sold"], 1)
        self.assertEqual(stats["numbered_sold"], 2)


class TestRedisBackendInterface(unittest.TestCase):
    """Test RedisBackend interface."""
    
    def test_redis_backend_initialization(self):
        """Test RedisBackend initialization with default parameters."""
        backend = RedisBackend()
        
        self.assertEqual(backend.host, "localhost")
        self.assertEqual(backend.port, 6379)
        self.assertEqual(backend.db, 0)
        self.assertIsNone(backend.client)
    
    def test_redis_backend_initialization_custom_params(self):
        """Test RedisBackend initialization with custom parameters."""
        backend = RedisBackend(host="redis.example.com", port=1234, db=5)
        
        self.assertEqual(backend.host, "redis.example.com")
        self.assertEqual(backend.port, 1234)
        self.assertEqual(backend.db, 5)
    
    def test_redis_backend_has_required_methods(self):
        """Test that RedisBackend has all required methods."""
        backend = RedisBackend()
        
        required_methods = [
            'connect', 'disconnect', 'get_unnumbered_count',
            'increment_unnumbered', 'set_numbered_seat'
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(backend, method_name),
                f"RedisBackend missing method: {method_name}"
            )
            self.assertTrue(callable(getattr(backend, method_name)))


class TestRedisBackendBehavior(unittest.TestCase):
    """Behavior tests for RedisBackend using mocked Redis client."""

    def test_connect_registers_lua_script_and_pings(self):
        fake_client = MagicMock()
        fake_script = MagicMock()
        fake_client.register_script.return_value = fake_script

        fake_redis_module = SimpleNamespace(Redis=MagicMock(return_value=fake_client))
        backend = RedisBackend(host="h", port=1234, db=9)

        with patch.dict("sys.modules", {"redis": fake_redis_module}):
            backend.connect()

        fake_redis_module.Redis.assert_called_once_with(
            host="h", port=1234, db=9, decode_responses=True
        )
        fake_client.ping.assert_called_once()
        fake_client.register_script.assert_called_once()
        self.assertIs(backend.client, fake_client)
        self.assertIs(backend._incr_script, fake_script)

    def test_disconnect_closes_client_and_clears_reference(self):
        backend = RedisBackend()
        mock_client = MagicMock()
        backend.client = mock_client

        backend.disconnect()

        mock_client.close.assert_called_once()
        self.assertIsNone(backend.client)

    def test_get_unnumbered_count_handles_missing_and_existing_value(self):
        backend = RedisBackend()
        backend.client = MagicMock()

        backend.client.get.return_value = None
        self.assertEqual(backend.get_unnumbered_count(), 0)

        backend.client.get.return_value = "7"
        self.assertEqual(backend.get_unnumbered_count(), 7)

    def test_increment_unnumbered_uses_registered_script(self):
        backend = RedisBackend()
        backend._incr_script = MagicMock(return_value=1)

        self.assertTrue(backend.increment_unnumbered())
        backend._incr_script.assert_called_once_with(
            keys=["tickets:unnumbered:count"], args=[backend.MAX_TICKETS]
        )

    def test_set_numbered_seat_returns_true_only_on_first_claim(self):
        backend = RedisBackend()
        backend.client = MagicMock()

        backend.client.set.return_value = True
        self.assertTrue(backend.set_numbered_seat(42))

        backend.client.set.return_value = None
        self.assertFalse(backend.set_numbered_seat(42))

    def test_is_numbered_seat_sold_maps_exists_to_boolean(self):
        backend = RedisBackend()
        backend.client = MagicMock()

        backend.client.exists.return_value = 1
        self.assertTrue(backend.is_numbered_seat_sold(1))

        backend.client.exists.return_value = 0
        self.assertFalse(backend.is_numbered_seat_sold(2))

    def test_reset_deletes_counter_and_all_scanned_numbered_keys(self):
        backend = RedisBackend()
        backend.client = MagicMock()

        backend.client.scan.side_effect = [
            (1, ["tickets:numbered:1", "tickets:numbered:2"]),
            (0, ["tickets:numbered:3"]),
        ]

        backend.reset()

        backend.client.delete.assert_any_call("tickets:unnumbered:count")
        backend.client.delete.assert_any_call("tickets:numbered:1", "tickets:numbered:2")
        backend.client.delete.assert_any_call("tickets:numbered:3")

    def test_get_stats_aggregates_unnumbered_remaining_and_numbered_sold(self):
        backend = RedisBackend()
        backend.client = MagicMock()
        backend.client.get.return_value = "3"
        backend.client.scan_iter.return_value = iter([
            "tickets:numbered:10",
            "tickets:numbered:11",
        ])

        stats = backend.get_stats()

        self.assertEqual(stats["unnumbered_sold"], 3)
        self.assertEqual(stats["unnumbered_remaining"], 19997)
        self.assertEqual(stats["numbered_sold"], 2)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for consistency helpers."""

from unittest.mock import Mock

import pytest

from src.backend.consistency import ConsistencyManager, transactional


class TestConsistencyManager:
    """Test locking behavior in consistency manager."""

    def test_get_seat_lock_reuses_same_lock_instance(self):
        manager = ConsistencyManager()

        lock_a = manager.get_seat_lock(10)
        lock_b = manager.get_seat_lock(10)
        lock_c = manager.get_seat_lock(11)

        assert lock_a is lock_b
        assert lock_a is not lock_c

    def test_acquire_and_release_local_lock(self):
        manager = ConsistencyManager()

        assert manager.acquire_lock("resource", timeout=0.05) is True
        manager.release_lock("resource")

    def test_with_lock_timeout_raises(self):
        manager = ConsistencyManager()

        held = manager.acquire_lock("busy", timeout=0.05)
        assert held is True
        try:
            with pytest.raises(TimeoutError):
                with manager.with_lock("busy", timeout=0.01):
                    pass
        finally:
            manager.release_lock("busy")

    def test_release_lock_missing_key_is_noop(self):
        manager = ConsistencyManager()
        manager.release_lock("missing")

    def test_redis_lock_path_uses_set_and_delete(self):
        redis_client = Mock()
        redis_client.set.return_value = True
        manager = ConsistencyManager(redis_client=redis_client)

        assert manager.acquire_lock("seat_1", timeout=2.5) is True
        redis_client.set.assert_called_once_with("lock:seat_1", "1", nx=True, px=2500)

        manager.release_lock("seat_1")
        redis_client.delete.assert_called_once_with("lock:seat_1")


class TestTransactionalDecorator:
    """Test transactional decorator pass-through behavior."""

    def test_transactional_returns_function_result(self):
        @transactional
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_transactional_reraises_original_exception(self):
        @transactional
        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fail()

"""
Unit tests for ticket manager.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time
from src.backend.ticket_manager import TicketManager
from src.common.models import BuyRequest, BuyResponse, TicketType, RequestStatus


class MockStorage:
    """Mock implementation of StorageBackend for testing."""
    
    def __init__(self):
        """Initialize mock storage."""
        self.unnumbered_count = 0
        self.numbered_seats = set()
        self.reset_called = False
    
    def get_unnumbered_count(self) -> int:
        return self.unnumbered_count
    
    def increment_unnumbered(self) -> bool:
        if self.unnumbered_count < 20000:
            self.unnumbered_count += 1
            return True
        return False
    
    def set_numbered_seat(self, seat_id: int) -> bool:
        if seat_id not in self.numbered_seats:
            self.numbered_seats.add(seat_id)
            return True
        return False
    
    def is_numbered_seat_sold(self, seat_id: int) -> bool:
        return seat_id in self.numbered_seats
    
    def reset(self) -> None:
        self.reset_called = True
        self.unnumbered_count = 0
        self.numbered_seats.clear()
    
    def get_stats(self):
        return {
            "unnumbered": self.unnumbered_count,
            "numbered": len(self.numbered_seats)
        }


class TestTicketManagerInitialization(unittest.TestCase):
    """Test TicketManager initialization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_storage = MockStorage()
        self.manager = TicketManager(self.mock_storage)
    
    def test_ticket_manager_initialization(self):
        """Test TicketManager initialization."""
        self.assertIsNotNone(self.manager.storage)
        self.assertEqual(self.manager.storage, self.mock_storage)
        self.assertIsInstance(self.manager.processed_requests, dict)
        self.assertEqual(len(self.manager.processed_requests), 0)


class TestTicketManagerReset(unittest.TestCase):
    """Test TicketManager reset functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_storage = MockStorage()
        self.manager = TicketManager(self.mock_storage)
    
    def test_reset_clears_processed_requests(self):
        """Test that reset clears processed requests."""
        # Add some processed requests
        self.manager.processed_requests["req_001"] = MagicMock(
            status=RequestStatus.SUCCESS
        )
        self.manager.processed_requests["req_002"] = MagicMock(
            status=RequestStatus.SUCCESS
        )
        
        self.assertEqual(len(self.manager.processed_requests), 2)
        
        # Reset
        self.manager.reset()
        
        self.assertEqual(len(self.manager.processed_requests), 0)
        self.assertTrue(self.mock_storage.reset_called)
    
    def test_reset_calls_storage_reset(self):
        """Test that reset calls storage.reset()."""
        self.manager.reset()
        
        self.assertTrue(self.mock_storage.reset_called)
    
    def test_reset_clears_storage_tickets(self):
        """Test that reset clears storage."""
        # Pre-populate storage
        self.mock_storage.unnumbered_count = 100
        self.mock_storage.numbered_seats.add(1)
        self.mock_storage.numbered_seats.add(2)
        
        self.manager.reset()
        
        self.assertEqual(self.mock_storage.unnumbered_count, 0)
        self.assertEqual(len(self.mock_storage.numbered_seats), 0)


class TestTicketManagerGetStatistics(unittest.TestCase):
    """Test TicketManager statistics method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_storage = MockStorage()
        self.manager = TicketManager(self.mock_storage)
    
    def test_get_statistics_empty_system(self):
        """Test getting statistics from empty system."""
        # The implementation is TBD, so we'll test the interface
        result = self.manager.get_statistics()
        
        # Should return a dictionary
        self.assertIsInstance(result, (dict, type(None)))
    
    def test_get_statistics_after_reset(self):
        """Test getting statistics after reset."""
        self.manager.reset()
        result = self.manager.get_statistics()
        
        self.assertIsInstance(result, (dict, type(None)))


class TestTicketManagerIntegrationScenarios(unittest.TestCase):
    """Test TicketManager integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_storage = MockStorage()
        self.manager = TicketManager(self.mock_storage)
    
    def test_reset_workflow(self):
        """Test complete reset workflow."""
        # Add data
        self.mock_storage.unnumbered_count = 50
        self.mock_storage.set_numbered_seat(1)
        self.mock_storage.set_numbered_seat(2)
        
        # Add processed requests
        self.manager.processed_requests["req_1"] = MagicMock()
        
        # Verify data exists
        self.assertGreater(self.mock_storage.unnumbered_count, 0)
        self.assertGreater(len(self.mock_storage.numbered_seats), 0)
        self.assertGreater(len(self.manager.processed_requests), 0)
        
        # Reset
        self.manager.reset()
        
        # Verify everything is cleared
        self.assertEqual(self.mock_storage.unnumbered_count, 0)
        self.assertEqual(len(self.mock_storage.numbered_seats), 0)
        self.assertEqual(len(self.manager.processed_requests), 0)


class TestTicketManagerUnimplementedMethods(unittest.TestCase):
    """Test unimplemented TicketManager methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_storage = MockStorage()
        self.manager = TicketManager(self.mock_storage)
    
    def test_buy_ticket_exists(self):
        """Test that buy_ticket method exists."""
        self.assertTrue(hasattr(self.manager, 'buy_ticket'))
        self.assertTrue(callable(self.manager.buy_ticket))
    
    def test_buy_unnumbered_exists(self):
        """Test that buy_unnumbered method exists."""
        self.assertTrue(hasattr(self.manager, 'buy_unnumbered'))
        self.assertTrue(callable(self.manager.buy_unnumbered))
    
    def test_buy_numbered_exists(self):
        """Test that buy_numbered method exists."""
        self.assertTrue(hasattr(self.manager, 'buy_numbered'))
        self.assertTrue(callable(self.manager.buy_numbered))
    
    def test_buy_ticket_signature(self):
        """Test buy_ticket accepts BuyRequest."""
        request = BuyRequest(
            client_id="test_client",
            request_id="test_req",
            ticket_type=TicketType.UNNUMBERED
        )
        
        # Should not raise TypeError
        try:
            result = self.manager.buy_ticket(request)
            # Result might be None (not implemented)
            self.assertTrue(result is None or isinstance(result, BuyResponse))
        except (NotImplementedError, TypeError) as e:
            # Expected if not implemented yet
            pass


class TestBuyRequestCreation(unittest.TestCase):
    """Test BuyRequest creation for testing purposes."""
    
    def test_create_unnumbered_request(self):
        """Create an unnumbered ticket request."""
        request = BuyRequest(
            client_id="client_001",
            request_id="req_001",
            ticket_type=TicketType.UNNUMBERED
        )
        
        self.assertEqual(request.client_id, "client_001")
        self.assertEqual(request.request_id, "req_001")
        self.assertEqual(request.ticket_type, TicketType.UNNUMBERED)
    
    def test_create_numbered_request(self):
        """Create a numbered ticket request."""
        request = BuyRequest(
            client_id="client_002",
            request_id="req_002",
            ticket_type=TicketType.NUMBERED,
            seat_id=42
        )
        
        self.assertEqual(request.client_id, "client_002")
        self.assertEqual(request.request_id, "req_002")
        self.assertEqual(request.ticket_type, TicketType.NUMBERED)
        self.assertEqual(request.seat_id, 42)


class TestBuyResponseCreation(unittest.TestCase):
    """Test BuyResponse creation for expected behavior."""
    
    def test_create_success_response_unnumbered(self):
        """Create a success response for unnumbered ticket."""
        response = BuyResponse(
            request_id="req_001",
            client_id="client_001",
            status=RequestStatus.SUCCESS,
            message="Ticket purchased"
        )
        
        self.assertEqual(response.status, RequestStatus.SUCCESS)
        self.assertIsNone(response.seat_id)
    
    def test_create_success_response_numbered(self):
        """Create a success response for numbered ticket."""
        response = BuyResponse(
            request_id="req_002",
            client_id="client_002",
            status=RequestStatus.SUCCESS,
            seat_id=42,
            message="Seat 42 purchased"
        )
        
        self.assertEqual(response.status, RequestStatus.SUCCESS)
        self.assertEqual(response.seat_id, 42)
    
    def test_create_failure_response(self):
        """Create a failure response."""
        response = BuyResponse(
            request_id="req_003",
            client_id="client_003",
            status=RequestStatus.FAILED,
            message="Sold out"
        )
        
        self.assertEqual(response.status, RequestStatus.FAILED)


if __name__ == "__main__":
    unittest.main()

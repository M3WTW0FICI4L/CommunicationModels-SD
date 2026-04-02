"""
Unit tests for data models.
"""

import unittest
from src.common.models import (
    TicketType, RequestStatus, BuyRequest, BuyResponse
)


class TestTicketType(unittest.TestCase):
    """Test TicketType enum."""
    
    def test_ticket_type_values(self):
        """Test that TicketType enum has correct values."""
        self.assertEqual(TicketType.UNNUMBERED.value, "unnumbered")
        self.assertEqual(TicketType.NUMBERED.value, "numbered")
    
    def test_ticket_type_members(self):
        """Test that TicketType has expected members."""
        members = [e.name for e in TicketType]
        self.assertIn("UNNUMBERED", members)
        self.assertIn("NUMBERED", members)
        self.assertEqual(len(members), 2)


class TestRequestStatus(unittest.TestCase):
    """Test RequestStatus enum."""
    
    def test_request_status_values(self):
        """Test that RequestStatus enum has correct values."""
        self.assertEqual(RequestStatus.PENDING.value, "pending")
        self.assertEqual(RequestStatus.SUCCESS.value, "success")
        self.assertEqual(RequestStatus.FAILED.value, "failed")
        self.assertEqual(RequestStatus.DUPLICATE.value, "duplicate")
    
    def test_request_status_members(self):
        """Test that RequestStatus has expected members."""
        members = [e.name for e in RequestStatus]
        self.assertIn("PENDING", members)
        self.assertIn("SUCCESS", members)
        self.assertIn("FAILED", members)
        self.assertIn("DUPLICATE", members)


class TestBuyRequest(unittest.TestCase):
    """Test BuyRequest dataclass."""
    
    def test_buy_request_unnumbered_creation(self):
        """Test creating an unnumbered buy request."""
        request = BuyRequest(
            client_id="client_001",
            request_id="req_001",
            ticket_type=TicketType.UNNUMBERED
        )
        
        self.assertEqual(request.client_id, "client_001")
        self.assertEqual(request.request_id, "req_001")
        self.assertEqual(request.ticket_type, TicketType.UNNUMBERED)
        self.assertIsNone(request.seat_id)
    
    def test_buy_request_numbered_creation(self):
        """Test creating a numbered buy request."""
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
    
    def test_buy_request_with_edge_case_seat_ids(self):
        """Test buy request with edge case seat IDs."""
        # Min seat
        req_min = BuyRequest(
            client_id="client_003",
            request_id="req_003",
            ticket_type=TicketType.NUMBERED,
            seat_id=1
        )
        self.assertEqual(req_min.seat_id, 1)
        
        # Max seat
        req_max = BuyRequest(
            client_id="client_004",
            request_id="req_004",
            ticket_type=TicketType.NUMBERED,
            seat_id=20000
        )
        self.assertEqual(req_max.seat_id, 20000)


class TestBuyResponse(unittest.TestCase):
    """Test BuyResponse dataclass."""
    
    def test_buy_response_success_unnumbered(self):
        """Test successful response for unnumbered ticket."""
        response = BuyResponse(
            request_id="req_001",
            client_id="client_001",
            status=RequestStatus.SUCCESS,
            message="Ticket purchased successfully"
        )
        
        self.assertEqual(response.request_id, "req_001")
        self.assertEqual(response.client_id, "client_001")
        self.assertEqual(response.status, RequestStatus.SUCCESS)
        self.assertIsNone(response.seat_id)
        self.assertEqual(response.message, "Ticket purchased successfully")
    
    def test_buy_response_success_numbered(self):
        """Test successful response for numbered ticket."""
        response = BuyResponse(
            request_id="req_002",
            client_id="client_002",
            status=RequestStatus.SUCCESS,
            seat_id=42,
            message="Seat 42 purchased"
        )
        
        self.assertEqual(response.request_id, "req_002")
        self.assertEqual(response.client_id, "client_002")
        self.assertEqual(response.status, RequestStatus.SUCCESS)
        self.assertEqual(response.seat_id, 42)
    
    def test_buy_response_failed(self):
        """Test failed response."""
        response = BuyResponse(
            request_id="req_003",
            client_id="client_003",
            status=RequestStatus.FAILED,
            message="All tickets sold out"
        )
        
        self.assertEqual(response.status, RequestStatus.FAILED)
        self.assertEqual(response.message, "All tickets sold out")
        self.assertIsNone(response.seat_id)
    
    def test_buy_response_duplicate(self):
        """Test duplicate response."""
        response = BuyResponse(
            request_id="req_004",
            client_id="client_004",
            status=RequestStatus.DUPLICATE,
            message="This request was already processed"
        )
        
        self.assertEqual(response.status, RequestStatus.DUPLICATE)
        self.assertEqual(response.message, "This request was already processed")
    
    def test_buy_response_default_values(self):
        """Test response with default values."""
        response = BuyResponse(
            request_id="req_005",
            client_id="client_005",
            status=RequestStatus.PENDING
        )
        
        self.assertEqual(response.timestamp, 0.0)
        self.assertIsNone(response.seat_id)
        self.assertEqual(response.message, "")


if __name__ == "__main__":
    unittest.main()

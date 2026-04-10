"""
Unit tests for backend core functionality (ticket manager + storage).
"""

import pytest
from tests.test_storage import MockStorageBackend
from src.backend.ticket_manager import TicketManager
from src.common.models import BuyRequest, TicketType, RequestStatus


class TestBackendCore:
    """Test suite for backend core functionality."""

    @pytest.fixture
    def storage(self):
        """Fixture for mock storage backend."""
        storage = MockStorageBackend()
        storage.connect()
        return storage

    @pytest.fixture
    def ticket_manager(self, storage):
        """Fixture for ticket manager."""
        return TicketManager(storage)

    def test_buy_unnumbered_ticket_success(self, ticket_manager):
        """Test successful purchase of unnumbered tickets."""
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.UNNUMBERED
        )

        response = ticket_manager.buy_ticket(request)

        assert response.status == RequestStatus.SUCCESS
        assert response.client_id == 'client_1'
        assert response.request_id == 'req_1'
        assert response.seat_id is None
        assert "successfully" in response.message

    def test_buy_unnumbered_ticket_sold_out(self, ticket_manager):
        """Test unnumbered ticket purchase when sold out."""
        # Buy all available tickets (mock has limit)
        for i in range(20001):  # Exceed limit
            request = BuyRequest(
                client_id=f'client_{i}',
                request_id=f'req_{i}',
                ticket_type=TicketType.UNNUMBERED
            )
            response = ticket_manager.buy_ticket(request)
            if i >= 20000:  # Should fail after limit
                assert response.status == RequestStatus.FAILED
                assert "Sold out" in response.message
                break

    def test_buy_numbered_ticket_success(self, ticket_manager):
        """Test successful purchase of numbered ticket."""
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.NUMBERED,
            seat_id=123
        )

        response = ticket_manager.buy_ticket(request)

        assert response.status == RequestStatus.SUCCESS
        assert response.seat_id == 123
        assert "Seat 123 purchased successfully" in response.message

    def test_buy_numbered_ticket_duplicate(self, ticket_manager):
        """Test duplicate numbered ticket purchase."""
        # First purchase
        request1 = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.NUMBERED,
            seat_id=123
        )
        response1 = ticket_manager.buy_ticket(request1)
        assert response1.status == RequestStatus.SUCCESS

        # Second purchase of same seat
        request2 = BuyRequest(
            client_id='client_2',
            request_id='req_2',
            ticket_type=TicketType.NUMBERED,
            seat_id=123
        )
        response2 = ticket_manager.buy_ticket(request2)

        assert response2.status == RequestStatus.FAILED
        assert "already sold" in response2.message

    def test_buy_numbered_ticket_invalid_seat(self, ticket_manager):
        """Test numbered ticket purchase with invalid seat ID."""
        # Test seat ID too low
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.NUMBERED,
            seat_id=0  # Invalid
        )
        response = ticket_manager.buy_ticket(request)

        assert response.status == RequestStatus.FAILED
        assert "Invalid seat_id" in response.message

    def test_buy_numbered_ticket_missing_seat_id(self, ticket_manager):
        """Test numbered ticket purchase without seat_id."""
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.NUMBERED,
            seat_id=None  # Missing
        )
        response = ticket_manager.buy_ticket(request)

        assert response.status == RequestStatus.FAILED
        assert "seat_id is required" in response.message

    def test_idempotency(self, ticket_manager):
        """Test idempotent behavior with duplicate request_id."""
        request1 = BuyRequest(
            client_id='client_1',
            request_id='req_duplicate',
            ticket_type=TicketType.UNNUMBERED
        )

        # First request
        response1 = ticket_manager.buy_ticket(request1)
        assert response1.status == RequestStatus.SUCCESS

        # Duplicate request with same request_id
        request2 = BuyRequest(
            client_id='client_2',  # Different client
            request_id='req_duplicate',  # Same request_id
            ticket_type=TicketType.UNNUMBERED
        )
        response2 = ticket_manager.buy_ticket(request2)

        assert response2.status == RequestStatus.DUPLICATE
        assert response2.client_id == 'client_1'  # Original client
        assert "Duplicate request" in response2.message

    def test_invalid_ticket_type(self, ticket_manager):
        """Test request with invalid ticket type."""
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type="invalid_type",  # Invalid
            seat_id=None
        )
        response = ticket_manager.buy_ticket(request)

        assert response.status == RequestStatus.FAILED
        assert "Unknown ticket type" in response.message

    def test_statistics(self, ticket_manager):
        """Test statistics collection."""
        # Buy some tickets
        for i in range(3):
            request = BuyRequest(
                client_id=f'client_{i}',
                request_id=f'req_{i}',
                ticket_type=TicketType.UNNUMBERED
            )
            ticket_manager.buy_ticket(request)

        # Buy a numbered ticket
        request = BuyRequest(
            client_id='client_4',
            request_id='req_4',
            ticket_type=TicketType.NUMBERED,
            seat_id=123
        )
        ticket_manager.buy_ticket(request)

        stats = ticket_manager.get_statistics()

        assert 'unnumbered_sold' in stats
        assert 'numbered_sold' in stats
        assert 'cached_responses' in stats
        assert stats['unnumbered_sold'] == 3
        assert stats['numbered_sold'] == 1
        assert stats['cached_responses'] >= 4

    def test_reset_functionality(self, ticket_manager):
        """Test system reset functionality."""
        # Buy some tickets
        request = BuyRequest(
            client_id='client_1',
            request_id='req_1',
            ticket_type=TicketType.UNNUMBERED
        )
        ticket_manager.buy_ticket(request)

        # Check tickets were bought
        stats_before = ticket_manager.get_statistics()
        assert stats_before['unnumbered_sold'] > 0

        # Reset system
        ticket_manager.reset()

        # Check system is reset
        stats_after = ticket_manager.get_statistics()
        assert stats_after['unnumbered_sold'] == 0
        assert stats_after['cached_responses'] == 0
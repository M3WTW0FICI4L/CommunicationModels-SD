"""
Core ticket management logic and consistency enforcement.
"""

import time
from typing import Dict, Any
from .storage import StorageBackend
from ..common.models import BuyRequest, BuyResponse, RequestStatus, TicketType
from ..common.logger import setup_logger


logger = setup_logger(__name__)


class TicketManager:
    """Manages ticket acquisition with consistency guarantees.

    Idempotency: every request_id is stored after first processing so that
    retried/duplicate requests return the original response without re-running
    the purchase logic.
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        # Maps request_id -> BuyResponse for idempotency
        self.processed_requests: Dict[str, BuyResponse] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def buy_ticket(self, request: BuyRequest) -> BuyResponse:
        """Process a ticket purchase request.

        Handles idempotency: if request_id was already processed, return
        the cached response immediately.
        """
        # Idempotency check
        if request.request_id in self.processed_requests:
            cached = self.processed_requests[request.request_id]
            logger.debug(f"Duplicate request {request.request_id}, returning cached response")
            return BuyResponse(
                request_id=cached.request_id,
                client_id=cached.client_id,
                status=RequestStatus.DUPLICATE,
                seat_id=cached.seat_id,
                message="Duplicate request – previously processed",
                timestamp=cached.timestamp,
            )

        # Route to correct handler
        if request.ticket_type == TicketType.UNNUMBERED:
            response = self.buy_unnumbered(request)
        elif request.ticket_type == TicketType.NUMBERED:
            if request.seat_id is None:
                response = BuyResponse(
                    request_id=request.request_id,
                    client_id=request.client_id,
                    status=RequestStatus.FAILED,
                    message="seat_id is required for numbered tickets",
                    timestamp=time.time(),
                )
            else:
                response = self.buy_numbered(request)
        else:
            response = BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.FAILED,
                message=f"Unknown ticket type: {request.ticket_type}",
                timestamp=time.time(),
            )

        # Cache for idempotency (only successful or failed, not errors we want
        # to allow retrying – here we cache everything)
        self.processed_requests[request.request_id] = response
        return response

    def buy_unnumbered(self, request: BuyRequest) -> BuyResponse:
        """Handle unnumbered ticket purchase using atomic counter increment."""
        sold = self.storage.increment_unnumbered()
        if sold:
            logger.info(f"Unnumbered ticket sold – request={request.request_id}")
            return BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.SUCCESS,
                message="Ticket purchased successfully",
                timestamp=time.time(),
            )
        else:
            logger.info(f"Unnumbered ticket SOLD OUT – request={request.request_id}")
            return BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.FAILED,
                message="Sold out – no tickets remaining",
                timestamp=time.time(),
            )

    def buy_numbered(self, request: BuyRequest) -> BuyResponse:
        """Handle numbered ticket purchase using atomic set-if-not-exists."""
        seat_id = request.seat_id
        # Validate seat range
        if seat_id < 1 or seat_id > 20_000:
            return BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.FAILED,
                message=f"Invalid seat_id {seat_id}: must be 1–20000",
                timestamp=time.time(),
            )

        claimed = self.storage.set_numbered_seat(seat_id)
        if claimed:
            logger.info(f"Seat {seat_id} sold – request={request.request_id}")
            return BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.SUCCESS,
                seat_id=seat_id,
                message=f"Seat {seat_id} purchased successfully",
                timestamp=time.time(),
            )
        else:
            logger.info(f"Seat {seat_id} already sold – request={request.request_id}")
            return BuyResponse(
                request_id=request.request_id,
                client_id=request.client_id,
                status=RequestStatus.FAILED,
                seat_id=seat_id,
                message=f"Seat {seat_id} is already sold",
                timestamp=time.time(),
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Return current system statistics from the storage backend."""
        stats = self.storage.get_stats()
        stats["cached_responses"] = len(self.processed_requests)
        return stats

    def reset(self) -> None:
        """Reset ticket state (for testing)."""
        self.storage.reset()
        self.processed_requests.clear()

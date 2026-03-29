"""
Data models and structures for the ticket acquisition system.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TicketType(Enum):
    """Type of ticket being purchased."""
    UNNUMBERED = "unnumbered"  # Standing area - count-based
    NUMBERED = "numbered"      # Seat-based - identity-based


class RequestStatus(Enum):
    """Status of a ticket purchase request."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass
class BuyRequest:
    """Represents a ticket purchase request."""
    client_id: str
    request_id: str
    ticket_type: TicketType
    seat_id: Optional[int] = None  # Only for NUMBERED tickets


@dataclass
class BuyResponse:
    """Represents a ticket purchase response."""
    request_id: str
    client_id: str
    status: RequestStatus
    seat_id: Optional[int] = None  # If successful and NUMBERED
    message: str = ""
    timestamp: float = 0.0

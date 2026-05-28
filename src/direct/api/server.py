"""
Direct communication API server using FastAPI.
Single entry point for all client requests (enforced requirement).
"""

import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from ...backend.storage import RedisBackend
from ...backend.ticket_manager import TicketManager
from ...common.models import BuyRequest, TicketType, RequestStatus
from ...common.config import Config
from ...common.logger import setup_logger


logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    storage = RedisBackend(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
    )
    ticket_manager = TicketManager(storage)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        storage.connect()
        logger.info("Direct API server started – Redis connected")
        yield
        storage.disconnect()
        logger.info("Direct API server stopped")

    app = FastAPI(
        title="Ticket Acquisition System – Direct API",
        description="REST endpoint for synchronous ticket purchases",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.post("/buy")
    async def buy_ticket(
        client_id: str = Query(..., description="Client identifier"),
        request_id: str = Query(..., description="Unique request ID (idempotency key)"),
        ticket_type: str = Query(..., description='"unnumbered" or "numbered"'),
        seat_id: Optional[int] = Query(
            None, description="Seat number (numbered tickets only)"
        ),
    ):
        """Purchase a ticket (unnumbered or numbered)."""
        # Validate ticket_type
        try:
            t_type = TicketType(ticket_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid ticket_type '{ticket_type}'. "
                    "Use 'unnumbered' or 'numbered'."
                ),
            )

        if t_type == TicketType.NUMBERED and seat_id is None:
            raise HTTPException(
                status_code=400,
                detail="seat_id is required for numbered tickets",
            )

        request = BuyRequest(
            client_id=client_id,
            request_id=request_id,
            ticket_type=t_type,
            seat_id=seat_id,
        )

        response = ticket_manager.buy_ticket(request)

        status_code = (
            200
            if response.status in (RequestStatus.SUCCESS, RequestStatus.DUPLICATE)
            else 409
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "request_id": response.request_id,
                "client_id": response.client_id,
                "status": response.status.value,
                "seat_id": response.seat_id,
                "message": response.message,
                "timestamp": response.timestamp,
            },
        )

    @app.get("/stats")
    async def get_stats():
        """Return current ticket sale statistics."""
        return ticket_manager.get_statistics()

    @app.get("/health")
    async def health_check():
        """Liveness probe."""
        return {"status": "ok", "service": "direct-api", "timestamp": time.time()}

    @app.post("/reset")
    async def reset_system():
        """Reset ticket state. Intended for testing only."""
        ticket_manager.reset()
        return {"status": "reset", "message": "All ticket state cleared"}

    return app


# ---------------------------------------------------------------------------
# DirectAPIServer wrapper (kept for backwards-compatibility with tests)
# ---------------------------------------------------------------------------

class DirectAPIServer:
    """Wrapper around the FastAPI app for programmatic control."""

    def __init__(self):
        self.app = create_app()

    def run(self, host: str = Config.API_HOST, port: int = Config.API_PORT):
        uvicorn.run(self.app, host=host, port=port, log_level="info")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Direct ticket API server")
    parser.add_argument("--host", default=Config.API_HOST)
    parser.add_argument("--port", type=int, default=Config.API_PORT)
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

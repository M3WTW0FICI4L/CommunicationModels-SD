"""
Direct communication API server using FastAPI.
Single entry point for all client requests (enforced requirement).
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional

from ...backend.storage import RedisBackend
from ...backend.ticket_manager import TicketManager
from ...common.models import BuyRequest, BuyResponse, TicketType, RequestStatus
from ...common.config import Config
from ...common.logger import setup_logger


logger = setup_logger(__name__)


class DirectAPIServer:
    """FastAPI server for direct communication architecture."""
    
    def __init__(self):
        """Initialize API server."""
        self.app = FastAPI(title="Ticket Acquisition System - Direct API")
        self.storage = RedisBackend(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        self.ticket_manager = TicketManager(self.storage)
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Set up API routes."""
        
        @self.app.on_event("startup")
        async def startup_event():
            """Initialize storage on startup."""
            self.storage.connect()
            logger.info("API server started")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Clean up on shutdown."""
            self.storage.disconnect()
            logger.info("API server stopped")
        
        @self.app.post("/buy")
        async def buy_ticket(
            client_id: str,
            request_id: str,
            ticket_type: str,
            seat_id: Optional[int] = None
        ):
            """
            Purchase a ticket.
            
            Args:
                client_id: Client identifier
                request_id: Unique request identifier (for idempotency)
                ticket_type: "unnumbered" or "numbered"
                seat_id: Seat number (required for numbered tickets)
            
            Returns:
                Purchase response
            """
            # TODO: Implement request handling
            # 1. Validate inputs
            # 2. Create BuyRequest
            # 3. Call ticket_manager.buy_ticket()
            # 4. Return BuyResponse as JSON
            pass
        
        @self.app.get("/stats")
        async def get_stats():
            """Get current system statistics."""
            # TODO: Implement stats endpoint
            # Return statistics from ticket_manager
            pass
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "ok", "service": "direct-api"}
        
        @self.app.post("/reset")
        async def reset_system():
            """Reset system state (for testing)."""
            # TODO: Reset ticket manager and storage
            pass
    
    def run(self, host: str = Config.API_HOST, port: int = Config.API_PORT):
        """
        Run the API server.
        
        Args:
            host: Server host
            port: Server port
        """
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            workers=1,  # Single worker for consistency
            log_level="info"
        )


if __name__ == "__main__":
    server = DirectAPIServer()
    server.run()

"""
Direct communication client for benchmarking and testing.
"""

import requests
import time
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...common.models import TicketType
from ...common.config import Config
from ...common.logger import setup_logger


logger = setup_logger(__name__)


class DirectClient:
    """Client for direct communication with API server."""
    
    def __init__(self, base_url: str = f"http://{Config.API_HOST}:{Config.API_PORT}"):
        """
        Initialize client.
        
        Args:
            base_url: Base URL of the API server (single entry point)
        """
        self.base_url = base_url
        self.session = requests.Session()
    
    def buy_unnumbered(self, client_id: str, request_id: str) -> Dict[str, Any]:
        """
        Purchase an unnumbered ticket.
        
        Args:
            client_id: Client identifier
            request_id: Unique request identifier
        
        Returns:
            Response dictionary
        """
        # TODO: Implement unnumbered ticket purchase request
        # POST /buy?client_id=...&request_id=...&ticket_type=unnumbered
        pass
    
    def buy_numbered(self, client_id: str, request_id: str, seat_id: int) -> Dict[str, Any]:
        """
        Purchase a numbered ticket (specific seat).
        
        Args:
            client_id: Client identifier
            request_id: Unique request identifier
            seat_id: Seat number
        
        Returns:
            Response dictionary
        """
        # TODO: Implement numbered ticket purchase request
        # POST /buy?client_id=...&request_id=...&ticket_type=numbered&seat_id=...
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get server statistics.
        
        Returns:
            Statistics dictionary
        """
        # TODO: Implement stats request
        # GET /stats
        pass
    
    def health_check(self) -> bool:
        """Check server health."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def reset(self) -> None:
        """Reset server state (for testing)."""
        # TODO: Implement reset request
        # POST /reset
        pass
    
    def parallel_buy(self, requests_list: List[tuple]) -> List[Dict[str, Any]]:
        """
        Send multiple requests in parallel.
        
        Args:
            requests_list: List of (client_id, request_id, ticket_type, seat_id) tuples
        
        Returns:
            List of responses
        """
        # TODO: Implement parallel request execution using ThreadPoolExecutor
        pass
    
    def close(self) -> None:
        """Close the client session."""
        self.session.close()


class LoadBalancedClient(DirectClient):
    """
    Client that supports load balancing across multiple API instances.
    Can use round-robin or other strategies.
    """
    
    def __init__(self, server_urls: Optional[List[str]] = None):
        """
        Initialize load-balanced client.
        
        Args:
            server_urls: List of server URLs for load balancing
        """
        self.server_urls = server_urls or [f"http://{Config.API_HOST}:{Config.API_PORT}"]
        self.current_server_idx = 0
    
    def _get_next_server(self) -> str:
        """Get next server URL in round-robin fashion."""
        # TODO: Implement round-robin load balancing
        pass

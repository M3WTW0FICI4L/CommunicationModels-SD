"""
Direct communication client for benchmarking and testing.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

import requests

from ...common.models import TicketType
from ...common.config import Config
from ...common.logger import setup_logger


logger = setup_logger(__name__)


class DirectClient:
    """HTTP client for the direct-communication REST API."""

    def __init__(self, base_url: str = f"http://{Config.API_HOST}:{Config.API_PORT}"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        # Re-use the same adapter pool for connection keep-alive
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=200,
            max_retries=0,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Core requests
    # ------------------------------------------------------------------

    def buy_unnumbered(
        self,
        client_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Purchase an unnumbered ticket."""
        return self._buy(
            client_id=client_id,
            request_id=request_id,
            ticket_type="unnumbered",
        )

    def buy_numbered(
        self,
        client_id: str,
        request_id: str,
        seat_id: int,
    ) -> Dict[str, Any]:
        """Purchase a specific numbered seat."""
        return self._buy(
            client_id=client_id,
            request_id=request_id,
            ticket_type="numbered",
            seat_id=seat_id,
        )

    def _buy(self, **params) -> Dict[str, Any]:
        """Low-level POST /buy helper."""
        try:
            resp = self.session.post(
                f"{self.base_url}/buy",
                params=params,
                timeout=Config.REQUEST_TIMEOUT,
            )
            # Intentar deserialitzar JSON; si falla mostrar el text real
            try:
                return resp.json()
            except ValueError:
                body = resp.text[:300] if resp.text else "(buit)"
                logger.error(f"Resposta no-JSON HTTP {resp.status_code}: {body}")
                return {
                    "status": "error",
                    "message": f"HTTP {resp.status_code}: {body}",
                }
        except requests.RequestException as e:
            logger.error(f"Buy request failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve server statistics."""
        try:
            resp = self.session.get(
                f"{self.base_url}/stats",
                timeout=Config.REQUEST_TIMEOUT,
            )
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Stats request failed: {e}")
            return {}

    def health_check(self) -> bool:
        """Return True if the server is reachable and healthy."""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def reset(self) -> None:
        """Reset server ticket state (testing only)."""
        try:
            self.session.post(
                f"{self.base_url}/reset",
                timeout=Config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            logger.error(f"Reset failed: {e}")

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def parallel_buy(
        self,
        requests_list: List[tuple],
        max_workers: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Send requests concurrently.

        Args:
            requests_list: Iterable of tuples.  Each tuple is either:
                - (client_id, request_id)               → unnumbered
                - (client_id, request_id, seat_id)      → numbered
            max_workers: Thread-pool size.

        Returns:
            List of response dicts in the same order as the input.
        """
        results = [None] * len(requests_list)

        def _submit(idx: int, item: tuple):
            if len(item) == 2:
                client_id, request_id = item
                return idx, self.buy_unnumbered(client_id, request_id)
            else:
                client_id, request_id, seat_id = item
                return idx, self.buy_numbered(client_id, request_id, int(seat_id))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_submit, i, item): i
                       for i, item in enumerate(requests_list)}
            for future in as_completed(futures):
                try:
                    idx, resp = future.result()
                    results[idx] = resp
                except Exception as e:
                    results[futures[future]] = {"status": "error", "message": str(e)}

        return results

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()


class LoadBalancedClient(DirectClient):
    """
    Client-side round-robin load balancer across multiple API instances.

    Each call to _get_next_server() picks the next URL in a thread-safe
    way, so concurrent threads will spread load evenly.
    """

    def __init__(self, server_urls: Optional[List[str]] = None):
        # Don't call super().__init__() with a single base_url here;
        # we override _buy() to use the round-robin URL.
        self.server_urls = server_urls or [
            f"http://{Config.API_HOST}:{Config.API_PORT}"
        ]
        self._lock = threading.Lock()
        self._idx = 0
        # Build a shared session (connection pooling still works per-host)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=200,
            max_retries=0,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_next_server(self) -> str:
        """Return the next server URL in round-robin order (thread-safe)."""
        with self._lock:
            url = self.server_urls[self._idx % len(self.server_urls)]
            self._idx += 1
        return url

    def _buy(self, **params) -> Dict[str, Any]:
        """Override: pick a server for each request."""
        base_url = self._get_next_server()
        try:
            resp = self.session.post(
                f"{base_url}/buy",
                params=params,
                timeout=Config.REQUEST_TIMEOUT,
            )
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Buy request to {base_url} failed: {e}")
            return {"status": "error", "message": str(e)}

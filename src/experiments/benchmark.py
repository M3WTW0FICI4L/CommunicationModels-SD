"""
Benchmark execution and workload simulation.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from ..common.logger import setup_logger


logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Workload file parsers
# ---------------------------------------------------------------------------

class WorkloadLoader:
    """Loads and parses the provided benchmark workload files."""

    @staticmethod
    def load_unnumbered(file_path: str) -> List[Tuple[str, str]]:
        """
        Parse an unnumbered workload file.

        Format per line: BUY <client_id> <request_id>

        Returns a list of (client_id, request_id) tuples.
        """
        entries: List[Tuple[str, str]] = []
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 3 or parts[0] != "BUY":
                    continue
                entries.append((parts[1], parts[2]))
        return entries

    @staticmethod
    def load_numbered(file_path: str) -> List[Tuple[str, str, int]]:
        """
        Parse a numbered workload file.

        Format per line: BUY <client_id> <seat_id> <request_id>

        Returns a list of (client_id, request_id, seat_id) tuples.
        """
        entries: List[Tuple[str, str, int]] = []
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 4 or parts[0] != "BUY":
                    continue
                # order: client_id, request_id, seat_id  (matches benchmark format)
                entries.append((parts[1], parts[3], int(parts[2])))
        return entries


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """
    Generic benchmark runner that drives load against a ticket system.

    Subclasses plug in the correct send function.
    """

    def __init__(self, num_workers: int = 50):
        self.num_workers = num_workers
        self.results: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Override this in subclasses
    # ------------------------------------------------------------------

    def _send_request(self, item: tuple) -> Dict[str, Any]:
        """Send a single request.  Must be overridden by subclasses."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_benchmark(
        self,
        workload: List[tuple],
        concurrent_clients: int = 50,
    ) -> Dict[str, Any]:
        """
        Execute all workload items concurrently.

        Args:
            workload: Iterable of tuples passed to _send_request().
            concurrent_clients: Thread pool size.

        Returns:
            Results dictionary (same as get_results()).
        """
        self.results = []
        self.start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrent_clients) as pool:
            futures = {
                pool.submit(self._timed_send, item): item
                for item in workload
            }
            for future in as_completed(futures):
                try:
                    self.results.append(future.result())
                except Exception as e:
                    self.results.append({
                        "status": "error",
                        "message": str(e),
                        "response_time": 0.0,
                    })

        self.end_time = time.perf_counter()
        return self.get_results()

    def _timed_send(self, item: tuple) -> Dict[str, Any]:
        """Wrap _send_request() with response-time measurement."""
        t0 = time.perf_counter()
        result = self._send_request(item)
        elapsed = time.perf_counter() - t0
        result["response_time"] = elapsed
        return result

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def get_results(self) -> Dict[str, Any]:
        """Compute aggregate statistics from self.results."""
        if not self.results:
            return {}

        total_time = (self.end_time or 0) - (self.start_time or 0)
        total = len(self.results)
        successful = sum(
            1 for r in self.results
            if r.get("status") in ("success", "duplicate")
        )
        failed = total - successful
        response_times = [r.get("response_time", 0.0) for r in self.results]
        throughput = total / total_time if total_time > 0 else 0.0

        sorted_rt = sorted(response_times)
        p95 = sorted_rt[int(len(sorted_rt) * 0.95)] if sorted_rt else 0
        p99 = sorted_rt[int(len(sorted_rt) * 0.99)] if sorted_rt else 0
        mean_rt = sum(response_times) / len(response_times) if response_times else 0

        return {
            "total_time_s": round(total_time, 3),
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "throughput_rps": round(throughput, 2),
            "mean_response_time_s": round(mean_rt, 4),
            "p95_response_time_s": round(p95, 4),
            "p99_response_time_s": round(p99, 4),
            "min_response_time_s": round(min(response_times), 4) if response_times else 0,
            "max_response_time_s": round(max(response_times), 4) if response_times else 0,
        }

    def save_results(self, path: str) -> None:
        """Write results to a JSON file."""
        with open(path, "w") as fh:
            json.dump(
                {
                    "summary": self.get_results(),
                    "raw": self.results,
                },
                fh,
                indent=2,
            )
        logger.info(f"Results saved to {path}")

    # ------------------------------------------------------------------
    # Ticket-model-specific validation helpers
    # ------------------------------------------------------------------

    def get_stats_unnumbered(self) -> Dict[str, Any]:
        """Count how many successful vs. failed unnumbered purchases."""
        ok = sum(1 for r in self.results if r.get("status") == "success")
        fail = sum(1 for r in self.results if r.get("status") == "failed")
        return {"sold": ok, "rejected": fail, "oversold": max(0, ok - 20_000)}

    def get_stats_numbered(self) -> Dict[str, Any]:
        """Check for duplicate seat sales in the results."""
        sold_seats = [
            r.get("seat_id")
            for r in self.results
            if r.get("status") == "success" and r.get("seat_id") is not None
        ]
        unique = len(set(sold_seats))
        duplicates = len(sold_seats) - unique
        return {
            "sold": len(sold_seats),
            "unique_seats": unique,
            "duplicate_sales": duplicates,
        }


# ---------------------------------------------------------------------------
# Direct architecture benchmark
# ---------------------------------------------------------------------------

class DirectBenchmark(BenchmarkRunner):
    """Drives load against the REST API (direct architecture)."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        num_workers: int = 50,
    ):
        super().__init__(num_workers=num_workers)
        # Import here to avoid circular deps at module load time
        from ..direct.client.client import DirectClient
        self._client = DirectClient(base_url=api_url)

    def _send_request(self, item: tuple) -> Dict[str, Any]:
        if len(item) == 2:
            client_id, request_id = item
            resp = self._client.buy_unnumbered(client_id, request_id)
        else:
            client_id, request_id, seat_id = item
            resp = self._client.buy_numbered(client_id, request_id, int(seat_id))
        return resp

    def reset(self) -> None:
        self._client.reset()

    def close(self) -> None:
        self._client.close()


class DirectLoadBalancedBenchmark(BenchmarkRunner):
    """Drives load across multiple API instances (client-side round-robin)."""

    def __init__(
        self,
        server_urls: List[str],
        num_workers: int = 50,
    ):
        super().__init__(num_workers=num_workers)
        from ..direct.client.client import LoadBalancedClient
        self._client = LoadBalancedClient(server_urls=server_urls)

    def _send_request(self, item: tuple) -> Dict[str, Any]:
        if len(item) == 2:
            client_id, request_id = item
            resp = self._client.buy_unnumbered(client_id, request_id)
        else:
            client_id, request_id, seat_id = item
            resp = self._client.buy_numbered(client_id, request_id, int(seat_id))
        return resp

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Indirect architecture benchmark (RabbitMQ)
# ---------------------------------------------------------------------------

class IndirectBenchmark(BenchmarkRunner):
    """
    Indirect benchmark: sends all messages to RabbitMQ, then polls
    the response queue until all results are collected (or timeout).
    """

    def __init__(
        self,
        queue_url: Optional[str] = None,
        num_workers: int = 50,
    ):
        super().__init__(num_workers=num_workers)
        from ..indirect.producer.producer import BulkProducer
        from ..indirect.queue.queue_config import QueueConfig, QueueManager
        self._QueueConfig = QueueConfig
        self._QueueManager = QueueManager
        self._producer = BulkProducer(queue_url=queue_url)
        self._queue_url = queue_url

    def run_benchmark(
        self,
        workload: List[tuple],
        concurrent_clients: int = 50,
        wait_timeout: int = 300,
    ) -> Dict[str, Any]:  # type: ignore[override]
        """
        1. Publish all messages to RabbitMQ.
        2. Wait for all responses to land in the response queue.
        3. Return aggregated results.
        """
        self.results = []
        self._producer.connect()
        self.start_time = time.perf_counter()

        # Use thread pool to publish in parallel for speed
        def _send(item):
            if len(item) == 2:
                client_id, request_id = item
                self._producer.send_unnumbered_request(client_id, request_id)
            else:
                client_id, request_id, seat_id = item
                self._producer.send_numbered_request(client_id, request_id, int(seat_id))

        with ThreadPoolExecutor(max_workers=concurrent_clients) as pool:
            list(pool.map(_send, workload))

        self._producer.flush()
        publish_time = time.perf_counter() - self.start_time
        logger.info(
            f"IndirectBenchmark: published {len(workload)} messages "
            f"in {publish_time:.2f}s"
        )

        self.results = self.wait_for_responses(
            expected=len(workload), timeout=wait_timeout
        )
        self.end_time = time.perf_counter()
        self._producer.disconnect()
        return self.get_results()

    def wait_for_responses(
        self, expected: int, timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Drain the response queue until *expected* messages are collected
        or *timeout* seconds elapse.
        """
        import pika

        responses: List[Dict[str, Any]] = []
        mgr = self._QueueManager()
        mgr.connect(
            self._producer.queue_url
            if hasattr(self._producer, "queue_url")
            else self._queue_url
        )
        mgr.declare_queue(self._QueueConfig.RESPONSE_QUEUE, durable=True)

        deadline = time.time() + timeout
        while len(responses) < expected and time.time() < deadline:
            method, props, body = mgr.channel.basic_get(
                queue=self._QueueConfig.RESPONSE_QUEUE, auto_ack=True
            )
            if method:
                try:
                    data = json.loads(body.decode())
                    responses.append(data)
                except Exception:
                    pass
            else:
                time.sleep(0.05)

        mgr.disconnect()
        logger.info(
            f"IndirectBenchmark: collected {len(responses)}/{expected} responses"
        )
        return responses

    def _send_request(self, item: tuple) -> Dict[str, Any]:
        # Not used directly for indirect (messages are fire-and-forget)
        return {}

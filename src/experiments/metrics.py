"""
Metrics collection and analysis utilities.
"""

import json
import statistics
from typing import Any, Dict, List


class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self):
        self.response_times: List[float] = []
        self.success_count = 0
        self.failure_count = 0
        self.duplicate_count = 0
        self.error_details: List[str] = []

    def add_response(self, success: bool, response_time: float,
                     error: str = "") -> None:
        """Record a single response."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if error:
                self.error_details.append(error)

    def get_statistics(self) -> Dict[str, Any]:
        """Return computed aggregate statistics."""
        if not self.response_times:
            return {}

        total = self.success_count + self.failure_count
        return {
            "total_requests": total,
            "successful": self.success_count,
            "failed": self.failure_count,
            "success_rate": self.success_count / total if total > 0 else 0,
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "mean_response_time": statistics.mean(self.response_times),
            "median_response_time": statistics.median(self.response_times),
            "stddev_response_time": (
                statistics.stdev(self.response_times)
                if len(self.response_times) > 1
                else 0
            ),
            "p95_response_time": self._percentile(self.response_times, 0.95),
            "p99_response_time": self._percentile(self.response_times, 0.99),
        }

    @staticmethod
    def _percentile(data: List[float], p: float) -> float:
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p)
        return sorted_data[min(idx, len(sorted_data) - 1)]

    def export_json(self, file_path: str) -> None:
        """Write statistics to a JSON file."""
        with open(file_path, "w") as fh:
            json.dump(self.get_statistics(), fh, indent=2)


class CorrectnessValidator:
    """Validates correctness of ticket sale results."""

    @staticmethod
    def validate_unnumbered_sales(
        successful_count: int, max_tickets: int = 20_000
    ) -> Dict[str, Any]:
        """Check that we haven't oversold unnumbered tickets."""
        return {
            "valid": successful_count <= max_tickets,
            "expected_max": max_tickets,
            "actual": successful_count,
            "oversold": max(0, successful_count - max_tickets),
        }

    @staticmethod
    def validate_numbered_sales(
        sold_seats: List[int], max_seats: int = 20_000
    ) -> Dict[str, Any]:
        """Check that no numbered seat was sold more than once."""
        unique_seats = set(sold_seats)
        duplicates = len(sold_seats) - len(unique_seats)
        invalid_seats = [s for s in sold_seats if s < 1 or s > max_seats]
        duplicate_list = [
            s for s in unique_seats
            if sold_seats.count(s) > 1
        ]
        return {
            "valid": duplicates == 0 and len(invalid_seats) == 0,
            "total_sales": len(sold_seats),
            "unique_seats": len(unique_seats),
            "duplicate_count": duplicates,
            "invalid_seat_count": len(invalid_seats),
            "duplicate_seats": duplicate_list[:50],  # cap for readability
        }

    @staticmethod
    def compare_architectures(
        direct_results: Dict[str, Any],
        indirect_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Side-by-side comparison of direct vs indirect benchmark results.
        Both dicts must come from BenchmarkRunner.get_results().
        """
        def _safe_ratio(a, b):
            return round(a / b, 3) if b else None

        d_tps = direct_results.get("throughput_rps", 0)
        i_tps = indirect_results.get("throughput_rps", 0)

        return {
            "direct": {
                "throughput_rps": d_tps,
                "total_time_s": direct_results.get("total_time_s"),
                "mean_latency_s": direct_results.get("mean_response_time_s"),
                "p99_latency_s": direct_results.get("p99_response_time_s"),
                "successful": direct_results.get("successful_requests"),
            },
            "indirect": {
                "throughput_rps": i_tps,
                "total_time_s": indirect_results.get("total_time_s"),
                "mean_latency_s": indirect_results.get("mean_response_time_s"),
                "p99_latency_s": indirect_results.get("p99_response_time_s"),
                "successful": indirect_results.get("successful_requests"),
            },
            "ratio_throughput_direct_over_indirect": _safe_ratio(d_tps, i_tps),
            "winner_throughput": (
                "direct" if d_tps >= i_tps else "indirect"
            ),
        }

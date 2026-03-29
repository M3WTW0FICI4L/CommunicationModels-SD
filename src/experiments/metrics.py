"""
Metrics collection and analysis utilities.
"""

from typing import List, Dict, Any
import statistics
import json


class MetricsCollector:
    """Collects and aggregates performance metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.response_times: List[float] = []
        self.success_count = 0
        self.failure_count = 0
        self.duplicate_count = 0
        self.error_details: List[str] = []
    
    def add_response(self, success: bool, response_time: float, error: str = "") -> None:
        """
        Record a response.
        
        Args:
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if failed
        """
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if error:
                self.error_details.append(error)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get computed statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.response_times:
            return {}
        
        return {
            "total_requests": self.success_count + self.failure_count,
            "successful": self.success_count,
            "failed": self.failure_count,
            "success_rate": self.success_count / (self.success_count + self.failure_count) if (self.success_count + self.failure_count) > 0 else 0,
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "mean_response_time": statistics.mean(self.response_times),
            "median_response_time": statistics.median(self.response_times),
            "stddev_response_time": statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0,
            "p95_response_time": self._percentile(self.response_times, 0.95),
            "p99_response_time": self._percentile(self.response_times, 0.99),
        }
    
    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * percentile)
        return sorted_data[min(idx, len(sorted_data) - 1)]
    
    def export_json(self, file_path: str) -> None:
        """
        Export metrics to JSON file.
        
        Args:
            file_path: Path to output file
        """
        # TODO: Implement JSON export
        pass


class CorrectnessValidator:
    """Validates correctness of results."""
    
    @staticmethod
    def validate_unnumbered_sales(successful_count: int, max_tickets: int = 20000) -> Dict[str, Any]:
        """
        Validate unnumbered ticket sales.
        
        Args:
            successful_count: Number of successful sales
            max_tickets: Maximum allowed tickets
        
        Returns:
            Validation result dictionary
        """
        return {
            "valid": successful_count <= max_tickets,
            "expected": max_tickets,
            "actual": successful_count,
            "error": successful_count > max_tickets
        }
    
    @staticmethod
    def validate_numbered_sales(sold_seats: List[int], max_seats: int = 20000) -> Dict[str, Any]:
        """
        Validate numbered ticket sales for duplicates.
        
        Args:
            sold_seats: List of sold seat IDs
            max_seats: Maximum seat ID
        
        Returns:
            Validation result dictionary
        """
        unique_seats = set(sold_seats)
        duplicates = len(sold_seats) - len(unique_seats)
        invalid_seats = [s for s in sold_seats if s < 1 or s > max_seats]
        
        return {
            "valid": duplicates == 0 and len(invalid_seats) == 0,
            "total_sales": len(sold_seats),
            "unique_seats": len(unique_seats),
            "duplicate_count": duplicates,
            "invalid_seat_count": len(invalid_seats),
            "duplicates": list(set([s for s in sold_seats if sold_seats.count(s) > 1]))
        }
    
    @staticmethod
    def compare_architectures(direct_results: Dict[str, Any], indirect_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare results between direct and indirect architectures.
        
        Args:
            direct_results: Direct architecture results
            indirect_results: Indirect architecture results
        
        Returns:
            Comparison dictionary
        """
        # TODO: Implement architecture comparison
        pass

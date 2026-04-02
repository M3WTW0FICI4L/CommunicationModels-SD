"""
Unit tests for metrics collection and analysis.
"""

import unittest
import json
import tempfile
import os
from src.experiments.metrics import MetricsCollector, CorrectnessValidator


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.collector = MetricsCollector()
    
    def test_initialization(self):
        """Test MetricsCollector initialization."""
        self.assertEqual(len(self.collector.response_times), 0)
        self.assertEqual(self.collector.success_count, 0)
        self.assertEqual(self.collector.failure_count, 0)
        self.assertEqual(self.collector.duplicate_count, 0)
        self.assertEqual(len(self.collector.error_details), 0)
    
    def test_add_successful_response(self):
        """Test adding a successful response."""
        self.collector.add_response(success=True, response_time=0.5)
        
        self.assertEqual(self.collector.success_count, 1)
        self.assertEqual(self.collector.failure_count, 0)
        self.assertEqual(len(self.collector.response_times), 1)
        self.assertEqual(self.collector.response_times[0], 0.5)
    
    def test_add_failed_response(self):
        """Test adding a failed response."""
        self.collector.add_response(success=False, response_time=1.0, error="Timeout")
        
        self.assertEqual(self.collector.success_count, 0)
        self.assertEqual(self.collector.failure_count, 1)
        self.assertEqual(len(self.collector.response_times), 1)
        self.assertIn("Timeout", self.collector.error_details)
    
    def test_add_multiple_responses(self):
        """Test adding multiple responses."""
        response_times = [0.1, 0.2, 0.15, 0.3, 0.25]
        
        for i, time_val in enumerate(response_times):
            success = i % 2 == 0  # Alternate success/failure
            self.collector.add_response(
                success=success,
                response_time=time_val,
                error="Error" if not success else ""
            )
        
        self.assertEqual(self.collector.success_count, 3)
        self.assertEqual(self.collector.failure_count, 2)
        self.assertEqual(len(self.collector.response_times), 5)
        self.assertEqual(self.collector.response_times, response_times)
    
    def test_get_statistics_empty(self):
        """Test getting statistics from empty collector."""
        stats = self.collector.get_statistics()
        self.assertEqual(stats, {})
    
    def test_get_statistics_single_response(self):
        """Test getting statistics with single response."""
        self.collector.add_response(success=True, response_time=0.5)
        stats = self.collector.get_statistics()
        
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertEqual(stats["min_response_time"], 0.5)
        self.assertEqual(stats["max_response_time"], 0.5)
        self.assertEqual(stats["mean_response_time"], 0.5)
        self.assertEqual(stats["median_response_time"], 0.5)
        self.assertEqual(stats["stddev_response_time"], 0)
    
    def test_get_statistics_multiple_responses(self):
        """Test getting statistics with multiple responses."""
        response_times = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        for time_val in response_times:
            self.collector.add_response(success=True, response_time=time_val)
        
        stats = self.collector.get_statistics()
        
        self.assertEqual(stats["total_requests"], 5)
        self.assertEqual(stats["successful"], 5)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertEqual(stats["min_response_time"], 0.1)
        self.assertEqual(stats["max_response_time"], 0.5)
        self.assertAlmostEqual(stats["mean_response_time"], 0.3, places=5)
        self.assertEqual(stats["median_response_time"], 0.3)
    
    def test_get_statistics_with_failures(self):
        """Test statistics calculation with mixed success/failure."""
        # Add 7 successes and 3 failures
        for i in range(7):
            self.collector.add_response(success=True, response_time=0.1)
        for i in range(3):
            self.collector.add_response(success=False, response_time=0.5)
        
        stats = self.collector.get_statistics()
        
        self.assertEqual(stats["total_requests"], 10)
        self.assertEqual(stats["successful"], 7)
        self.assertEqual(stats["failed"], 3)
        self.assertAlmostEqual(stats["success_rate"], 0.7, places=5)
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        response_times = list(range(1, 101))  # 1-100
        for t in response_times:
            self.collector.add_response(success=True, response_time=float(t))
        
        stats = self.collector.get_statistics()
        
        # p95 should be around 95
        self.assertGreaterEqual(stats["p95_response_time"], 94)
        self.assertLessEqual(stats["p95_response_time"], 100)
        
        # p99 should be around 99
        self.assertGreaterEqual(stats["p99_response_time"], 98)
        self.assertLessEqual(stats["p99_response_time"], 100)


class TestCorrectnessValidator(unittest.TestCase):
    """Test CorrectnessValidator class."""
    
    def test_validate_unnumbered_sales_valid_within_limit(self):
        """Test validation when sales are within limit."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=10000,
            max_tickets=20000
        )
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected"], 20000)
        self.assertEqual(result["actual"], 10000)
        self.assertFalse(result["error"])
    
    def test_validate_unnumbered_sales_at_limit(self):
        """Test validation when sales reach limit."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=20000,
            max_tickets=20000
        )
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected"], 20000)
        self.assertEqual(result["actual"], 20000)
        self.assertFalse(result["error"])
    
    def test_validate_unnumbered_sales_exceeds_limit(self):
        """Test validation when sales exceed limit (invalid)."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=20001,
            max_tickets=20000
        )
        
        self.assertFalse(result["valid"])
        self.assertEqual(result["expected"], 20000)
        self.assertEqual(result["actual"], 20001)
        self.assertTrue(result["error"])
    
    def test_validate_unnumbered_sales_zero(self):
        """Test validation with zero sales."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=0,
            max_tickets=20000
        )
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["actual"], 0)
        self.assertFalse(result["error"])
    
    def test_validate_unnumbered_sales_custom_max(self):
        """Test validation with custom max tickets."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=100,
            max_tickets=50
        )
        
        self.assertFalse(result["valid"])
        self.assertEqual(result["expected"], 50)
        self.assertEqual(result["actual"], 100)
        self.assertTrue(result["error"])
    
    def test_validate_unnumbered_sales_boundary_one_below(self):
        """Test validation one below limit."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=19999,
            max_tickets=20000
        )
        
        self.assertTrue(result["valid"])
        self.assertFalse(result["error"])
    
    def test_validate_unnumbered_sales_boundary_one_above(self):
        """Test validation one above limit."""
        result = CorrectnessValidator.validate_unnumbered_sales(
            successful_count=20001,
            max_tickets=20000
        )
        
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"])


if __name__ == "__main__":
    unittest.main()

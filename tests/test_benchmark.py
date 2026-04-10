"""Unit tests for benchmark functionality."""

import json
import os
import tempfile
import unittest

from src.experiments.benchmark import BenchmarkRunner, WorkloadLoader


class EchoRunner(BenchmarkRunner):
    """Concrete runner for testing BenchmarkRunner behavior."""

    def _send_request(self, item):
        if item == "explode":
            raise RuntimeError("boom")
        if isinstance(item, dict):
            return item
        return {"status": "success"}


class TestWorkloadLoader(unittest.TestCase):
    """Test workload parser behavior."""

    def test_load_unnumbered_parses_valid_lines_only(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as fh:
            fh.write("# comment\n")
            fh.write("\n")
            fh.write("BAD line\n")
            fh.write("BUY c1 r1\n")
            fh.write("BUY c2 r2 extra-token\n")
            path = fh.name

        try:
            result = WorkloadLoader.load_unnumbered(path)
            self.assertEqual(result, [("c1", "r1"), ("c2", "r2")])
        finally:
            os.unlink(path)

    def test_load_numbered_parses_and_reorders_fields(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as fh:
            fh.write("# comment\n")
            fh.write("BUY c1 10 req-1\n")
            fh.write("BUY c2 20 req-2\n")
            fh.write("NOPE c3 30 req-3\n")
            path = fh.name

        try:
            result = WorkloadLoader.load_numbered(path)
            self.assertEqual(result, [("c1", "req-1", 10), ("c2", "req-2", 20)])
        finally:
            os.unlink(path)

    def test_load_unnumbered_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            WorkloadLoader.load_unnumbered("/definitely/missing/workload.txt")


class TestBenchmarkRunner(unittest.TestCase):
    """Test benchmark runner core behavior and stats."""

    def test_initialization_defaults(self):
        runner = EchoRunner()
        self.assertEqual(runner.num_workers, 1)
        self.assertEqual(runner.results, [])
        self.assertIsNone(runner.start_time)
        self.assertIsNone(runner.end_time)

    def test_timed_send_adds_response_time(self):
        runner = EchoRunner()
        result = runner._timed_send({"status": "success", "seat_id": 1})

        self.assertEqual(result["status"], "success")
        self.assertIn("response_time", result)
        self.assertGreaterEqual(result["response_time"], 0.0)

    def test_run_benchmark_collects_success_and_duplicate(self):
        runner = EchoRunner()
        workload = [
            {"status": "success", "seat_id": 1},
            {"status": "duplicate", "seat_id": 1},
            {"status": "failed"},
        ]

        summary = runner.run_benchmark(workload=workload, concurrent_clients=2)

        self.assertEqual(summary["total_requests"], 3)
        self.assertEqual(summary["successful_requests"], 2)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertGreaterEqual(summary["throughput_rps"], 0)
        self.assertIn("p95_response_time_s", summary)

    def test_run_benchmark_captures_exceptions_as_error_results(self):
        runner = EchoRunner()
        summary = runner.run_benchmark(workload=["explode"], concurrent_clients=1)

        self.assertEqual(summary["total_requests"], 1)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertEqual(runner.results[0]["status"], "error")
        self.assertIn("boom", runner.results[0]["message"])

    def test_get_results_empty_returns_empty_dict(self):
        runner = EchoRunner()
        self.assertEqual(runner.get_results(), {})

    def test_save_results_writes_summary_and_raw(self):
        runner = EchoRunner()
        runner.run_benchmark(workload=[{"status": "success"}], concurrent_clients=1)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as fh:
            path = fh.name

        try:
            runner.save_results(path)
            with open(path, "r") as fh2:
                payload = json.load(fh2)
            self.assertIn("summary", payload)
            self.assertIn("raw", payload)
            self.assertEqual(payload["summary"]["total_requests"], 1)
            self.assertEqual(len(payload["raw"]), 1)
        finally:
            os.unlink(path)

    def test_get_stats_unnumbered_computes_oversold(self):
        runner = EchoRunner()
        runner.results = [{"status": "success"}] * 20002 + [{"status": "failed"}]

        stats = runner.get_stats_unnumbered()

        self.assertEqual(stats["sold"], 20002)
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(stats["oversold"], 2)

    def test_get_stats_numbered_detects_duplicates(self):
        runner = EchoRunner()
        runner.results = [
            {"status": "success", "seat_id": 10},
            {"status": "success", "seat_id": 10},
            {"status": "success", "seat_id": 11},
            {"status": "failed", "seat_id": 12},
            {"status": "success", "seat_id": None},
        ]

        stats = runner.get_stats_numbered()

        self.assertEqual(stats["sold"], 3)
        self.assertEqual(stats["unique_seats"], 2)
        self.assertEqual(stats["duplicate_sales"], 1)


if __name__ == "__main__":
    unittest.main()

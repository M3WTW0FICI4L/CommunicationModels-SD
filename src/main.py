"""
Main entry point for the ticket acquisition system.
Supports running different configurations and experiments.
"""

import argparse
import sys
from typing import Optional

from src.common.logger import setup_logger
from src.common.config import Config


logger = setup_logger(__name__)


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="Scalable Concert Ticket Acquisition System"
    )
    
    parser.add_argument(
        "--mode",
        choices=["direct-api", "direct-client", "indirect-producer", "indirect-worker", "benchmark"],
        required=True,
        help="Execution mode"
    )
    
    parser.add_argument(
        "--host",
        default=Config.API_HOST,
        help="Server host (for API or worker)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=Config.API_PORT,
        help="Server port (for API)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=Config.WORKER_COUNT,
        help="Number of workers (for indirect mode)"
    )
    
    parser.add_argument(
        "--workload",
        type=str,
        help="Path to benchmark workload file"
    )
    
    parser.add_argument(
        "--ticket-type",
        choices=["unnumbered", "numbered"],
        default="unnumbered",
        help="Ticket type for benchmark"
    )
    
    parser.add_argument(
        "--concurrent-clients",
        type=int,
        default=1,
        help="Number of concurrent clients for benchmark"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == "direct-api":
            run_direct_api(args)
        elif args.mode == "direct-client":
            run_direct_client(args)
        elif args.mode == "indirect-producer":
            run_indirect_producer(args)
        elif args.mode == "indirect-worker":
            run_indirect_worker(args)
        elif args.mode == "benchmark":
            run_benchmark(args)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def run_direct_api(args) -> None:
    """Run direct API server."""
    logger.info("Starting Direct Communication API Server...")
    
    from src.direct.api.server import DirectAPIServer
    
    server = DirectAPIServer()
    server.run(host=args.host, port=args.port)


def run_direct_client(args) -> None:
    """Run direct client for benchmarking."""
    logger.info("Starting Direct Communication Client...")
    
    # TODO: Implement direct client execution
    pass


def run_indirect_producer(args) -> None:
    """Run indirect producer (client side)."""
    logger.info("Starting Indirect Communication Producer...")
    
    # TODO: Implement producer execution
    pass


def run_indirect_worker(args) -> None:
    """Run indirect worker (server side)."""
    logger.info(f"Starting Indirect Communication Worker(s)... ({args.workers} workers)")
    
    from src.indirect.worker.worker import WorkerPool
    
    # TODO: Implement worker pool execution
    pass


def run_benchmark(args) -> None:
    """Run benchmark experiment."""
    logger.info("Starting Benchmark Experiment...")
    
    if not args.workload:
        raise ValueError("Workload file is required for benchmark mode")
    
    # TODO: Implement benchmark execution
    pass


if __name__ == "__main__":
    main()

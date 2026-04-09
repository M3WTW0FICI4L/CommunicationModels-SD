"""
Main entry point for the ticket acquisition system.
Supports running different configurations and experiments.
"""

import argparse
import sys
import os

from src.common.logger import setup_logger
from src.common.config import Config


logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Scalable Concert Ticket Acquisition System"
    )
    parser.add_argument(
        "--mode",
        choices=[
            "direct-api",
            "indirect-worker",
            "indirect-producer",
            "benchmark-direct",
            "benchmark-indirect",
        ],
        required=True,
        help="Execution mode",
    )
    parser.add_argument("--host", default=Config.API_HOST)
    parser.add_argument("--port", type=int, default=Config.API_PORT)
    parser.add_argument("--workers", type=int, default=Config.WORKER_COUNT)
    parser.add_argument("--worker-id", type=str, default="worker-0")
    parser.add_argument("--workload", type=str, help="Path to benchmark workload file")
    parser.add_argument(
        "--ticket-type", choices=["unnumbered", "numbered"], default="unnumbered"
    )
    parser.add_argument("--concurrent-clients", type=int, default=50)
    parser.add_argument("--output", type=str, help="Output JSON path for results")
    parser.add_argument(
        "--api-url",
        type=str,
        default=f"http://{Config.API_HOST}:{Config.API_PORT}",
        help="API server URL (for benchmark-direct)",
    )

    args = parser.parse_args()

    try:
        if args.mode == "direct-api":
            run_direct_api(args)
        elif args.mode == "indirect-worker":
            run_indirect_worker(args)
        elif args.mode == "indirect-producer":
            run_indirect_producer(args)
        elif args.mode == "benchmark-direct":
            run_benchmark_direct(args)
        elif args.mode == "benchmark-indirect":
            run_benchmark_indirect(args)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------

def run_direct_api(args) -> None:
    """Launch the FastAPI REST server."""
    import uvicorn
    from src.direct.api.server import create_app

    logger.info(f"Starting Direct API on {args.host}:{args.port}")
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def run_indirect_worker(args) -> None:
    """Launch one or more RabbitMQ consumer workers."""
    if args.workers == 1:
        from src.indirect.worker.worker import IndirectWorker

        logger.info(f"Starting single worker {args.worker_id}")
        w = IndirectWorker(worker_id=args.worker_id)
        w.start()
    else:
        import time
        from src.indirect.worker.worker import WorkerPool

        logger.info(f"Starting worker pool with {args.workers} workers")
        pool = WorkerPool(initial_workers=args.workers)
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            pool.stop_all()


def run_indirect_producer(args) -> None:
    """Publish a benchmark workload file to RabbitMQ."""
    if not args.workload:
        raise ValueError("--workload is required for indirect-producer mode")

    from src.indirect.producer.producer import BulkProducer

    logger.info(f"Publishing workload: {args.workload}")
    producer = BulkProducer()
    producer.connect()
    count = producer.load_and_send_file(args.workload, ticket_type=args.ticket_type)
    producer.disconnect()
    logger.info(f"Published {count} messages")


def run_benchmark_direct(args) -> None:
    """Run direct-architecture benchmark."""
    if not args.workload:
        raise ValueError("--workload is required for benchmark modes")

    from src.experiments.benchmark import DirectBenchmark, WorkloadLoader

    logger.info(f"Direct benchmark: {args.workload} | clients={args.concurrent_clients}")

    bench = DirectBenchmark(api_url=args.api_url, num_workers=args.concurrent_clients)

    if args.ticket_type == "unnumbered":
        workload = WorkloadLoader.load_unnumbered(args.workload)
    else:
        workload = WorkloadLoader.load_numbered(args.workload)

    results = bench.run_benchmark(workload, concurrent_clients=args.concurrent_clients)

    _print_results(results)
    if args.output:
        bench.save_results(args.output)


def run_benchmark_indirect(args) -> None:
    """Run indirect-architecture benchmark (publish + wait for responses)."""
    if not args.workload:
        raise ValueError("--workload is required for benchmark modes")

    from src.experiments.benchmark import IndirectBenchmark, WorkloadLoader

    logger.info(f"Indirect benchmark: {args.workload} | clients={args.concurrent_clients}")

    bench = IndirectBenchmark(num_workers=args.concurrent_clients)

    if args.ticket_type == "unnumbered":
        workload = WorkloadLoader.load_unnumbered(args.workload)
    else:
        workload = WorkloadLoader.load_numbered(args.workload)

    results = bench.run_benchmark(
        workload,
        concurrent_clients=args.concurrent_clients,
    )

    _print_results(results)
    if args.output:
        bench.save_results(args.output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_results(results: dict) -> None:
    print("\n=== Benchmark Results ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("=========================\n")


if __name__ == "__main__":
    main()

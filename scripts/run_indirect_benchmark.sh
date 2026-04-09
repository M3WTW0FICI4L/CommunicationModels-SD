#!/usr/bin/env bash
# Run the indirect-architecture benchmark.
# Publishes workload to RabbitMQ and waits for responses.
# Usage:
#   ./scripts/run_indirect_benchmark.sh [unnumbered|numbered] [concurrent_clients]

set -euo pipefail

TICKET_TYPE="${1:-unnumbered}"
CONCURRENT="${2:-50}"
RESULTS_DIR="results/indirect"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTS_DIR"

if [ "$TICKET_TYPE" = "unnumbered" ]; then
    WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
else
    WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
fi

echo "=== Indirect Benchmark ==="
echo "  Ticket type : $TICKET_TYPE"
echo "  Concurrency : $CONCURRENT"
echo "  Workload    : $WORKLOAD"
echo ""

OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${CONCURRENT}_${TIMESTAMP}.json"

python -m src.main \
    --mode benchmark-indirect \
    --ticket-type "$TICKET_TYPE" \
    --workload "$WORKLOAD" \
    --concurrent-clients "$CONCURRENT" \
    --output "$OUTPUT"

echo "Results saved to: $OUTPUT"

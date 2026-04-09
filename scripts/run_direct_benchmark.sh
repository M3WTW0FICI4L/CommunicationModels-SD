#!/usr/bin/env bash
# Run the direct-architecture benchmark against a running API server.
# Usage:
#   ./scripts/run_direct_benchmark.sh [unnumbered|numbered] [concurrent_clients] [api_url]

set -euo pipefail

TICKET_TYPE="${1:-unnumbered}"
CONCURRENT="${2:-50}"
API_URL="${3:-http://localhost:80}"
RESULTS_DIR="results/direct"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTS_DIR"

if [ "$TICKET_TYPE" = "unnumbered" ]; then
    WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
else
    WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
fi

echo "=== Direct Benchmark ==="
echo "  Ticket type : $TICKET_TYPE"
echo "  Concurrency : $CONCURRENT"
echo "  API URL     : $API_URL"
echo "  Workload    : $WORKLOAD"
echo ""

OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${CONCURRENT}_${TIMESTAMP}.json"

python -m src.main \
    --mode benchmark-direct \
    --ticket-type "$TICKET_TYPE" \
    --workload "$WORKLOAD" \
    --concurrent-clients "$CONCURRENT" \
    --api-url "$API_URL" \
    --output "$OUTPUT"

echo "Results saved to: $OUTPUT"

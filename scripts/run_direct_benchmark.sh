#!/usr/bin/env bash
# Run the direct-architecture benchmark against a running API server.
# Usage:
#   ./scripts/run_direct_benchmark.sh [unnumbered|numbered] [concurrent_clients] [api_url]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo "Error: no Python interpreter found (.venv/bin/python, python3, python)."
    exit 1
fi

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

if ! [ -f "$WORKLOAD" ]; then
    echo "Error: workload file not found: $WORKLOAD"
    exit 1
fi

echo "=== Direct Benchmark ==="
echo "  Ticket type : $TICKET_TYPE"
echo "  Concurrency : $CONCURRENT"
echo "  API URL     : $API_URL"
echo "  Workload    : $WORKLOAD"
echo ""

OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${CONCURRENT}_${TIMESTAMP}.json"

if ! curl -fsS "${API_URL}/health" >/dev/null; then
    echo "Error: API not reachable at ${API_URL}. Start direct API first."
    echo "Hint A (docker, recommended): docker compose -f docker/docker-compose.direct.yml up -d --build"
    echo "Hint B (local API): python3 -m src.main --mode direct-api --host 0.0.0.0 --port 8000"
    echo "If using local API on 8000, run this script with: ./scripts/run_direct_benchmark.sh ${TICKET_TYPE} ${CONCURRENT} http://localhost:8000"
    exit 1
fi

"$PYTHON_BIN" -m src.main \
    --mode benchmark-direct \
    --ticket-type "$TICKET_TYPE" \
    --workload "$WORKLOAD" \
    --concurrent-clients "$CONCURRENT" \
    --api-url "$API_URL" \
    --output "$OUTPUT"

echo "Results saved to: $OUTPUT"

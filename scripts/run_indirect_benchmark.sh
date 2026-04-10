#!/usr/bin/env bash
# Run the indirect-architecture benchmark.
# Publishes workload to RabbitMQ and waits for responses.
# Usage:
#   ./scripts/run_indirect_benchmark.sh [unnumbered|numbered] [concurrent_clients]

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
RESULTS_DIR="results/indirect"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RABBITMQ_HOST="${RABBITMQ_HOST:-localhost}"
RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"

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

echo "=== Indirect Benchmark ==="
echo "  Ticket type : $TICKET_TYPE"
echo "  Concurrency : $CONCURRENT"
echo "  Workload    : $WORKLOAD"
echo ""

OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${CONCURRENT}_${TIMESTAMP}.json"

# Ensure RabbitMQ is reachable before launching benchmark
if ! timeout 2 bash -c "</dev/tcp/${RABBITMQ_HOST}/${RABBITMQ_PORT}" 2>/dev/null; then
    echo "Error: RabbitMQ not reachable at ${RABBITMQ_HOST}:${RABBITMQ_PORT}."
    echo "Hint: docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4"
    exit 1
fi

echo "Checking worker availability (best-effort)..."
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'worker'; then
    echo "Warning: no worker container name detected via docker ps."
    echo "Benchmark can publish messages, but without workers responses may timeout."
fi

"$PYTHON_BIN" -m src.main \
    --mode benchmark-indirect \
    --ticket-type "$TICKET_TYPE" \
    --workload "$WORKLOAD" \
    --concurrent-clients "$CONCURRENT" \
    --output "$OUTPUT"

echo "Results saved to: $OUTPUT"

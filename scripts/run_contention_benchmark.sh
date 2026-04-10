#!/usr/bin/env bash
# Run the high-contention numbered benchmark for either architecture.
# Usage:
#   ./scripts/run_contention_benchmark.sh [direct|indirect] [concurrent_clients] [api_url]

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

ARCHITECTURE="${1:-direct}"
CONCURRENT="${2:-50}"
API_URL="${3:-http://localhost:80}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WORKLOAD="benchmarks/benchmark_numbered_contention.txt"
RABBITMQ_HOST="${RABBITMQ_HOST:-localhost}"
RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"

if ! [ -f "$WORKLOAD" ]; then
    echo "Error: workload file not found: $WORKLOAD"
    echo "Hint: python3 scripts/generate_contention_benchmark.py --output $WORKLOAD"
    exit 1
fi

case "$ARCHITECTURE" in
    direct)
        RESULTS_DIR="results/direct/numbered/contention"
        OUTPUT="${RESULTS_DIR}/c${CONCURRENT}_${TIMESTAMP}.json"
        mkdir -p "$RESULTS_DIR"

        if ! curl -fsS "${API_URL}/health" >/dev/null; then
            echo "Error: API not reachable at ${API_URL}. Start direct API first."
            echo "Hint: docker compose -f docker/docker-compose.direct.yml up -d --build"
            exit 1
        fi

        echo "=== Contention Benchmark (Direct) ==="
        echo "  Concurrency : $CONCURRENT"
        echo "  API URL     : $API_URL"
        echo "  Workload    : $WORKLOAD"
        echo ""

        "$PYTHON_BIN" -m src.main \
            --mode benchmark-direct \
            --ticket-type numbered \
            --workload "$WORKLOAD" \
            --concurrent-clients "$CONCURRENT" \
            --api-url "$API_URL" \
            --output "$OUTPUT"
        ;;

    indirect)
        RESULTS_DIR="results/indirect/numbered/contention"
        OUTPUT="${RESULTS_DIR}/c${CONCURRENT}_${TIMESTAMP}.json"
        mkdir -p "$RESULTS_DIR"

        if ! timeout 2 bash -c "</dev/tcp/${RABBITMQ_HOST}/${RABBITMQ_PORT}" 2>/dev/null; then
            echo "Error: RabbitMQ not reachable at ${RABBITMQ_HOST}:${RABBITMQ_PORT}."
            echo "Hint: docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4"
            exit 1
        fi

        echo "=== Contention Benchmark (Indirect) ==="
        echo "  Concurrency : $CONCURRENT"
        echo "  Workload    : $WORKLOAD"
        echo ""

        "$PYTHON_BIN" -m src.main \
            --mode benchmark-indirect \
            --ticket-type numbered \
            --workload "$WORKLOAD" \
            --concurrent-clients "$CONCURRENT" \
            --output "$OUTPUT"
        ;;

    *)
        echo "Error: architecture must be 'direct' or 'indirect'."
        echo "Usage: ./scripts/run_contention_benchmark.sh [direct|indirect] [concurrent_clients] [api_url]"
        exit 1
        ;;
esac

echo "Results saved to: $OUTPUT"

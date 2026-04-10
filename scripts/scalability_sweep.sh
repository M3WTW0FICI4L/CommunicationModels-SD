#!/usr/bin/env bash
# Scalability sweep: run direct benchmark with 1,2,4,8,16 concurrent clients.
# Also tests both ticket types.
# Requires: direct API + Redis already running.
# Usage:
#   ./scripts/scalability_sweep.sh [api_url]

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

API_URL="${1:-http://localhost:80}"
RESULTS_DIR="results/direct"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTS_DIR"

if ! curl -fsS "${API_URL}/health" >/dev/null; then
    echo "Error: API not reachable at ${API_URL}. Start direct API first."
    echo "Hint A (docker, recommended): docker compose -f docker/docker-compose.direct.yml up -d --build"
    echo "Hint B (local API): python3 -m src.main --mode direct-api --host 0.0.0.0 --port 8000"
    echo "If using local API on 8000, run this script with: ./scripts/scalability_sweep.sh http://localhost:8000"
    exit 1
fi

for TICKET_TYPE in unnumbered numbered; do
    for C in 1 2 4 8 16 32; do

        if [ "$TICKET_TYPE" = "unnumbered" ]; then
            WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
        else
            WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
        fi

        OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${C}_${TIMESTAMP}.json"
        echo "Running: type=$TICKET_TYPE  concurrency=$C ..."

          # Reset state before each run (with retry)
          for retry in 1 2 3; do
              if curl -fsS -X POST "${API_URL}/reset" > /dev/null 2>&1; then
                  break
              fi
              if [ $retry -lt 3 ]; then sleep 0.5; fi
          done
            --ticket-type "$TICKET_TYPE" \
            --workload "$WORKLOAD" \
            --concurrent-clients "$C" \
            --api-url "$API_URL" \
            --output "$OUTPUT"

        echo "  → $OUTPUT"
    done
done

echo ""
echo "All sweeps done.  Results in $RESULTS_DIR/"

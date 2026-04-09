#!/usr/bin/env bash
# Scalability sweep: run direct benchmark with 1,2,4,8,16 concurrent clients.
# Also tests both ticket types.
# Requires: direct API + Redis already running.
# Usage:
#   ./scripts/scalability_sweep.sh [api_url]

set -euo pipefail

API_URL="${1:-http://localhost:80}"
RESULTS_DIR="results/direct"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTS_DIR"

for TICKET_TYPE in unnumbered numbered; do
    for C in 1 2 4 8 16 32; do

        if [ "$TICKET_TYPE" = "unnumbered" ]; then
            WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
        else
            WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
        fi

        OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}_c${C}_${TIMESTAMP}.json"
        echo "Running: type=$TICKET_TYPE  concurrency=$C ..."

        # Reset state before each run
        curl -s -X POST "${API_URL}/reset" > /dev/null

        python -m src.main \
            --mode benchmark-direct \
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

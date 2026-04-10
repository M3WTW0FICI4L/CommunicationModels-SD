#!/usr/bin/env bash
# Scalability sweep: run direct benchmark with 1,2,4,8,16 concurrent clients.
# Also tests both ticket types.
# If API is not running at localhost:80, this script can auto-start direct stack.
# Usage:
#   ./scripts/scalability_sweep.sh [api_url] [auto_start]
# Examples:
#   ./scripts/scalability_sweep.sh
#   ./scripts/scalability_sweep.sh http://localhost:80 true
#   ./scripts/scalability_sweep.sh http://localhost:8000 false

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
AUTO_START="${2:-true}"
RESULTS_DIR="results/direct"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

DOCKER_RUN_MODE="direct"
STARTED_DOCKER_STACK="false"

mkdir -p "$RESULTS_DIR/unnumbered" "$RESULTS_DIR/numbered"

detect_docker_run_mode() {
    if docker ps >/dev/null 2>&1; then
        DOCKER_RUN_MODE="direct"
        return 0
    fi

    if sg docker -c "docker ps" >/dev/null 2>&1; then
        DOCKER_RUN_MODE="sg"
        return 0
    fi

    return 1
}

run_docker_cmd() {
    local cmd="$1"
    if [ "$DOCKER_RUN_MODE" = "sg" ]; then
        sg docker -c "cd '$ROOT_DIR' && $cmd"
    else
        (
            cd "$ROOT_DIR"
            eval "$cmd"
        )
    fi
}

wait_for_api() {
    local tries=0
    while [ $tries -lt 60 ]; do
        if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    return 1
}

cleanup_stack() {
    if [ "$STARTED_DOCKER_STACK" = "true" ]; then
        echo "Stopping auto-started direct stack..."
        run_docker_cmd "docker compose -f docker/docker-compose.direct.yml down" || true
    fi
}

trap cleanup_stack EXIT

if ! curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
    if [ "$AUTO_START" = "true" ] && [ "$API_URL" = "http://localhost:80" ]; then
        echo "API not reachable at ${API_URL}. Trying to auto-start direct stack..."
        if ! detect_docker_run_mode; then
            echo "Error: Docker is not accessible in this session."
            echo "Run: ./scripts/setup_docker.sh"
            echo "Then: sg docker -c 'bash'   (or re-login)"
            exit 1
        fi

        run_docker_cmd "docker compose -f docker/docker-compose.direct.yml up -d --build"
        STARTED_DOCKER_STACK="true"

        if ! wait_for_api; then
            echo "Error: API did not become healthy at ${API_URL} after auto-start."
            exit 1
        fi
        echo "Direct API is up. Starting sweep..."
    else
        echo "Error: API not reachable at ${API_URL}. Start direct API first."
        echo "Hint A (docker, recommended): docker compose -f docker/docker-compose.direct.yml up -d --build"
        echo "Hint B (local API): python3 -m src.main --mode direct-api --host 0.0.0.0 --port 8000"
        echo "If using local API on 8000, run this script with: ./scripts/scalability_sweep.sh http://localhost:8000 false"
        exit 1
    fi
fi

for TICKET_TYPE in unnumbered numbered; do
    for C in 1 2 4 8 16 32; do

        if [ "$TICKET_TYPE" = "unnumbered" ]; then
            WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
        else
            WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
        fi

        OUTPUT="${RESULTS_DIR}/${TICKET_TYPE}/c${C}_${TIMESTAMP}.json"
        echo "Running: type=$TICKET_TYPE  concurrency=$C ..."

        # Reset state before each run (with retry)
        for retry in 1 2 3; do
            if curl -fsS -X POST "${API_URL}/reset" > /dev/null 2>&1; then
                break
            fi
            if [ $retry -lt 3 ]; then sleep 0.5; fi
        done

        "$PYTHON_BIN" -m src.main \
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
echo "All sweeps done. Results in:"
echo "  - ${RESULTS_DIR}/unnumbered/"
echo "  - ${RESULTS_DIR}/numbered/"
